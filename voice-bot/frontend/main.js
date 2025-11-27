const toggleBtn = document.getElementById("toggle");
const statusEl = document.getElementById("status");
const meterFill = document.getElementById("meterFill");
const player = document.getElementById("player");

let isActive = false;
let isBusy = false; // true while sending or playing assistant audio

let stream = null;
let recorder = null;
let chunks = [];

let audioCtx = null;
let analyser = null;
let sourceNode = null;
let dataArray = null;
let rafId = null;

// VAD config with localStorage persistence
const VAD_STORAGE_KEY = "voicebot_vad_config_v1";
const VAD_DEFAULTS = {
  RMS_THRESHOLD: 0.012,
  SILENCE_MS: 1600,  // Increased to avoid cutting off pauses (was 1000)
  SPEECH_START_MS: 60
};

function loadVadConfig() {
  try {
    const raw = localStorage.getItem(VAD_STORAGE_KEY);
    if (!raw) return { ...VAD_DEFAULTS };
    const parsed = JSON.parse(raw);
    return { ...VAD_DEFAULTS, ...parsed };
  } catch {
    return { ...VAD_DEFAULTS };
  }
}

function saveVadConfig(cfg) {
  localStorage.setItem(VAD_STORAGE_KEY, JSON.stringify(cfg));
}

function setVadParam(key, value) {
  vadConfig[key] = value;
  saveVadConfig(vadConfig);
  if (key === "RMS_THRESHOLD") RMS_THRESHOLD = value;
  if (key === "SILENCE_MS") SILENCE_MS = value;
  if (key === "SPEECH_START_MS") SPEECH_START_MS = value;
}

let vadConfig = loadVadConfig();
let RMS_THRESHOLD = vadConfig.RMS_THRESHOLD;
let SILENCE_MS = vadConfig.SILENCE_MS;
let SPEECH_START_MS = vadConfig.SPEECH_START_MS;

let speechStartedAt = null;
let silenceStartedAt = null;
let hasSpeech = false;

function setUI() {
  toggleBtn.textContent = isActive ? "Deactivate" : "Activate";
  statusEl.textContent = isBusy
    ? "Thinking / Speaking…"
    : isActive
    ? (hasSpeech ? "Listening (speech)" : "Listening…")
    : "Inactive";
  toggleBtn.disabled = isBusy; // optional: lock toggle while busy
}

async function initMicAndAudioGraph() {
  stream = await navigator.mediaDevices.getUserMedia({ audio: true });

  recorder = new MediaRecorder(stream); // Chrome/Brave -> webm/opus
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);

  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  sourceNode = audioCtx.createMediaStreamSource(stream);
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 2048;
  dataArray = new Uint8Array(analyser.fftSize);
  sourceNode.connect(analyser);
}

function rmsFromTimeDomain(u8) {
  // convert 0..255 to -1..1, compute RMS
  let sumSq = 0;
  for (let i = 0; i < u8.length; i++) {
    const v = (u8[i] - 128) / 128;
    sumSq += v * v;
  }
  return Math.sqrt(sumSq / u8.length);
}

function resetTurnState() {
  speechStartedAt = null;
  silenceStartedAt = null;
  hasSpeech = false;
  chunks = [];
}

async function sendTurn(blob) {
  const ext = blob.type.includes("webm") ? "webm"
            : blob.type.includes("ogg")  ? "ogg"
            : blob.type.includes("mp4")  ? "mp4"
            : "wav";

  const fd = new FormData();
  fd.append("audio", blob, `recording.${ext}`);

  const res = await fetch("/api/turn", {
    method: "POST",
    body: fd
  });

  if (!res.ok) throw new Error(await res.text());
  return await res.blob();
}

function startRecordingIfNeeded() {
  if (recorder && recorder.state !== "recording") {
    chunks = [];
    recorder.start();
  }
}

function stopRecordingIfNeeded() {
  if (recorder && recorder.state === "recording") {
    recorder.stop();
  }
}

function loopVAD() {
  if (!isActive || isBusy) return; // stop scanning when inactive or busy

  analyser.getByteTimeDomainData(dataArray);
  const rms = rmsFromTimeDomain(dataArray);
  meterFill.style.width = `${Math.min(100, rms * 7000)}%`;

  const now = performance.now();

  if (rms >= RMS_THRESHOLD) {
    // above threshold -> possible speech
    silenceStartedAt = null;
    if (!speechStartedAt) speechStartedAt = now;

    if (!hasSpeech && (now - speechStartedAt) >= SPEECH_START_MS) {
      hasSpeech = true;
      startRecordingIfNeeded();
    }
  } else {
    // below threshold -> possible silence
    speechStartedAt = null;
    if (hasSpeech) {
      if (!silenceStartedAt) silenceStartedAt = now;

      if ((now - silenceStartedAt) >= SILENCE_MS) {
        // end of turn
        stopRecordingIfNeeded();
        recorder.onstop = async () => {
          try {
            isBusy = true; setUI();
            const inputBlob = new Blob(chunks, { type: recorder.mimeType });
            resetTurnState();

            const outBlob = await sendTurn(inputBlob);
            player.src = URL.createObjectURL(outBlob);
            await player.play();

            player.onended = () => {
              isBusy = false; setUI();
              if (isActive) rafId = requestAnimationFrame(loopVAD);
            };
          } catch (e) {
            console.error(e);
            isBusy = false; setUI();
            if (isActive) rafId = requestAnimationFrame(loopVAD);
          }
        };
        return; // wait for onstop chain
      }
    }
  }

  setUI();
  rafId = requestAnimationFrame(loopVAD);
}

async function activate() {
  if (!stream) await initMicAndAudioGraph();
  isActive = true;
  resetTurnState();
  setUI();
  rafId = requestAnimationFrame(loopVAD);
}

function deactivate() {
  isActive = false;
  resetTurnState();
  if (rafId) cancelAnimationFrame(rafId);
  rafId = null;
  stopRecordingIfNeeded();
  setUI();
}

toggleBtn.addEventListener("click", async () => {
  try {
    if (isActive) deactivate();
    else await activate();
  } catch (e) {
    console.error(e);
    statusEl.textContent = "Mic init failed. Check permissions.";
  }
});

// Ensure we don't listen while assistant audio is playing (echo safety)
player.addEventListener("play", () => {
  isBusy = true; setUI();
});
player.addEventListener("ended", () => {
  isBusy = false; setUI();
  if (isActive && !rafId) rafId = requestAnimationFrame(loopVAD);
});

// Calibration: measure noise floor and auto-set threshold
const calibrateBtn = document.getElementById("calibrate");
const calStatus = document.getElementById("calStatus");

async function calibrateNoiseFloor() {
  if (!analyser || !dataArray) {
    if (calStatus) calStatus.textContent = "Start mic first (click Activate)";
    return;
  }

  const wasActive = isActive;
  if (wasActive) deactivate();

  if (calStatus) calStatus.textContent = "Calibrating… stay silent";
  if (calibrateBtn) calibrateBtn.disabled = true;

  const durationMs = 3000;
  const intervalMs = 50;
  const samples = [];
  const start = performance.now();

  while (performance.now() - start < durationMs) {
    analyser.getByteTimeDomainData(dataArray);
    const rms = rmsFromTimeDomain(dataArray);
    samples.push(rms);
    await new Promise(r => setTimeout(r, intervalMs));
  }

  // Use median to resist spikes
  samples.sort((a, b) => a - b);
  const median = samples[Math.floor(samples.length / 2)] || 0.0;

  const multiplier = 2.5;
  let newThr = median * multiplier;
  newThr = Math.max(0.006, Math.min(0.03, newThr));
  newThr = Number(newThr.toFixed(3));

  setVadParam("RMS_THRESHOLD", newThr);

  if (calStatus) {
    calStatus.textContent = `Noise ${median.toFixed(4)} → threshold ${newThr.toFixed(3)}`;
  }
  if (calibrateBtn) calibrateBtn.disabled = false;

  // Update slider if it exists
  const thr = document.getElementById("thr");
  const thrVal = document.getElementById("thrVal");
  if (thr) thr.value = newThr;
  if (thrVal) thrVal.textContent = newThr.toFixed(3);

  if (wasActive) await activate();
}

if (calibrateBtn) {
  calibrateBtn.onclick = () => calibrateNoiseFloor().catch(console.error);
}

// Optional tuning sliders
const thr = document.getElementById("thr");
const thrVal = document.getElementById("thrVal");
const sil = document.getElementById("sil");
const silVal = document.getElementById("silVal");

if (thr && thrVal) {
  thr.value = RMS_THRESHOLD;
  thrVal.textContent = RMS_THRESHOLD.toFixed(3);
  thr.oninput = (e) => {
    const v = Number(e.target.value);
    setVadParam("RMS_THRESHOLD", v);
    thrVal.textContent = v.toFixed(3);
  };
}

if (sil && silVal) {
  sil.value = SILENCE_MS;
  silVal.textContent = SILENCE_MS;
  sil.oninput = (e) => {
    const v = Number(e.target.value);
    setVadParam("SILENCE_MS", v);
    silVal.textContent = v;
  };
}
