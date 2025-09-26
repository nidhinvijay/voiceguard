# backend/call/consumers.py

import os
import asyncio
import json
from google.cloud import speech
from googleapiclient import discovery
from channels.generic.websocket import AsyncWebsocketConsumer
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, db
from groq import AsyncGroq

load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcloud-credentials.json"

try:
    cred = credentials.Certificate("gcloud-credentials.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': os.getenv("FIREBASE_DATABASE_URL")
    })
except ValueError:
    print("Firebase Admin already initialized.")

TOXICITY_THRESHOLD = 0.4

class CallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.call_id = self.scope['url_route']['kwargs']['call_id']
        self.call_group_name = f'call_{self.call_id}'
        await self.channel_layer.group_add(self.call_group_name, self.channel_name)

        # --- Initialize ALL clients once on connect ---
        self.speech_client = speech.SpeechAsyncClient()
        # NEW: Create the Perspective client once and store it
        self.perspective_client = await asyncio.to_thread(
            discovery.build,
            "commentanalyzer",
            "v1alpha1",
            developerKey=os.getenv("PERSPECTIVE_API_KEY"),
            static_discovery=False,
        )
        self.groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

        self.streaming_config = speech.StreamingRecognitionConfig(
            config=speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000, language_code="en-US",
            ),
            interim_results=True,
        )
        self.requests = asyncio.Queue()
        await self.accept()
        print("WebSocket connected. All API clients initialized.")

        self.response_iterator = await self.speech_client.streaming_recognize(
            requests=self.request_generator()
        )
        self.process_responses_task = asyncio.create_task(self.process_responses())

    # ... (disconnect, receive, request_generator, process_responses, transcript_message are unchanged)
    async def disconnect(self, close_code):
        print("WebSocket disconnected.")
        await self.channel_layer.group_discard(self.call_group_name, self.channel_name)
        if hasattr(self, 'process_responses_task'):
            self.process_responses_task.cancel()
        if hasattr(self, 'response_iterator'):
            await self.requests.put(None)

    async def receive(self, bytes_data):
        await self.requests.put(speech.StreamingRecognizeRequest(audio_content=bytes_data))

    async def request_generator(self):
        yield speech.StreamingRecognizeRequest(streaming_config=self.streaming_config)
        while True:
            chunk = await self.requests.get()
            if chunk is None:
                break
            yield chunk
            self.requests.task_done()

    async def process_responses(self):
        try:
            async for response in self.response_iterator:
                for result in response.results:
                    transcript = result.alternatives[0].transcript
                    await self.channel_layer.group_send(
                        self.call_group_name,
                        {"type": "transcript.message", "is_final": result.is_final, "transcript": transcript},
                    )
                    if result.is_final:
                        print(f"Final Transcript: {transcript}")
                        if transcript.strip():
                            await self.analyze_text(transcript)
        except asyncio.CancelledError:
            pass
            
    async def transcript_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "transcript", "is_final": event["is_final"], "transcript": event["transcript"],
        }))

    # THIS METHOD IS NOW SIMPLIFIED
    async def analyze_text(self, text):
        try:
            analyze_request = {
                'comment': {'text': text},
                'requestedAttributes': {'TOXICITY': {}}
            }
            # Use the client we created on connect
            response = await asyncio.to_thread(
                self.perspective_client.comments().analyze(body=analyze_request).execute
            )
            toxicity_score = response['attributeScores']['TOXICITY']['summaryScore']['value']
            print(f"  └── Toxicity Score: {toxicity_score:.4f}")
            
            if toxicity_score > TOXICITY_THRESHOLD:
                print("    └── High toxicity detected! Getting suggestion...")
                suggestion = await self.get_polite_suggestion(text)
                self.broadcast_moderation_alert(text, suggestion) # Made this synchronous

        except Exception as e:
            print(f"Error calling Perspective API: {e}")

    # THIS METHOD IS NOW SIMPLIFIED
    async def get_polite_suggestion(self, text):
        try:
            # Use the client we created on connect
            chat_completion = await self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are an assistant that rephrases harsh or toxic sentences into polite, constructive, and friendly alternatives."},
                    {"role": "user", "content": f"Please rephrase the following sentence: '{text}'"}
                ],
                model="llama-3.3-70b-versatile",
            )
            suggestion = chat_completion.choices[0].message.content
            print(f"    └── Groq Suggestion: {suggestion}")
            return suggestion
        except Exception as e:
            print(f"Error calling Groq API: {e}")
            return "Could not generate a suggestion."

    # Made this synchronous since firebase-admin is synchronous
    def broadcast_moderation_alert(self, original_text, suggestion):
        print("    └── Broadcasting alert to Firebase...")
        ref = db.reference(f'alerts/{self.call_id}')
        ref.push().set({
            'original': original_text,
            'suggestion': suggestion
        })