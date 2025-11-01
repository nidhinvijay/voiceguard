# core/consumers.py

import json
import threading
from queue import Queue
import os
import time
from urllib.parse import parse_qs
import requests
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from google.cloud import speech
from groq import Groq
import time


class CallConsumer(WebsocketConsumer):
    def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'call_{self.room_name}'

        # --- language from query ?lang=en-US / ml-IN (default en-US)
        query_string = parse_qs(self.scope['query_string'].decode())
        self.language_code = query_string.get('lang', ['en-US'])[0]

        # Audio queue + stop flag for Google streaming thread
        self.audio_queue = Queue()
        self.stop_transcription = threading.Event()

        async_to_sync(self.channel_layer.group_add)(self.room_group_name, self.channel_name)
        self.accept()

        # Start STT + moderation thread
        self.transcription_thread = threading.Thread(target=self.google_streaming_thread)
        self.transcription_thread.start()

    def disconnect(self, close_code):
        # Signal thread to stop
        self.stop_transcription.set()
        # Unblock audio queue
        try:
            self.audio_queue.put_nowait(None)
        except Exception:
            pass
        # Join briefly
        if self.transcription_thread.is_alive():
            self.transcription_thread.join(timeout=1)

        async_to_sync(self.channel_layer.group_discard)(self.room_group_name, self.channel_name)

    def receive(self, text_data=None, bytes_data=None):
        # Receive raw PCM chunks from AudioWorklet
        if bytes_data:
            self.audio_queue.put(bytes_data)

    def google_streaming_thread(self):
        """
        Handles a loop of Google STT streaming sessions (each ~4.5 minutes) and
        Perspective/Groq moderation. Emits:
          - type="transcript" messages when final transcripts arrive
          - type="ai_suggestion" messages for polite rephrasing
          - type="toxicity" messages with numeric score (0..1) for client-side averaging
        """
        print("Google streaming thread started.")

        while not self.stop_transcription.is_set():
            if self.stop_transcription.is_set():
                break
            print("Starting new Google streaming session...")

            # Clients
            speech_client = speech.SpeechClient()
            groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            API_KEY = os.environ.get('PERSPECTIVE_API_KEY')
            perspective_url = f'https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze?key={API_KEY}'

            # Google STT config
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=self.language_code,
                enable_automatic_punctuation=True
            )
            streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=True)

            session_start = time.time()
            MAX_SESSION_DURATION = 270  # ~4.5 min

            def audio_generator():
                while not self.stop_transcription.is_set():
                    # cut session before 305s limit
                    if time.time() - session_start > MAX_SESSION_DURATION:
                        print("Session duration limit reached. Ending stream gracefully.")
                        return
                    try:
                        chunk = self.audio_queue.get(timeout=1.0)
                        if chunk is None:
                            return
                        yield speech.StreamingRecognizeRequest(audio_content=chunk)
                    except Exception:
                        continue

            try:
                responses = speech_client.streaming_recognize(
                    config=streaming_config,
                    requests=audio_generator()
                )

                for response in responses:
                    if self.stop_transcription.is_set():
                        break

                    for result in response.results:
                        if result.is_final and result.alternatives:
                            transcript = result.alternatives[0].transcript
                            if not transcript.strip():
                                continue
                            print(f"Final Transcript: {transcript}")

                            # push transcript to all sockets in room
                            async_to_sync(self.channel_layer.group_send)(
                                self.room_group_name,
                                {'type': 'chat_message', 'message': f"Transcript: {transcript}"}
                            )

                            # Toxicity check via Perspective
                            try:
                                analyze_request = {
                                    'comment': {'text': transcript},
                                    'requestedAttributes': {'TOXICITY': {}}
                                }
                                resp = requests.post(perspective_url, json=analyze_request, timeout=5)
                                resp.raise_for_status()
                                toxicity_score = resp.json()['attributeScores']['TOXICITY']['summaryScore']['value']
                                print(f"  -> Toxicity Score: {toxicity_score:.2f}")

                                # NEW: emit raw score so client can compute avg
                                async_to_sync(self.channel_layer.group_send)(
                                    self.room_group_name,
                                    {'type': 'toxicity_metric', 'score': toxicity_score}
                                )

                                # If toxic enough, generate polite suggestion using Groq
                                if toxicity_score > 0.1:
                                    print("  -> High toxicity detected! Sending suggestion...")

                                    if self.language_code == 'ml-IN':
                                        system_prompt = (
                                            "You are a moderation assistant. The user provides a toxic comment in Malayalam. "
                                            "Your job is to rephrase it into a polite, constructive alternative, also in Malayalam. "
                                            "Always provide a rephrasing. Do not refuse. "
                                            "Begin your response with: 'ക്ഷമിക്കണം, പക്ഷെ അത് പറയാൻ ഇതിലും നല്ലൊരു രീതിയുണ്ട്:'. "
                                            "Keep your response short and respectful."
                                        )
                                    else:
                                        system_prompt = (
                                            "You are a moderation assistant. Rephrase the toxic comment politely. "
                                            "Begin with: 'Please refrain. A better way to say that might be:'. "
                                            "Keep under 15 words. No extra commentary."
                                        )

                                    stream = groq_client.chat.completions.create(
                                        messages=[
                                            {"role": "system", "content": system_prompt},
                                            {"role": "user", "content": transcript}
                                        ],
                                        model="llama-3.1-8b-instant",
                                        stream=True
                                    )
                                    suggestion = "".join(chunk.choices[0].delta.content or "" for chunk in stream)
                                    print(f"  -> AI Suggestion: {suggestion}")

                                    if suggestion.strip():
                                        async_to_sync(self.channel_layer.group_send)(
                                            self.room_group_name,
                                            {'type': 'ai_suggestion', 'suggestion': suggestion}
                                        )
                            except Exception as e:
                                print(f"  -> Error in toxicity/AI pipeline: {e}")

            except Exception as e:
                print(f"Error in Google streaming session: {e}")
                if "305" in str(e) or "maximum allowed stream duration" in str(e):
                    print("Google stream hit time limit. Will restart automatically.")

            if not self.stop_transcription.is_set():
                time.sleep(0.5)

        print("Google streaming thread has been stopped.")

    # ---- WS event handlers (to client) ----

    def ai_suggestion(self, event):
        self.send(text_data=json.dumps({
            'type': 'ai_suggestion',
            'suggestion': event['suggestion']
        }))

    def chat_message(self, event):
        self.send(text_data=json.dumps({
            "type": "transcript",
            "message": event['message']
        }))

    # NEW: per-utterance numeric toxicity score to client
    def toxicity_metric(self, event):
        self.send(text_data=json.dumps({
            'type': 'toxicity',
            'score': event['score']
        }))
