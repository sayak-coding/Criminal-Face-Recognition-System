import cv2
import pickle
import numpy as np
from deepface import DeepFace

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
DB_PATH       = "face_db.pkl"
MODEL_NAME    = "ArcFace"
DETECTOR      = "retinaface"
THRESHOLD     = 0.50          # cosine similarity (0–1). Tune if needed.
PROCESS_EVERY = 5             # run DeepFace every N frames for speed


# ─────────────────────────────────────────
#  LOAD DATABASE
# ─────────────────────────────────────────
try:
    with open(DB_PATH, "rb") as f:
        database = pickle.load(f)
    print(f"✅  Loaded {len(database)} embedding(s) from {DB_PATH}")
except FileNotFoundError:
    print(f"❌  {DB_PATH} not found. Run create_db.py first.")
    exit()


# ─────────────────────────────────────────
#  MATCHING  (cosine similarity)
# ─────────────────────────────────────────
def find_match(embedding: np.ndarray, threshold: float = THRESHOLD):
    """
    Returns (name, confidence_score).
    Embeddings in DB are already L2-normalised, so dot product == cosine sim.
    """
    embedding = np.array(embedding, dtype=np.float32)
    embedding = embedding / (np.linalg.norm(embedding) + 1e-10)

    best_score = -1.0
    identity   = "Unknown"

    for data in database:
        score = float(np.dot(embedding, data["embedding"]))
        if score > best_score:
            best_score = score
            identity   = data["name"]

    if best_score < threshold:
        return "Unknown", best_score

    return str(identity), best_score


# ─────────────────────────────────────────
#  WEBCAM LOOP
# ─────────────────────────────────────────
def run_camera():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌  Cannot open webcam.")
        return

    print("🚀  Camera started — press ESC to quit\n")

    frame_idx   = 0
    last_results = []          # cache last detections between frames

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1

        # ── Run recognition every N frames ──
        if frame_idx % PROCESS_EVERY == 0:
            small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)

            try:
                raw = DeepFace.represent(
                    img_path         = small,
                    model_name       = MODEL_NAME,
                    detector_backend = DETECTOR,
                    enforce_detection= False,
                    align            = True,
                )

                last_results = []
                for res in raw:
                    if res.get("face_confidence", 1.0) < 0.80:
                        continue

                    name, score = find_match(res["embedding"])
                    area = res.get("facial_area", {})

                    last_results.append({
                        "name" : name,
                        "score": score,
                        "x"    : area.get("x", 0) * 2,
                        "y"    : area.get("y", 0) * 2,
                        "w"    : area.get("w", 0) * 2,
                        "h"    : area.get("h", 0) * 2,
                    })

            except Exception as e:
                print(f"Error: {e}")

        # ── Draw cached results on every frame ──
        for det in last_results:
            x, y, w, h = det["x"], det["y"], det["w"], det["h"]
            name, score = det["name"], det["score"]

            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
            label = f"{name}  {score*100:.1f}%"

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, label, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)

        # ── FPS overlay ──
        fps = cap.get(cv2.CAP_PROP_FPS)
        cv2.putText(frame, f"FPS: {int(fps)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2)

        cv2.imshow("Face Recognition  |  ESC = quit", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Camera closed.")


if __name__ == "__main__":
    run_camera()