import base64
import threading
import cv2
import numpy as np
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from .. import socketio
from ..face_engine import process_image, get_person_info

recognize_bp = Blueprint("recognize", __name__)

# ─────────────────────────────────────────
#  Per-session frame queue + worker
#  One background thread per connected client.
#  Only the latest frame is kept — old frames
#  are dropped if DeepFace is still processing.
# ─────────────────────────────────────────
_sessions      = {}          # sid → {"frame": b64|None, "lock": Lock, "active": bool}
_sessions_lock = threading.Lock()


# ── Upload image page ─────────────────────────────────────────────────────────
@recognize_bp.route("/", methods=["GET"])
@recognize_bp.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("recognize/upload.html")


# ── Process uploaded image (AJAX POST) ───────────────────────────────────────
@recognize_bp.route("/process", methods=["POST"])
@login_required
def process():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    np_arr = np.frombuffer(file.read(), np.uint8)
    img    = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({"error": "Cannot decode image"}), 400

    try:
        detections = process_image(img)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    annotated = _draw_boxes(img.copy(), detections)
    _, buf    = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
    b64_image = base64.b64encode(buf).decode("utf-8")

    results = []
    for det in detections:
        entry = {
            "name"       : det["name"],
            "display_pct": det["display_pct"],
            "x": det["x"], "y": det["y"],
            "w": det["w"], "h": det["h"],
            "profile"    : None,
        }
        if det["name"] != "Unknown":
            entry["profile"] = get_person_info(det["name"])
        results.append(entry)

    return jsonify({"image": b64_image, "detections": results})


# ── Webcam page ───────────────────────────────────────────────────────────────
@recognize_bp.route("/webcam")
@login_required
def webcam():
    return render_template("recognize/webcam.html")


# ── SocketIO lifecycle ────────────────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
    sid = request.sid
    with _sessions_lock:
        _sessions[sid] = {"frame": None, "lock": threading.Lock(), "active": True}
    # Pass the Flask app so the worker thread can push an app context
    from flask import current_app
    app = current_app._get_current_object()
    t = threading.Thread(target=_worker, args=(sid, app), daemon=True)
    t.start()


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    with _sessions_lock:
        if sid in _sessions:
            _sessions[sid]["active"] = False
            del _sessions[sid]


# ── SocketIO — receive base64 frame ──────────────────────────────────────────
@socketio.on("frame")
def handle_frame(data):
    """
    Client sends a 0.5x scaled JPEG every N frames.
    We just store the latest — the background worker picks it up.
    Returns immediately so SocketIO ping loop is NEVER blocked.
    """
    sid = request.sid

    with _sessions_lock:
        session = _sessions.get(sid)
    if not session:
        return

    b64 = data.get("image", "")
    if "," in b64:
        b64 = b64.split(",")[1]

    # Drop any unprocessed frame — only keep the latest
    with session["lock"]:
        session["frame"] = b64


# ── Background worker — one per connected client ──────────────────────────────
def _worker(sid, app):
    """
    Runs in its own thread with a Flask app context so current_app works.
    Polls for new frames, runs DeepFace, emits results.
    """
    with app.app_context():
        while True:
            with _sessions_lock:
                session = _sessions.get(sid)
            if not session or not session["active"]:
                break

            # Grab latest frame
            with session["lock"]:
                b64 = session["frame"]
                session["frame"] = None

            if b64 is None:
                threading.Event().wait(0.05)
                continue

            try:
                img_bytes = base64.b64decode(b64)
                np_arr    = np.frombuffer(img_bytes, np.uint8)
                small     = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if small is None:
                    # Unblock client even on bad frame
                    socketio.emit("result", {"image": None, "detections": []}, to=sid)
                    continue

                detections = process_image(small)

                # Scale bounding boxes x2 to match full-res canvas
                scaled_dets = [{
                    **det,
                    "x": det["x"] * 2,
                    "y": det["y"] * 2,
                    "w": det["w"] * 2,
                    "h": det["h"] * 2,
                } for det in detections]

                full      = cv2.resize(small, (0, 0), fx=2.0, fy=2.0)
                annotated = _draw_boxes(full, scaled_dets)
                _, buf    = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
                b64_out   = base64.b64encode(buf).decode("utf-8")

                results = []
                for det in scaled_dets:
                    entry = {"name": det["name"], "display_pct": det["display_pct"]}
                    if det["name"] != "Unknown":
                        entry["profile"] = get_person_info(det["name"])
                    results.append(entry)

                socketio.emit("result", {"image": b64_out, "detections": results}, to=sid)

            except Exception as e:
                app.logger.error(f"Worker error for {sid}: {e}", exc_info=True)
                # Always emit so client resets processingFrame flag
                socketio.emit("result", {"image": None, "detections": [], "error": str(e)}, to=sid)


# ── Draw helper ───────────────────────────────────────────────────────────────
def _draw_boxes(frame, detections):
    for det in detections:
        x, y, w, h = det["x"], det["y"], det["w"], det["h"]
        name       = det["name"]
        pct        = det["display_pct"]
        known      = name != "Unknown"
        color      = (0, 255, 157) if known else (255, 60, 90)

        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        c = 14
        for cx, cy, dx, dy in [
            (x, y, 1, 1), (x + w, y, -1, 1),
            (x, y + h, 1, -1), (x + w, y + h, -1, -1)
        ]:
            cv2.line(frame, (cx, cy), (cx + dx * c, cy), color, 3)
            cv2.line(frame, (cx, cy), (cx, cy + dy * c), color, 3)

        label = f"{name}  {pct * 100:.1f}%"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        cv2.rectangle(frame, (x, y - th - 16), (x + tw + 12, y), (10, 14, 30), -1)
        cv2.putText(frame, label, (x + 6, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

    return frame