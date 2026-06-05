import os
import pickle
import numpy as np
from deepface import DeepFace

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
DATASET_PATH  = "cropped_faces"
DB_OUTPUT     = "face_db.pkl"
MODEL_NAME    = "ArcFace"
DETECTOR      = "retinaface"   # more accurate than default opencv


def build_database(dataset_path: str) -> list:
    database = []
    persons  = [p for p in os.listdir(dataset_path)
                if os.path.isdir(os.path.join(dataset_path, p))]

    print(f"Found {len(persons)} person(s): {persons}\n")

    for person_name in persons:
        person_folder = os.path.join(dataset_path, person_name)
        images        = [f for f in os.listdir(person_folder)
                         if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp"))]

        print(f"[{person_name}] Processing {len(images)} image(s)...")
        success = 0

        for img_name in images:
            img_path = os.path.join(person_folder, img_name)

            try:
                results = DeepFace.represent(
                    img_path        = img_path,
                    model_name      = MODEL_NAME,
                    detector_backend= DETECTOR,
                    enforce_detection= False,
                    align           = True,
                )

                for res in results:
                    # Skip if face confidence is too low
                    if res.get("face_confidence", 1.0) < 0.85:
                        continue

                    emb = np.array(res["embedding"], dtype=np.float32)

                    # L2-normalise so cosine sim == dot product later
                    emb = emb / (np.linalg.norm(emb) + 1e-10)

                    database.append({
                        "name"     : person_name,
                        "embedding": emb,
                    })
                    success += 1

            except Exception as e:
                print(f"  ⚠  Skipped {img_name}: {e}")

        print(f"  ✓  {success}/{len(images)} embeddings stored for '{person_name}'\n")

    return database


# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Building Face Embedding Database")
    print("=" * 50 + "\n")

    db = build_database(DATASET_PATH)

    with open(DB_OUTPUT, "wb") as f:
        pickle.dump(db, f)

    print(f"✅  Database saved → {DB_OUTPUT}  ({len(db)} embedding(s) total)")