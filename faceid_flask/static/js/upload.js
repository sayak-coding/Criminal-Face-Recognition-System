/**
 * upload.js — handles drag/drop upload + AJAX recognition for upload.html
 */

const fileInput   = document.getElementById("fileInput");
const uploadZone  = document.getElementById("uploadZone");
const imageBox    = document.getElementById("imageBox");
const processBadge = document.getElementById("processingBadge");

const statEls = {
  matched: document.getElementById("statMatched"),
  unknown: document.getElementById("statUnknown"),
  total  : document.getElementById("statTotal"),
};

// ── Click to browse ──────────────────────────────────────────────────────────
uploadZone.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) processFile(fileInput.files[0]);
});

// ── Drag & Drop ──────────────────────────────────────────────────────────────
uploadZone.addEventListener("dragover", e => { e.preventDefault(); uploadZone.classList.add("dragging"); });
uploadZone.addEventListener("dragleave", ()  => uploadZone.classList.remove("dragging"));
uploadZone.addEventListener("drop", e => {
  e.preventDefault();
  uploadZone.classList.remove("dragging");
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) processFile(file);
});

// ── Process ──────────────────────────────────────────────────────────────────
async function processFile(file) {
  // Show preview immediately
  const objectUrl = URL.createObjectURL(file);
  showImage(objectUrl);

  processBadge.style.display = "flex";

  const formData = new FormData();
  formData.append("image", file);

  try {
    const resp = await fetch("/recognize/process", {
      method: "POST",
      body  : formData,
    });

    const data = await resp.json();

    if (data.error) {
      showError(data.error);
      return;
    }

    // Replace preview with annotated image from server
    showImage("data:image/jpeg;base64," + data.image);

    renderDetections(data.detections, statEls);

  } catch (err) {
    showError("Network error: " + err.message);
  } finally {
    processBadge.style.display = "none";
  }
}

function showImage(src) {
  imageBox.innerHTML = `<img src="${src}" alt="Result" style="width:100%;height:100%;object-fit:contain" />`;
}

function showError(msg) {
  document.getElementById("detectionList").innerHTML =
    `<div class="text-danger text-sm" style="padding:8px 0">❌ ${msg}</div>`;
}
