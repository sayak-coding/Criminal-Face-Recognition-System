import threading
import pickle
import sqlite3
import numpy as np
import cv2
import time
from PIL import Image, ImageDraw
from tkinter import filedialog
import customtkinter as ctk
from deepface import DeepFace

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
FACE_DB_PATH   = "face_db.pkl"
SQLITE_PATH    = "terrorist.db"
MODEL_NAME     = "ArcFace"
DETECTOR       = "retinaface"
THRESHOLD      = 0.50
PROCESS_EVERY  = 5
DISPLAY_LOW    = THRESHOLD
DISPLAY_HIGH   = 0.85

# ─────────────────────────────────────────
#  PALETTE
# ─────────────────────────────────────────
BG        = "#0a0e1a"
PANEL     = "#0f1528"
PANEL2    = "#111827"
ACCENT    = "#00d4ff"
ACCENT2   = "#7b2fff"
SUCCESS   = "#00ff9d"
DANGER    = "#ff3c5a"
WARNING   = "#ffaa00"
TEXT_DIM  = "#4a5a7a"
TEXT      = "#c8d8f0"
BORDER    = "#1e2a45"
BORDER2   = "#243050"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─────────────────────────────────────────
#  LOAD FACE EMBEDDINGS
# ─────────────────────────────────────────
try:
    with open(FACE_DB_PATH, "rb") as f:
        database = pickle.load(f)
    print(f"✅  Loaded {len(database)} embeddings from {FACE_DB_PATH}")
except FileNotFoundError:
    print(f"❌  {FACE_DB_PATH} not found. Run create_db.py first.")
    exit()


# ─────────────────────────────────────────
#  SQLITE HELPERS
# ─────────────────────────────────────────
def get_person_info(name: str) -> dict | None:
    """Fetch person details + activities from SQLite by name."""
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM persons WHERE name = ? COLLATE NOCASE", (name,))
        row = cur.fetchone()

        if not row:
            conn.close()
            return None

        cur.execute(
            "SELECT activity FROM activities WHERE person_id = ? ORDER BY id",
            (row["id"],)
        )
        activities = [r["activity"] for r in cur.fetchall()]
        conn.close()

        return {
            "name"          : row["name"],
            "date_of_birth" : row["date_of_birth"] or "N/A",
            "date_of_death" : row["date_of_death"] or "N/A",
            "status"        : row["status"] or "Unknown",
            "activities"    : activities,
        }
    except Exception as e:
        print(f"SQLite error: {e}")
        return None


# ─────────────────────────────────────────
#  CONFIDENCE REMAP
# ─────────────────────────────────────────
def remap_confidence(raw: float) -> float:
    pct = (raw - DISPLAY_LOW) / (DISPLAY_HIGH - DISPLAY_LOW)
    return max(0.0, min(1.0, pct))


# ─────────────────────────────────────────
#  COSINE MATCH
# ─────────────────────────────────────────
def find_match(embedding):
    emb = np.array(embedding, dtype=np.float32)
    emb = emb / (np.linalg.norm(emb) + 1e-10)

    best_score = -1.0
    identity   = "Unknown"

    for data in database:
        score = float(np.dot(emb, data["embedding"]))
        if score > best_score:
            best_score = score
            identity   = data["name"]

    if best_score < THRESHOLD:
        return "Unknown", 0.0

    return str(identity), remap_confidence(best_score)


# ─────────────────────────────────────────
#  DRAW ON FRAME
# ─────────────────────────────────────────
def draw_detections(frame, detections):
    for det in detections:
        x, y, w, h = det["x"], det["y"], det["w"], det["h"]
        name       = det["name"]
        disp_pct   = det["display_pct"]
        known      = name != "Unknown"
        color      = (0, 255, 157) if known else (255, 60, 90)

        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        c = 14
        for cx, cy, dx, dy in [(x,y,1,1),(x+w,y,-1,1),(x,y+h,1,-1),(x+w,y+h,-1,-1)]:
            cv2.line(frame, (cx, cy), (cx + dx*c, cy), color, 3)
            cv2.line(frame, (cx, cy), (cx, cy + dy*c), color, 3)

        label = f"{name}  {disp_pct*100:.1f}%"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        cv2.rectangle(frame, (x, y - th - 16), (x + tw + 12, y), (10, 14, 30), -1)
        cv2.putText(frame, label, (x + 6, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
    return frame


# ─────────────────────────────────────────
#  PLACEHOLDER
# ─────────────────────────────────────────
def make_placeholder(w=680, h=400):
    img  = Image.new("RGB", (w, h), color=(10, 14, 26))
    draw = ImageDraw.Draw(img)
    for i in range(0, w, 40):
        draw.line([(i, 0), (i, h)], fill=(20, 30, 55), width=1)
    for j in range(0, h, 40):
        draw.line([(0, j), (w, j)], fill=(20, 30, 55), width=1)
    cx, cy, r = w//2, h//2, 55
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(0, 212, 255), width=1)
    draw.line([(cx-r-20, cy), (cx+r+20, cy)], fill=(0, 212, 255), width=1)
    draw.line([(cx, cy-r-20), (cx, cy+r+20)], fill=(0, 212, 255), width=1)
    return img


# ─────────────────────────────────────────
#  APP
# ─────────────────────────────────────────
class FaceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FaceID  ·  Recognition System")
        self.geometry("1920x1080")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self._cap            = None
        self._cam_running    = False
        self._last_dets      = []
        self._current_frame  = None
        self._stats          = {"matched": 0, "unknown": 0, "fps": 0}
        self._last_fps_time  = time.time()
        self._fps_frames     = 0
        self._last_shown_names = set()   # avoid redrawing profile on same face

        self._build_ui()
        self._show_placeholder()

    # ────────────────────────────────────
    #  BUILD UI
    # ────────────────────────────────────
    def _build_ui(self):

        # ── Header ──
        header = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="  ◈  FACE RECOGNITION SYSTEM",
            font=ctk.CTkFont("Courier", 18, "bold"), text_color=ACCENT
        ).pack(side="left", padx=24, pady=18)

        self.status_dot = ctk.CTkLabel(
            header, text="● IDLE",
            font=ctk.CTkFont("Courier", 12), text_color=TEXT_DIM
        )
        self.status_dot.pack(side="right", padx=24)

        ctk.CTkLabel(
            header,
            text=f"MODEL: {MODEL_NAME}   DB: {len(database)} EMBEDDINGS",
            font=ctk.CTkFont("Courier", 11), text_color=TEXT_DIM
        ).pack(side="right", padx=20)

        # ── Body ──
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)

        # ── LEFT COLUMN (camera + detection result) ──
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        # Image panel
        img_border = ctk.CTkFrame(left, fg_color=BORDER, corner_radius=10)
        img_border.pack(fill="x", pady=(0, 10))

        self.image_label = ctk.CTkLabel(
            img_border, text="", width=680, height=400,
            corner_radius=8, fg_color=PANEL
        )
        self.image_label.pack(padx=2, pady=2)

        # Detection result card
        result_card = ctk.CTkFrame(left, fg_color=PANEL, corner_radius=10)
        result_card.pack(fill="x", pady=(0, 8))

        hrow = ctk.CTkFrame(result_card, fg_color="transparent")
        hrow.pack(fill="x", padx=16, pady=(10, 6))

        ctk.CTkLabel(
            hrow, text="DETECTION RESULT",
            font=ctk.CTkFont("Courier", 10), text_color=TEXT_DIM
        ).pack(side="left")

        self.face_count_label = ctk.CTkLabel(
            hrow, text="",
            font=ctk.CTkFont("Courier", 10), text_color=ACCENT
        )
        self.face_count_label.pack(side="right")

        self.faces_panel = ctk.CTkFrame(result_card, fg_color="transparent")
        self.faces_panel.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkLabel(
            self.faces_panel, text="—  No detection yet",
            font=ctk.CTkFont("Courier", 17, "bold"), text_color=TEXT
        ).pack(anchor="w", pady=4)

        # Controls row (under result card)
        ctrl_row = ctk.CTkFrame(left, fg_color="transparent")
        ctrl_row.pack(fill="x", pady=(0, 4))

        self.upload_btn = ctk.CTkButton(
            ctrl_row, text="📂  Upload Image",
            command=self.upload_image, height=42, corner_radius=8,
            fg_color=ACCENT2, hover_color="#5a1fd0",
            font=ctk.CTkFont("Courier", 13, "bold"), text_color="white"
        )
        self.upload_btn.pack(side="left", padx=(0, 10))

        self.cam_btn = ctk.CTkButton(
            ctrl_row, text="📷  Start Camera",
            command=self.toggle_camera, height=42, corner_radius=8,
            fg_color="#0a3a5a", hover_color="#0d4d78",
            font=ctk.CTkFont("Courier", 13, "bold"), text_color=ACCENT
        )
        self.cam_btn.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            ctrl_row, text="⬜  Clear",
            command=self.clear_panel, height=42, corner_radius=8,
            fg_color=BORDER, hover_color="#2a3550",
            font=ctk.CTkFont("Courier", 11), text_color=TEXT_DIM
        ).pack(side="left")

        # Stats row
        stats_row = ctk.CTkFrame(left, fg_color=PANEL, corner_radius=8)
        stats_row.pack(fill="x", pady=(8, 0))

        self._stat_labels = {}
        for key, label, color in [
            ("matched", "MATCHED", SUCCESS),
            ("unknown", "UNKNOWN", DANGER),
            ("fps",     "FPS",     ACCENT),
        ]:
            cell = ctk.CTkFrame(stats_row, fg_color="transparent")
            cell.pack(side="left", expand=True, padx=10, pady=8)

            ctk.CTkLabel(
                cell, text=label,
                font=ctk.CTkFont("Courier", 9), text_color=TEXT_DIM
            ).pack()

            val = ctk.CTkLabel(
                cell, text="0",
                font=ctk.CTkFont("Courier", 20, "bold"), text_color=color
            )
            val.pack()
            self._stat_labels[key] = val

        # ── RIGHT COLUMN (profile card) ──
        right = ctk.CTkFrame(body, fg_color="transparent", width=380)
        right.pack(side="right", fill="y", padx=(16, 0))
        right.pack_propagate(False)

        # Profile card header
        prof_header = ctk.CTkFrame(right, fg_color=PANEL, corner_radius=10, height=48)
        prof_header.pack(fill="x", pady=(0, 8))
        prof_header.pack_propagate(False)

        ctk.CTkLabel(
            prof_header, text="SUBJECT PROFILE",
            font=ctk.CTkFont("Courier", 11, "bold"), text_color=ACCENT
        ).pack(side="left", padx=16, pady=14)

        self.profile_status_badge = ctk.CTkLabel(
            prof_header, text="NO MATCH",
            font=ctk.CTkFont("Courier", 10, "bold"),
            text_color=TEXT_DIM
        )
        self.profile_status_badge.pack(side="right", padx=16)

        # Scrollable profile body
        self.profile_scroll = ctk.CTkScrollableFrame(
            right, fg_color=PANEL2, corner_radius=10,
            scrollbar_button_color=BORDER2,
            scrollbar_button_hover_color=ACCENT
        )
        self.profile_scroll.pack(fill="both", expand=True)

        # Seed with idle state
        self._show_profile_idle()

    # ────────────────────────────────────
    #  PROFILE PANEL
    # ────────────────────────────────────
    def _clear_profile(self):
        for w in self.profile_scroll.winfo_children():
            w.destroy()

    def _show_profile_idle(self):
        self._clear_profile()
        self.profile_status_badge.configure(text="NO MATCH", text_color=TEXT_DIM)

        ctk.CTkLabel(
            self.profile_scroll,
            text="Awaiting recognition…",
            font=ctk.CTkFont("Courier", 13), text_color=TEXT_DIM
        ).pack(pady=40)

    def _show_profile_unknown(self):
        self._clear_profile()
        self.profile_status_badge.configure(text="UNKNOWN", text_color=DANGER)

        ctk.CTkLabel(
            self.profile_scroll,
            text="✘  Unknown Subject",
            font=ctk.CTkFont("Courier", 16, "bold"), text_color=DANGER
        ).pack(pady=(30, 8))

        ctk.CTkLabel(
            self.profile_scroll,
            text="No matching record found\nin the database.",
            font=ctk.CTkFont("Courier", 12), text_color=TEXT_DIM,
            justify="center"
        ).pack()

    def _show_profile(self, info: dict, confidence: float):
        """Render full profile card for a recognised person."""
        self._clear_profile()

        status       = info["status"]
        is_active    = "active" in status.lower() and "not" not in status.lower()
        status_color = DANGER if is_active else WARNING

        self.profile_status_badge.configure(
            text="⚠ ACTIVE" if is_active else "● INACTIVE",
            text_color=status_color
        )

        # ── Name banner ──
        name_frame = ctk.CTkFrame(
            self.profile_scroll, fg_color=BORDER2, corner_radius=8
        )
        name_frame.pack(fill="x", padx=10, pady=(12, 6))

        ctk.CTkLabel(
            name_frame, text=info["name"],
            font=ctk.CTkFont("Courier", 18, "bold"), text_color=TEXT
        ).pack(anchor="w", padx=14, pady=(10, 2))

        ctk.CTkLabel(
            name_frame, text=f"Match confidence: {confidence*100:.1f}%",
            font=ctk.CTkFont("Courier", 10), text_color=SUCCESS
        ).pack(anchor="w", padx=14)

        conf_bar = ctk.CTkProgressBar(
            name_frame, height=6, corner_radius=3,
            fg_color="#1a2035", progress_color=SUCCESS
        )
        conf_bar.pack(fill="x", padx=14, pady=(4, 12))
        conf_bar.set(confidence)

        # ── Details ──
        def _section(title):
            ctk.CTkLabel(
                self.profile_scroll, text=title,
                font=ctk.CTkFont("Courier", 9), text_color=TEXT_DIM
            ).pack(anchor="w", padx=14, pady=(10, 2))
            ctk.CTkFrame(
                self.profile_scroll, height=1, fg_color=BORDER2
            ).pack(fill="x", padx=10, pady=(0, 4))

        def _field(label, value, value_color=TEXT):
            row = ctk.CTkFrame(self.profile_scroll, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(
                row, text=f"{label}",
                font=ctk.CTkFont("Courier", 10), text_color=TEXT_DIM,
                width=110, anchor="w"
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=value,
                font=ctk.CTkFont("Courier", 11, "bold"), text_color=value_color,
                anchor="w", wraplength=200, justify="left"
            ).pack(side="left")

        _section("PERSONAL DETAILS")
        _field("Date of Birth",  info["date_of_birth"])
        _field("Date of Death",  info["date_of_death"])
        _field("Status",         info["status"], value_color=status_color)

        # ── Activities ──
        if info["activities"]:
            _section("KEY ACTIVITIES")

            for i, act in enumerate(info["activities"]):
                act_frame = ctk.CTkFrame(
                    self.profile_scroll, fg_color=BORDER, corner_radius=6
                )
                act_frame.pack(fill="x", padx=10, pady=3)

                bullet_row = ctk.CTkFrame(act_frame, fg_color="transparent")
                bullet_row.pack(fill="x", padx=10, pady=6)

                ctk.CTkLabel(
                    bullet_row,
                    text=f"▸",
                    font=ctk.CTkFont("Courier", 11), text_color=ACCENT,
                    width=16
                ).pack(side="left", anchor="n", pady=2)

                ctk.CTkLabel(
                    bullet_row,
                    text=act,
                    font=ctk.CTkFont("Courier", 10), text_color=TEXT,
                    wraplength=280, justify="left", anchor="w"
                ).pack(side="left", padx=(6, 0), fill="x")

        # Bottom padding
        ctk.CTkFrame(
            self.profile_scroll, height=16, fg_color="transparent"
        ).pack()

    # ────────────────────────────────────
    #  UPDATE FACES + PROFILE TOGETHER
    # ────────────────────────────────────
    def _update_detections(self, dets):
        """Update both the faces panel and the profile card."""
        self._update_faces_panel(dets)

        if not dets:
            self._show_profile_idle()
            return

        # Show profile for the first known face; fallback to unknown card
        primary = next((d for d in dets if d["name"] != "Unknown"), None)

        if primary:
            name = primary["name"]
            # Only re-query DB if the recognised name changed
            current_names = {d["name"] for d in dets if d["name"] != "Unknown"}
            if current_names != self._last_shown_names:
                self._last_shown_names = current_names
                info = get_person_info(name)
                if info:
                    self._show_profile(info, primary["display_pct"])
                else:
                    # Face matched embedding but no DB record
                    self._show_profile({
                        "name"         : name,
                        "date_of_birth": "N/A",
                        "date_of_death": "N/A",
                        "status"       : "No record in database",
                        "activities"   : [],
                    }, primary["display_pct"])
        else:
            if self._last_shown_names != {"__unknown__"}:
                self._last_shown_names = {"__unknown__"}
                self._show_profile_unknown()

    # ────────────────────────────────────
    #  FACES PANEL (bottom-left)
    # ────────────────────────────────────
    def _update_faces_panel(self, dets):
        for w in self.faces_panel.winfo_children():
            w.destroy()

        if not dets:
            ctk.CTkLabel(
                self.faces_panel, text="—  No face detected",
                font=ctk.CTkFont("Courier", 17, "bold"), text_color=TEXT_DIM
            ).pack(anchor="w", pady=4)
            self.face_count_label.configure(text="")
            return

        count = len(dets)
        self.face_count_label.configure(
            text=f"{count} FACE{'S' if count > 1 else ''} DETECTED"
        )

        for i, det in enumerate(dets):
            name     = det["name"]
            disp_pct = det["display_pct"]
            known    = name != "Unknown"
            color    = SUCCESS if known else DANGER
            icon     = "✔" if known else "✘"

            if i > 0:
                ctk.CTkFrame(self.faces_panel, height=1, fg_color=BORDER).pack(fill="x", pady=5)

            row = ctk.CTkFrame(self.faces_panel, fg_color="transparent")
            row.pack(fill="x", pady=(3, 0))

            ctk.CTkLabel(
                row, text=f"#{i+1}",
                font=ctk.CTkFont("Courier", 11), text_color=TEXT_DIM, width=28
            ).pack(side="left")

            ctk.CTkLabel(
                row, text=f"{icon}  {name}",
                font=ctk.CTkFont("Courier", 16, "bold"), text_color=color
            ).pack(side="left", padx=(4, 0))

            ctk.CTkLabel(
                row, text=f"{disp_pct*100:.1f}%",
                font=ctk.CTkFont("Courier", 14, "bold"), text_color=color
            ).pack(side="right")

            bar = ctk.CTkProgressBar(
                self.faces_panel, height=6, corner_radius=3,
                fg_color="#1a2035", progress_color=color
            )
            bar.pack(fill="x", pady=(3, 0))
            bar.set(disp_pct)

    # ────────────────────────────────────
    #  UPLOAD IMAGE
    # ────────────────────────────────────
    def upload_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")]
        )
        if not path:
            return

        self._set_status("PROCESSING", ACCENT)
        self.update()

        img = cv2.imread(path)
        if img is None:
            for w in self.faces_panel.winfo_children():
                w.destroy()
            ctk.CTkLabel(
                self.faces_panel, text="❌  Cannot read file",
                font=ctk.CTkFont("Courier", 15, "bold"), text_color=DANGER
            ).pack(anchor="w")
            return

        try:
            raw = DeepFace.represent(
                img_path          = img,
                model_name        = MODEL_NAME,
                detector_backend  = DETECTOR,
                enforce_detection = False,
                align             = True,
            )

            dets = []
            for res in raw:
                if res.get("face_confidence", 1.0) < 0.80:
                    continue
                name, disp_pct = find_match(res["embedding"])
                area = res.get("facial_area", {})
                dets.append({
                    "name"       : name,
                    "display_pct": disp_pct,
                    "x": area.get("x", 0),
                    "y": area.get("y", 0),
                    "w": area.get("w", 0),
                    "h": area.get("h", 0),
                })
                if name != "Unknown":
                    self._stats["matched"] += 1
                else:
                    self._stats["unknown"] += 1

            draw_detections(img, dets)
            self._update_detections(dets)
            self._update_stat_labels()
            self._set_status("IDLE", TEXT_DIM)

        except Exception as e:
            for w in self.faces_panel.winfo_children():
                w.destroy()
            ctk.CTkLabel(
                self.faces_panel, text=f"Error: {e}",
                font=ctk.CTkFont("Courier", 12), text_color=DANGER
            ).pack(anchor="w")
            self._set_status("ERROR", DANGER)

        self._show_cv2_frame(img)

    # ────────────────────────────────────
    #  CAMERA
    # ────────────────────────────────────
    def toggle_camera(self):
        if self._cam_running:
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        self._cap = cv2.VideoCapture(0)
        if not self._cap.isOpened():
            for w in self.faces_panel.winfo_children():
                w.destroy()
            ctk.CTkLabel(
                self.faces_panel, text="❌  Cannot open webcam",
                font=ctk.CTkFont("Courier", 15, "bold"), text_color=DANGER
            ).pack(anchor="w")
            return

        self._cam_running    = True
        self._last_dets      = []
        self._last_fps_time  = time.time()
        self._fps_frames     = 0
        self._last_shown_names = set()

        self.cam_btn.configure(
            text="⏹  Stop Camera",
            fg_color="#3a0a0a", hover_color="#5a1010", text_color=DANGER
        )
        self._set_status("LIVE", SUCCESS)
        threading.Thread(target=self._cam_worker, daemon=True).start()
        self._poll_camera()

    def _stop_camera(self):
        self._cam_running = False
        if self._cap:
            self._cap.release()
            self._cap = None
        self.cam_btn.configure(
            text="📷  Start Camera",
            fg_color="#0a3a5a", hover_color="#0d4d78", text_color=ACCENT
        )
        self._set_status("IDLE", TEXT_DIM)
        self._update_detections([])

    def _cam_worker(self):
        frame_idx = 0
        while self._cam_running and self._cap:
            ret, frame = self._cap.read()
            if not ret:
                break

            frame_idx          += 1
            self._current_frame = frame.copy()
            self._fps_frames   += 1

            if frame_idx % PROCESS_EVERY == 0:
                small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                try:
                    raw = DeepFace.represent(
                        img_path          = small,
                        model_name        = MODEL_NAME,
                        detector_backend  = DETECTOR,
                        enforce_detection = False,
                        align             = True,
                    )
                    dets = []
                    for res in raw:
                        if res.get("face_confidence", 1.0) < 0.80:
                            continue
                        name, disp_pct = find_match(res["embedding"])
                        area = res.get("facial_area", {})
                        dets.append({
                            "name"       : name,
                            "display_pct": disp_pct,
                            "x": area.get("x", 0) * 2,
                            "y": area.get("y", 0) * 2,
                            "w": area.get("w", 0) * 2,
                            "h": area.get("h", 0) * 2,
                        })
                    self._last_dets = dets
                except Exception:
                    pass

    def _poll_camera(self):
        if not self._cam_running:
            return

        frame = getattr(self, "_current_frame", None)
        if frame is not None:
            display = frame.copy()
            draw_detections(display, self._last_dets)
            self._show_cv2_frame(display)

            now = time.time()
            if now - self._last_fps_time >= 1.0:
                self._stats["fps"] = self._fps_frames
                self._fps_frames   = 0
                self._last_fps_time = now

            for det in self._last_dets:
                if det["name"] != "Unknown":
                    self._stats["matched"] += 1
                else:
                    self._stats["unknown"] += 1

            self._update_detections(self._last_dets)
            self._update_stat_labels()

        self.after(30, self._poll_camera)

    # ────────────────────────────────────
    #  HELPERS
    # ────────────────────────────────────
    def _show_cv2_frame(self, bgr):
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(680, 400))
        self.image_label.configure(image=img, text="")
        self.image_label._img = img

    def _show_placeholder(self):
        pil = make_placeholder(680, 400)
        img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(680, 400))
        self.image_label.configure(image=img, text="")
        self.image_label._img = img

    def _set_status(self, text, color):
        self.status_dot.configure(text=f"● {text}", text_color=color)

    def _update_stat_labels(self):
        for key, lbl in self._stat_labels.items():
            lbl.configure(text=str(self._stats[key]))

    def clear_panel(self):
        self._stop_camera()
        self._stats = {"matched": 0, "unknown": 0, "fps": 0}
        self._last_shown_names = set()
        self._update_stat_labels()
        self._update_faces_panel([])
        self._show_profile_idle()
        self._show_placeholder()

    def on_close(self):
        self._stop_camera()
        self.destroy()


# ─────────────────────────────────────────
#  ENTRY
# ─────────────────────────────────────────
if __name__ == "__main__":
    app = FaceApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()