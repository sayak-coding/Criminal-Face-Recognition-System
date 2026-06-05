/**
 * webcam.js — live webcam → SocketIO → annotated frame + detections
 *
 * Key fixes vs v1:
 *  - processingFrame flag: don't send a new frame until server responds
 *  - Interval-based sending (not rAF-based) so DeepFace latency doesn't
 *    affect the display frame rate
 *  - Auto-reconnect on disconnect
 *  - Canvas draw is decoupled from frame sending
 */

const video       = document.getElementById("webcamVideo");
const canvas      = document.getElementById("resultCanvas");
const placeholder = document.getElementById("camPlaceholder");
const liveStatus  = document.getElementById("liveStatus");
const startBtn    = document.getElementById("startBtn");
const stopBtn     = document.getElementById("stopBtn");

const statEls = {
  matched: document.getElementById("statMatched"),
  unknown: document.getElementById("statUnknown"),
  fps    : document.getElementById("statFps"),
};

const ctx    = canvas.getContext("2d");
const socket = io({ reconnection: true, reconnectionDelay: 1000, reconnectionAttempts: 10 });

let stream          = null;
let running         = false;
let processingFrame = false;   // true while server is working on a frame
let sendInterval    = null;
let displayInterval = null;
let frameCount      = 0;
let fpsInterval     = null;
let lastResultImg   = null;

// ── Start ─────────────────────────────────────────────────────────────────────
async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" }
    });
    video.srcObject = stream;
    video.style.display  = "block";
    canvas.style.display = "block";
    placeholder.style.display = "none";

    await new Promise(resolve => { video.onloadedmetadata = resolve; });
    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;

    running = true;
    processingFrame = false;
    lastResultImg = null;

    startBtn.style.display = "none";
    stopBtn.style.display  = "inline-flex";
    setStatus("LIVE", "var(--success)");

    // ── Display loop — runs at ~30fps independently of DeepFace ──
    displayInterval = setInterval(() => {
      if (!running) return;
      frameCount++;
      if (lastResultImg) {
        const img = new Image();
        img.onload = () => {
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          lastResultImg = null;
        };
        img.src = "data:image/jpeg;base64," + lastResultImg;
      } else {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      }
    }, 33);

    // ── Send loop — only send when server is free ──
    // Sends at most every 200ms, and only if previous result received
    sendInterval = setInterval(() => {
      if (!running || processingFrame) return;
      sendFrame();
    }, 200);

    fpsInterval = setInterval(() => {
      if (statEls.fps) statEls.fps.textContent = frameCount;
      frameCount = 0;
    }, 1000);

  } catch (err) {
    setStatus("ERROR: " + err.message, "var(--danger)");
  }
}

// ── Stop ──────────────────────────────────────────────────────────────────────
function stopCamera() {
  running = false;
  processingFrame = false;

  if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
  clearInterval(sendInterval);
  clearInterval(displayInterval);
  clearInterval(fpsInterval);

  video.style.display   = "none";
  canvas.style.display  = "none";
  placeholder.style.display = "flex";

  startBtn.style.display = "inline-flex";
  stopBtn.style.display  = "none";
  setStatus("IDLE", "var(--dim)");

  renderProfileIdle();
  document.getElementById("detectionList").innerHTML =
    '<div class="text-dim text-sm" style="padding:8px 0">— No detection yet</div>';
  document.getElementById("faceCountLabel").textContent = "";
}

// ── Send one frame to server ──────────────────────────────────────────────────
function sendFrame() {
  if (!video.videoWidth) return;

  processingFrame = true;

  const offscreen = document.createElement("canvas");
  offscreen.width  = Math.round(video.videoWidth  * 0.5);
  offscreen.height = Math.round(video.videoHeight * 0.5);
  offscreen.getContext("2d").drawImage(video, 0, 0, offscreen.width, offscreen.height);

  offscreen.toBlob(blob => {
    const reader = new FileReader();
    reader.onloadend = () => {
      socket.emit("frame", { image: reader.result.split(",")[1] });
    };
    reader.readAsDataURL(blob);
  }, "image/jpeg", 0.75);
}

// ── Receive result ────────────────────────────────────────────────────────────
socket.on("result", data => {
  processingFrame = false;   // ALWAYS reset — error, empty, or success

  if (data.error) {
    console.warn("Server error:", data.error);
    document.getElementById("detectionList").innerHTML =
      `<div style="color:var(--danger);font-size:12px;padding:8px 0">⚠ ${data.error}</div>`;
    return;
  }

  if (data.image) {
    lastResultImg = data.image;
  }

  if (data.detections !== undefined) {
    renderDetections(data.detections, statEls);
  }
});

// ── Connection events ─────────────────────────────────────────────────────────
socket.on("connect", () => {
  console.log("Socket connected:", socket.id);
  if (running) setStatus("LIVE", "var(--success)");
});

socket.on("disconnect", reason => {
  processingFrame = false;   // unblock on disconnect
  setStatus("DISCONNECTED — reconnecting…", "var(--warning)");
  console.warn("Socket disconnected:", reason);
});

socket.on("reconnect", () => {
  if (running) setStatus("LIVE", "var(--success)");
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function setStatus(text, color) {
  liveStatus.textContent = "● " + text;
  liveStatus.style.color = color;
}