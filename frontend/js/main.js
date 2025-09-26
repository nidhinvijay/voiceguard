const firebaseConfig = {
    apiKey: "AIzaSyA62oFGhXZnUeq8ri_72MGU-M8SByrcikk",
    authDomain: "voiceguard2-d44ed.firebaseapp.com",
    databaseURL: "https://voiceguard2-d44ed-default-rtdb.firebaseio.com",
    projectId: "voiceguard2-d44ed",
    storageBucket: "voiceguard2-d44ed.firebasestorage.app",
    messagingSenderId: "967320846038",
    appId: "1:967320846038:web:bb7323840f0b7edf8d1377"
};

firebase.initializeApp(firebaseConfig);
const database = firebase.database();

const configuration = {
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
};

let peerConnection = null;
let localStream = null;
let remoteStream = null;
let userRole = null;

// --- HTML Elements ---
const localAudio = document.getElementById('local-audio');
const remoteAudio = document.getElementById('remote-audio');
const callId = document.getElementById('call-id').innerText;
const callRef = database.ref(`calls/${callId}`);
const callerCandidatesRef = callRef.child('callerCandidates');
const calleeCandidatesRef = callRef.child('calleeCandidates');


// THIS IS THE UPDATED init() FUNCTION WITH DEBUG LOGS
async function init() {
    try {
        console.log("1. Starting initialization...");

        console.log("2. Requesting microphone access...");
        localStream = await navigator.mediaDevices.getUserMedia({ video: false, audio: true });
        localAudio.srcObject = localStream;
        console.log("3. Microphone access granted!");

        console.log("4. Creating peer connection...");
        peerConnection = new RTCPeerConnection(configuration);

        localStream.getTracks().forEach(track => {
            peerConnection.addTrack(track, localStream);
        });

        peerConnection.ontrack = event => {
            remoteStream = event.streams[0];
            remoteAudio.srcObject = remoteStream;
            console.log("Received remote stream!");
        };

        const offerSnapshot = await callRef.child('offer').get();
        if (offerSnapshot.exists()) {
            userRole = 'callee';
            await createAnswer(offerSnapshot.val());
        } else {
            userRole = 'caller';
            await createOffer();
        }
        
        console.log("5. Setting up listeners and starting streaming...");
        setupIceCandidateListeners();
        setupAudioStreaming();
        listenForModerationAlerts();
        console.log("6. Initialization complete!");

    } catch (error) {
        console.error("--- ERROR DURING INITIALIZATION ---", error);
    }
}


// --- Other functions (no changes below this line) ---

async function createOffer() {
    console.log("Creating offer...");
    callRef.child('answer').on('value', async snapshot => {
        if (snapshot.exists() && !peerConnection.currentRemoteDescription) {
            console.log("Received answer, setting remote description.");
            const answer = new RTCSessionDescription(snapshot.val());
            await peerConnection.setRemoteDescription(answer);
        }
    });
    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    await callRef.child('offer').set({ type: offer.type, sdp: offer.sdp });
}

async function createAnswer(offerData) {
    console.log("Creating answer...");
    const offer = new RTCSessionDescription(offerData);
    await peerConnection.setRemoteDescription(offer);
    const answer = await peerConnection.createAnswer();
    await peerConnection.setLocalDescription(answer);
    await callRef.child('answer').set({ type: answer.type, sdp: answer.sdp });
}

function setupIceCandidateListeners() {
    peerConnection.onicecandidate = event => {
        if (event.candidate) {
            if (userRole === 'caller') {
                callerCandidatesRef.push(event.candidate.toJSON());
            } else {
                calleeCandidatesRef.push(event.candidate.toJSON());
            }
        }
    };
    if (userRole === 'caller') {
        calleeCandidatesRef.on('child_added', snapshot => {
            const candidate = new RTCIceCandidate(snapshot.val());
            peerConnection.addIceCandidate(candidate);
        });
    } else {
        callerCandidatesRef.on('child_added', snapshot => {
            const candidate = new RTCIceCandidate(snapshot.val());
            peerConnection.addIceCandidate(candidate);
        });
    }
}

function setupAudioStreaming() {
    if (!localStream) {
        console.error("Local stream not available for streaming.");
        return;
    }
    const socketProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socketURL = `${socketProtocol}//${window.location.host}/ws/call/${callId}/`;
    const audioSocket = new WebSocket(socketURL);
    audioSocket.onopen = () => {
        console.log("Audio WebSocket connected!");
        const mediaRecorder = new MediaRecorder(localStream, { mimeType: 'audio/webm' });
        mediaRecorder.ondataavailable = event => {
            if (event.data.size > 0) {
                audioSocket.send(event.data);
            }
        };
        mediaRecorder.start(500);
    };
    audioSocket.onmessage = event => {
        const data = JSON.parse(event.data);
        if (data.type === 'transcript') {
            updateTranscript(data.transcript, data.is_final);
        }
    };
    audioSocket.onclose = () => {
        console.log("Audio WebSocket disconnected.");
    };
    audioSocket.onerror = (error) => {
        console.error("Audio WebSocket error:", error);
    };
}

let transcriptContainer = document.getElementById('my-transcript');
let currentSentenceSpan = null;

function updateTranscript(text, isFinal) {
    if (!currentSentenceSpan || isFinal) {
        currentSentenceSpan = document.createElement('span');
        transcriptContainer.appendChild(currentSentenceSpan);
        if (!isFinal) {
            transcriptContainer.appendChild(document.createTextNode(' '));
        }
    }
    currentSentenceSpan.textContent = text;
    if (isFinal) {
        currentSentenceSpan = null;
    }
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;
}

function listenForModerationAlerts() {
    const alertsRef = database.ref(`alerts/${callId}`);
    alertsRef.on('child_added', snapshot => {
        const alertData = snapshot.val();
        displayModerationAlert(alertData.original, alertData.suggestion);
    });
}

function displayModerationAlert(originalText, suggestion) {
    const alertsContainer = document.getElementById('public-alerts');
    const alertDiv = document.createElement('div');
    alertDiv.className = 'p-2 mb-2 bg-red-900/50 border border-red-700 rounded-lg';
    const originalP = document.createElement('p');
    originalP.innerHTML = `<strong>Original:</strong> ${originalText}`;
    const suggestionP = document.createElement('p');
    suggestionP.className = 'mt-1 text-green-300';
    suggestionP.innerHTML = `<strong>Suggestion:</strong> ${suggestion}`;
    alertDiv.appendChild(originalP);
    alertDiv.appendChild(suggestionP);
    alertsContainer.appendChild(alertDiv);
    alertsContainer.scrollTop = alertsContainer.scrollHeight;
}

// Start the process
init();