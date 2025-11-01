// static/js/voiceguard.js

(() => {
  // ======= Elements =======
  const logDiv = document.getElementById('log');
  const callBtn = document.getElementById('call-button');
  const hangBtn = document.getElementById('hang-button');
  const peerPhoneInput = document.getElementById('peer-phone-input');
  const lifetimeBadge = document.getElementById('peer-lifetime-badge');
  const languageSelect = document.getElementById('language-select');
  const transcribeButton = document.getElementById('transcribe-button');
  const startAudioButton = document.getElementById('start-audio-button');

  const incomingModal = document.getElementById('incoming-modal');
  const incomingMeta = document.getElementById('incoming-meta');
  const acceptBtn = document.getElementById('accept-btn');
  const declineBtn = document.getElementById('decline-btn');

  // ======= Voice SDK state =======
  let device = null;     // Twilio.Device
  let activeCall = null; // Twilio.Call
  let pendingIncoming = null;

  // ======= Moderation state =======
  let audioContext = null;
  let transcriptionSocket = null;
  let toxicityScores = [];
  let callStartedAt = null;

  // ======= Helpers =======
  function log(msg) {
    logDiv.innerHTML += `<p>&gt; ${msg}</p>`;
    logDiv.scrollTop = logDiv.scrollHeight;
  }
  function csrfToken() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }
  function debounce(fn, wait=350) {
    let t = null; return (...a)=>{clearTimeout(t);t=setTimeout(()=>fn(...a),wait);};
  }
  function primeTTS() {
    try { window.speechSynthesis.speak(new SpeechSynthesisUtterance('')); } catch {}
  }

  // ======= Lifetime toxicity lookup =======
  const lookupLifetime = debounce(async () => {
    const raw = (peerPhoneInput.value || '').trim();
    if (!raw) { lifetimeBadge.textContent = ''; return; }
    const isIN = /^\+91\d{10}$/.test(raw) || /^\d{10}$/.test(raw);
    if (!isIN) { lifetimeBadge.textContent = ''; return; }
    const normalized = /^\d{10}$/.test(raw) ? `+91${raw}` : raw;
    try {
      const url = new URL(window.location.origin + '/users/lifetime_avg');
      url.searchParams.set('phone', normalized);
      const resp = await fetch(url, { credentials: 'same-origin' });
      const data = await resp.json();
      if (data && data.ok) {
        const v = data.lifetime_avg;
        lifetimeBadge.textContent = (v == null) ? '(no history)' : `(lifetime avg: ${Number(v).toFixed(2)})`;
      } else {
        lifetimeBadge.textContent = '(no profile)';
      }
    } catch { lifetimeBadge.textContent = ''; }
  });
  peerPhoneInput?.addEventListener('input', lookupLifetime);

  // ======= Token + Device =======
  async function getToken() {
    const r = await fetch('/token/', { credentials: 'same-origin' });
    const j = await r.json();
    if (!j || !j.ok) throw new Error('Token error');
    return j;
  }

  async function ensureDeviceRegistered() {
    if (!window.Twilio || !Twilio.Device) {
      log('Twilio Voice SDK not found. Ensure twilio-voice.min.js is loaded.');
      throw new Error('Twilio SDK missing');
    }
    if (device && device.state === 'registered') return;

    const { token } = await getToken();
    device = new Twilio.Device(token.toString(), { debug: false });

    device.on('registered', () => log('Device registered (ready).'));
    device.on('error', e => log('Device error: ' + (e?.message || e)));

    // Auto refresh token when expiring
    device.on('tokenWillExpire', async () => {
      try { const { token: t } = await getToken(); device.updateToken(t.toString()); } catch {}
    });

    device.on('incoming', handleIncoming);
    await device.register();
  }

  // Auto-register on load (so the tab can receive calls)
  (async () => {
    try {
      await ensureDeviceRegistered();
      const info = await (await fetch('/token/', { credentials: 'same-origin' })).json();
      if (info && info.ok && info.identity) log('Registered as ' + info.identity);
    } catch (e) {
      console.error(e);
      log('Could not register device on load.');
    }
  })();

  // ======= Incoming flow (Accept/Decline modal) =======
  async function fetchLifetimeForIncoming(phone) {
    if (!/^\+91\d{10}$/.test(phone)) return;
    try {
      const url = new URL(window.location.origin + '/users/lifetime_avg');
      url.searchParams.set('phone', phone);
      const r = await fetch(url, { credentials: 'same-origin' });
      const j = await r.json();
      if (j && j.ok) {
        const v = j.lifetime_avg;
        const badge = (v == null) ? '(no history)' : `(lifetime avg: ${Number(v).toFixed(2)})`;
        incomingMeta.textContent = `From: ${phone}  ${badge}`;
      }
    } catch {}
  }

  // --- Deep link support: /?dial=+91... or /?prefill=+91... ---
(function handleDialDeepLink() {
  const params = new URLSearchParams(location.search);
  const dial = params.get("dial");
  const prefill = params.get("prefill");
  const phoneInput = document.getElementById("peer-phone-input");
  const callBtn = document.getElementById("call-button");

  if (!phoneInput) return;

  const setNumber = (num) => {
    if (!num) return;
    phoneInput.value = num.startsWith("+91") ? num : `+91${num.replace(/^\+?/, "")}`;
  };

  // Always prefill if present
  if (prefill) setNumber(prefill);

  // If `dial` is present, prefill and auto-dial once the device is ready
  if (dial) {
    setNumber(dial);

    // Wait for Twilio Device & DOM to be ready; try a few times
    let attempts = 0;
    const tryDial = () => {
      attempts += 1;
      const disabled = callBtn && callBtn.hasAttribute("disabled");
      if (callBtn && !disabled) {
        callBtn.click(); // trigger your existing click handler
        // Clean the query so refresh doesn't re-dial
        const url = new URL(location.href);
        url.searchParams.delete("dial");
        history.replaceState({}, "", url.toString());
        return;
      }
      if (attempts < 50) setTimeout(tryDial, 200); // retry for ~10s
    };
    tryDial();
  }
})();


  function handleIncoming(call) {
    pendingIncoming = call;
    const from = (call.parameters && call.parameters.From) || 'unknown';
    const normalized = /^\d{10}$/.test(from) ? `+91${from}` : from;
    incomingMeta.textContent = `From: ${normalized}`;
    fetchLifetimeForIncoming(normalized);

    incomingModal.style.display = 'block';

    let cleaned = false;
    const cleanup = () => {
      if (cleaned) return;
      cleaned = true;
      incomingModal.style.display = 'none';
      acceptBtn.onclick = null;
      declineBtn.onclick = null;
      pendingIncoming = null;
    };

    acceptBtn.onclick = () => {
      try { call.accept(); } catch {}
      log('Call accepted.');
      hangBtn.disabled = false;
      transcribeButton.disabled = false;
      startAudioButton.style.display = 'inline-block';
      activeCall = call;
      primeTTS();
      // When either side hangs up, we’ll cleanly reset below
      wireActiveCallEvents(call);
      cleanup();
    };

    declineBtn.onclick = () => {
      try { call.reject(); } catch {}
      log('Call declined.');
      cleanup();
    };

    // If caller cancels before answering
    call.on('cancel', () => { log('Caller hung up.'); cleanup(); });
    call.on('disconnect', () => { log('Call ended.'); cleanup(); });
  }

  function wireActiveCallEvents(call) {
  // Mark the real call start when media is established
  call.on('accept', () => {
    if (!callStartedAt) callStartedAt = new Date();
  });

  call.on('disconnect', async () => {
    // This fires on BOTH sides when one hangs up
    activeCall = null;
    hangBtn.disabled = true;
    transcribeButton.disabled = true;
    log('Peer disconnected.');
    await postCallSummary();
    toxicityScores = [];
    callStartedAt = null;
  });

  call.on('error', e => log('Call error: ' + (e?.message || e)));
}

  // ======= Call controls =======
  callBtn?.addEventListener('click', async () => {
    const to = (peerPhoneInput.value || '').trim();
    if (!to) { log('Enter callee identity (+91XXXXXXXXXX).'); return; }
    window.sessionStorage.setItem('peer_phone', to);

    try {
      await ensureDeviceRegistered();
      primeTTS();
      const call = await device.connect({ params: { To: to } });
      activeCall = call;
      if (!callStartedAt) callStartedAt = new Date();
      log('Calling ' + to + ' ...');
      hangBtn.disabled = false;
      transcribeButton.disabled = false;
      startAudioButton.style.display = 'inline-block';
      wireActiveCallEvents(call);
    } catch (e) {
      console.error(e);
      log('Call failed to start.');
    }
  });

  hangBtn?.addEventListener('click', async () => {
    if (activeCall) { try { activeCall.disconnect(); } catch {} activeCall = null; }
    log('You hung up.');
    hangBtn.disabled = true;
    transcribeButton.disabled = true;

    await postCallSummary();
    toxicityScores = [];
    callStartedAt = null;
  });

  // ======= Moderation (client mic → WS → server) =======
  transcribeButton?.addEventListener('click', async () => {
    log('Starting transcription stream...');
    const selectedLang = languageSelect.value;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = protocol + '//' + window.location.host + '/ws/call/voiceguard/?lang=' + selectedLang;
    transcriptionSocket = new WebSocket(wsUrl);

    transcriptionSocket.onopen = async () => {
      log('WebSocket connected. Initializing Audio Worklet...');
      audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
      if (audioContext.state === 'suspended') { await audioContext.resume(); }

      try {
        await audioContext.audioWorklet.addModule('/static/js/audio-processor.js');
      } catch(e) {
        console.error('Error loading audio worklet module', e);
        log('Error: Could not load audio processor.');
        return;
      }

      const workletNode = new AudioWorkletNode(audioContext, 'audio-processor');
      workletNode.port.onmessage = (event) => {
        if (transcriptionSocket.readyState === WebSocket.OPEN) transcriptionSocket.send(event.data);
      };

      try {
        const mic = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        const micSource = audioContext.createMediaStreamSource(mic);
        micSource.connect(workletNode);
      } catch (e) {
        console.error(e);
        log('Microphone permission denied or unavailable.');
        return;
      }

      transcribeButton.disabled = true;
      log('Streaming local mic audio to server for moderation.');
    };

    transcriptionSocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const selectedLang = languageSelect.value;

      if (data.type === 'transcript') {
        log(data.message);
        if (!callStartedAt) callStartedAt = new Date();
      } else if (data.type === 'ai_suggestion') {
        log(`AI: ${data.suggestion}`);
        const u = new SpeechSynthesisUtterance(data.suggestion);
        u.lang = selectedLang;
        window.speechSynthesis.speak(u);
      } else if (data.type === 'toxicity') {
        if (typeof data.score === 'number') toxicityScores.push(data.score);
      }
    };
  });

  // ======= Post call summary =======
  async function postCallSummary() {
    let avg = 0;
    if (toxicityScores.length) {
      const sum = toxicityScores.reduce((a,b)=>a+b,0);
      avg = sum / toxicityScores.length;
    }
    const peerPhone = window.sessionStorage.getItem('peer_phone') || '';
    const selectedLang = languageSelect.value;
    const endedAt = new Date();
    const startedISO = (callStartedAt || endedAt).toISOString();

    try {
      const resp = await fetch('/calls/finish', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': csrfToken()
        },
        credentials: 'same-origin',
        body: new URLSearchParams({
          peer_phone: peerPhone,
          started_at: startedISO,
          ended_at: endedAt.toISOString(),
          avg_toxicity: String(avg),
          lang: selectedLang
        })
      });
      const data = await resp.json();
      if (data.ok) {
        log(`Call saved. Your lifetime avg: ${((data.lifetime_avg ?? 0) * 1).toFixed(2)}`);
      } else {
        log('Could not save call: ' + (data.error || 'unknown'));
      }
    } catch (e) {
      console.error(e);
      log('Error posting call summary.');
    }
  }

  // ======= Mobile UX: resume audio on first tap if needed =======
  document.addEventListener('click', () => {
    if (audioContext && audioContext.state === 'suspended') {
      audioContext.resume().catch(()=>{});
    }
  });
})();
