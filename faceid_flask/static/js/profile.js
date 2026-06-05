/**
 * profile.js
 * Renders the right-column profile card.
 * Shared by upload.js and webcam.js.
 *
 * Fixes:
 *  - Multiple faces: shows tab switcher so you can view each person's profile
 *  - Single face: renders directly as before
 */

// ── Keep track of currently shown detections for tab switching ───────────────
let _currentDetections = [];

// ── Idle / Unknown states ─────────────────────────────────────────────────────
function renderProfileIdle() {
  _currentDetections = [];
  const card  = document.getElementById("profileCard");
  const badge = document.getElementById("profileBadge");
  if (badge) { badge.textContent = "NO MATCH"; badge.style.color = "var(--dim)"; }
  card.innerHTML = '<div class="profile-idle">Awaiting recognition…</div>';
}

function renderProfileUnknown() {
  const card  = document.getElementById("profileCard");
  const badge = document.getElementById("profileBadge");
  if (badge) { badge.textContent = "UNKNOWN"; badge.style.color = "var(--danger)"; }
  card.innerHTML = `
    <div class="profile-idle" style="color:var(--danger)">
      <div style="font-size:22px;margin-bottom:8px">✘</div>
      <div style="font-weight:bold;font-size:15px">Unknown Subject</div>
      <div class="text-dim text-sm" style="margin-top:6px">No matching record in database</div>
    </div>`;
}

// ── Render full profile for one person ────────────────────────────────────────
function renderProfile(profile, displayPct) {
  const card  = document.getElementById("profileCard");
  const badge = document.getElementById("profileBadge");

  const status    = profile.status || "";
  const isActive  = status.toLowerCase().includes("active") && !status.toLowerCase().includes("not");
  const statusClr = isActive ? "var(--danger)" : "var(--warning)";
  const badgeTxt  = isActive ? "⚠ ACTIVE" : "● INACTIVE";

  if (badge) { badge.textContent = badgeTxt; badge.style.color = statusClr; }

  const pct   = Math.round(displayPct * 100);
  const fillW = Math.min(100, pct);

  const activitiesHtml = (profile.activities || []).map(act => `
    <div class="activity-item">
      <span class="activity-bullet">▸</span>
      <span class="activity-text">${escHtml(act)}</span>
    </div>`).join("");

  // Preserve tabs if multiple people were detected
  const tabsEl = card.querySelector(".profile-tabs");
  const tabsHtml = tabsEl ? tabsEl.outerHTML : "";

  card.innerHTML = `
    ${tabsHtml}
    <div style="padding:12px">
      <div class="profile-name-banner">
        <div class="profile-name">${escHtml(profile.name)}</div>
        <div class="profile-conf">Match confidence: ${pct}%</div>
        <div class="conf-bar-wrap">
          <div class="conf-bar-fill" style="width:${fillW}%"></div>
        </div>
      </div>
    </div>

    <div class="profile-section-title">PERSONAL DETAILS</div>
    <div class="profile-field">
      <span class="profile-field-label">Date of Birth</span>
      <span class="profile-field-value">${escHtml(profile.date_of_birth || "N/A")}</span>
    </div>
    <div class="profile-field">
      <span class="profile-field-label">Date of Death</span>
      <span class="profile-field-value">${escHtml(profile.date_of_death || "N/A")}</span>
    </div>
    <div class="profile-field">
      <span class="profile-field-label">Status</span>
      <span class="profile-field-value" style="color:${statusClr}">${escHtml(status)}</span>
    </div>

    ${activitiesHtml.length ? `
    <div class="profile-section-title">KEY ACTIVITIES</div>
    ${activitiesHtml}` : ""}

    <div style="height:16px"></div>`;
}

// ── Tab switcher for multiple detected faces ──────────────────────────────────
function renderProfileTabs(detections, activeIdx) {
  const card  = document.getElementById("profileCard");
  const badge = document.getElementById("profileBadge");

  const known = detections.filter(d => d.name !== "Unknown");

  // Build tab bar
  const tabsHtml = `
    <div class="profile-tabs" style="
      display:flex; gap:6px; padding:10px 12px 0;
      border-bottom:1px solid var(--border); flex-wrap:wrap;
    ">
      ${known.map((det, i) => `
        <button
          onclick="switchProfileTab(${detections.indexOf(det)})"
          style="
            padding:5px 12px; border-radius:6px 6px 0 0; border:none; cursor:pointer;
            font-family:var(--font); font-size:11px; font-weight:bold; letter-spacing:1px;
            background:${i === activeIdx ? 'var(--border2)' : 'transparent'};
            color:${i === activeIdx ? 'var(--accent)' : 'var(--dim)'};
            border-bottom: ${i === activeIdx ? '2px solid var(--accent)' : '2px solid transparent'};
          "
        >#${detections.indexOf(det) + 1} ${escHtml(det.name.split('_').join(' '))}</button>
      `).join("")}
    </div>`;

  const det = detections[activeIdx];

  if (!det || det.name === "Unknown") {
    card.innerHTML = tabsHtml;
    renderProfileUnknown();
    return;
  }

  // Set status badge from active person
  const status   = det.profile ? (det.profile.status || "") : "";
  const isActive = status.toLowerCase().includes("active") && !status.toLowerCase().includes("not");
  if (badge) {
    badge.textContent = known.length > 1
      ? `${known.length} SUBJECTS`
      : (isActive ? "⚠ ACTIVE" : "● INACTIVE");
    badge.style.color = known.length > 1 ? "var(--accent)" : (isActive ? "var(--danger)" : "var(--warning)");
  }

  const pct    = Math.round((det.display_pct || 0) * 100);
  const fillW  = Math.min(100, pct);
  const statusClr = isActive ? "var(--danger)" : "var(--warning)";

  const profile = det.profile || {
    name: det.name, date_of_birth: "N/A", date_of_death: "N/A",
    status: "No DB record", activities: []
  };

  const activitiesHtml = (profile.activities || []).map(act => `
    <div class="activity-item">
      <span class="activity-bullet">▸</span>
      <span class="activity-text">${escHtml(act)}</span>
    </div>`).join("");

  card.innerHTML = `
    ${tabsHtml}
    <div style="padding:12px">
      <div class="profile-name-banner">
        <div class="profile-name">${escHtml(profile.name)}</div>
        <div class="profile-conf">Match confidence: ${pct}%</div>
        <div class="conf-bar-wrap">
          <div class="conf-bar-fill" style="width:${fillW}%"></div>
        </div>
      </div>
    </div>

    <div class="profile-section-title">PERSONAL DETAILS</div>
    <div class="profile-field">
      <span class="profile-field-label">Date of Birth</span>
      <span class="profile-field-value">${escHtml(profile.date_of_birth || "N/A")}</span>
    </div>
    <div class="profile-field">
      <span class="profile-field-label">Date of Death</span>
      <span class="profile-field-value">${escHtml(profile.date_of_death || "N/A")}</span>
    </div>
    <div class="profile-field">
      <span class="profile-field-label">Status</span>
      <span class="profile-field-value" style="color:${statusClr}">${escHtml(profile.status || "")}</span>
    </div>

    ${activitiesHtml.length ? `
    <div class="profile-section-title">KEY ACTIVITIES</div>
    ${activitiesHtml}` : ""}

    <div style="height:16px"></div>`;
}

// Called by tab button onclick
function switchProfileTab(idx) {
  if (_currentDetections.length === 0) return;
  renderProfileTabs(_currentDetections, idx);
}

// ── Main entry point called by upload.js and webcam.js ───────────────────────
function renderDetections(detections, statEls) {
  const list  = document.getElementById("detectionList");
  const label = document.getElementById("faceCountLabel");

  if (!detections || detections.length === 0) {
    list.innerHTML = '<div class="text-dim text-sm" style="padding:8px 0">— No face detected</div>';
    if (label) label.textContent = "";
    renderProfileIdle();
    return;
  }

  if (label) {
    label.textContent = `${detections.length} FACE${detections.length > 1 ? "S" : ""} DETECTED`;
  }

  // Detection list (bottom-left)
  list.innerHTML = detections.map((det, i) => {
    const known = det.name !== "Unknown";
    const clr   = known ? "var(--success)" : "var(--danger)";
    const icon  = known ? "✔" : "✘";
    const pct   = Math.round((det.display_pct || 0) * 100);
    return `
      ${i > 0 ? '<div class="divider"></div>' : ""}
      <div class="detection-row">
        <span class="text-dim text-sm">#${i + 1}</span>
        <span class="detection-name" style="color:${clr}">${icon}  ${escHtml(det.name.split('_').join(' '))}</span>
        <span class="detection-pct" style="color:${clr}">${pct}%</span>
      </div>
      <div class="detection-bar">
        <div class="detection-fill" style="width:${pct}%;background:${clr}"></div>
      </div>`;
  }).join("");

  // Stats
  if (statEls) {
    const matched = detections.filter(d => d.name !== "Unknown").length;
    const unknown = detections.filter(d => d.name === "Unknown").length;
    if (statEls.matched) statEls.matched.textContent = parseInt(statEls.matched.textContent || 0) + matched;
    if (statEls.unknown) statEls.unknown.textContent = parseInt(statEls.unknown.textContent || 0) + unknown;
    if (statEls.total)   statEls.total.textContent   = parseInt(statEls.total.textContent   || 0) + 1;
  }

  // Profile panel (right)
  const knownFaces = detections.filter(d => d.name !== "Unknown");

  if (knownFaces.length === 0) {
    // All unknown
    renderProfileUnknown();
    return;
  }

  if (knownFaces.length === 1) {
    // Single known face — render directly, no tabs
    _currentDetections = [];
    const det = knownFaces[0];
    if (det.profile) {
      renderProfile(det.profile, det.display_pct);
    } else {
      renderProfile({
        name: det.name, date_of_birth: "N/A",
        date_of_death: "N/A", status: "No DB record", activities: []
      }, det.display_pct);
    }
    return;
  }

  // Multiple known faces — show tabs, default to first known
  _currentDetections = detections;
  const firstKnownIdx = detections.indexOf(knownFaces[0]);
  renderProfileTabs(detections, firstKnownIdx);
}

// ── Utility ───────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}