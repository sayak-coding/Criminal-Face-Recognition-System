"""
face_engine.py
--------------
Wraps DeepFace ArcFace recognition for use in Flask routes.
Mirrors logic from recognize.py and create_db.py exactly.
"""

import pickle
import sqlite3
import numpy as np
from pathlib import Path
from flask import current_app

MODEL_NAME = "ArcFace"
DETECTOR   = "retinaface"
THRESHOLD    = 0.42   # lowered from 0.50 — webcam compressed/resized frames score lower
DISPLAY_LOW  = 0.42   # remap starts here (0% bar)
DISPLAY_HIGH = 0.85   # remap ends here  (100% bar)

_database = None   # list of {name, embedding} dicts — loaded once


# ─────────────────────────────────────────
#  LOAD / RELOAD EMBEDDINGS
# ─────────────────────────────────────────
def load_database(force=False):
    global _database
    if _database is not None and not force:
        return _database

    db_path = Path(current_app.config["FACE_DB_PATH"])
    if not db_path.exists():
        _database = []
        return _database

    with open(db_path, "rb") as f:
        _database = pickle.load(f)

    current_app.logger.info(f"✅  Loaded {len(_database)} embeddings from {db_path}")
    return _database


# ─────────────────────────────────────────
#  COSINE MATCH  (dot product on L2-normalised embeddings)
# ─────────────────────────────────────────
def find_match(embedding, database):
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

    display_pct = _remap_confidence(best_score)
    return str(identity), display_pct


def _remap_confidence(raw: float) -> float:
    pct = (raw - DISPLAY_LOW) / (DISPLAY_HIGH - DISPLAY_LOW)
    return round(max(0.0, min(1.0, pct)), 4)


# ─────────────────────────────────────────
#  PROCESS A SINGLE IMAGE (numpy BGR or file path)
# ─────────────────────────────────────────
def process_image(img_input):
    """
    img_input: numpy BGR array or str/Path to image file.
    Returns list of detection dicts:
      { name, display_pct, x, y, w, h }
    """
    from deepface import DeepFace

    database = load_database()
    if not database:
        return []

    raw = DeepFace.represent(
        img_path          = img_input,
        model_name        = MODEL_NAME,
        detector_backend  = DETECTOR,
        enforce_detection = False,
        align             = True,
    )

    detections = []
    for res in raw:
        # Lowered from 0.80 → 0.65 — webcam compressed frames score lower
        if res.get("face_confidence", 1.0) < 0.65:
            continue

        name, display_pct = find_match(res["embedding"], database)
        area = res.get("facial_area", {})

        detections.append({
            "name"       : name,
            "display_pct": display_pct,
            "x"          : area.get("x", 0),
            "y"          : area.get("y", 0),
            "w"          : area.get("w", 0),
            "h"          : area.get("h", 0),
        })

    return detections


# ─────────────────────────────────────────
#  SQLITE HELPERS  (mirrors gui_app.py's get_person_info)
# ─────────────────────────────────────────
def get_person_info(name: str) -> dict | None:
    sqlite_path = current_app.config["TERRORIST_DB_PATH"]
    try:
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 1. Exact match (case-insensitive)
        cur.execute("SELECT * FROM persons WHERE name = ? COLLATE NOCASE", (name,))
        row = cur.fetchone()

        # 2. Underscore/hyphen → space fallback
        #    Handles embeddings stored as folder names e.g. "osama_bin_laden"
        if not row:
            normalised = name.replace("_", " ").replace("-", " ").strip()
            cur.execute("SELECT * FROM persons WHERE name = ? COLLATE NOCASE", (normalised,))
            row = cur.fetchone()

        # 3. Substring fallback — match first significant word
        if not row:
            words = [w for w in normalised.split() if len(w) > 2]
            for word in words:
                cur.execute(
                    "SELECT * FROM persons WHERE name LIKE ? COLLATE NOCASE",
                    (f"%{word}%",)
                )
                row = cur.fetchone()
                if row:
                    break

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
            "id"           : row["id"],
            "name"         : row["name"],
            "date_of_birth": row["date_of_birth"] or "N/A",
            "date_of_death": row["date_of_death"] or "N/A",
            "status"       : row["status"] or "Unknown",
            "activities"   : activities,
        }
    except Exception as e:
        current_app.logger.error(f"SQLite error: {e}")
        return None


def get_all_persons() -> list:
    sqlite_path = current_app.config["TERRORIST_DB_PATH"]
    try:
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM persons ORDER BY name")
        rows = cur.fetchall()
        persons = []
        for row in rows:
            cur.execute(
                "SELECT activity FROM activities WHERE person_id = ? ORDER BY id",
                (row["id"],)
            )
            activities = [r["activity"] for r in cur.fetchall()]
            persons.append({
                "id"           : row["id"],
                "name"         : row["name"],
                "date_of_birth": row["date_of_birth"] or "",
                "date_of_death": row["date_of_death"] or "",
                "status"       : row["status"] or "",
                "activities"   : activities,
                "created_at"   : row["created_at"],
            })
        conn.close()
        return persons
    except Exception as e:
        current_app.logger.error(f"SQLite error: {e}")
        return []


def add_person(name, dob, dod, status, activities: list) -> bool:
    sqlite_path = current_app.config["TERRORIST_DB_PATH"]
    try:
        conn = sqlite3.connect(sqlite_path)
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO persons (name, date_of_birth, date_of_death, status) VALUES (?,?,?,?)",
            (name, dob or None, dod or None, status)
        )
        person_id = cur.lastrowid
        for act in activities:
            act = act.strip()
            if act:
                cur.execute(
                    "INSERT INTO activities (person_id, activity) VALUES (?,?)",
                    (person_id, act)
                )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        current_app.logger.error(f"add_person error: {e}")
        return False


def update_person(person_id, name, dob, dod, status, activities: list) -> bool:
    sqlite_path = current_app.config["TERRORIST_DB_PATH"]
    try:
        conn = sqlite3.connect(sqlite_path)
        cur  = conn.cursor()
        cur.execute(
            "UPDATE persons SET name=?, date_of_birth=?, date_of_death=?, status=? WHERE id=?",
            (name, dob or None, dod or None, status, person_id)
        )
        cur.execute("DELETE FROM activities WHERE person_id=?", (person_id,))
        for act in activities:
            act = act.strip()
            if act:
                cur.execute(
                    "INSERT INTO activities (person_id, activity) VALUES (?,?)",
                    (person_id, act)
                )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        current_app.logger.error(f"update_person error: {e}")
        return False


def delete_person(person_id) -> bool:
    sqlite_path = current_app.config["TERRORIST_DB_PATH"]
    try:
        conn = sqlite3.connect(sqlite_path)
        cur  = conn.cursor()
        cur.execute("DELETE FROM activities WHERE person_id=?", (person_id,))
        cur.execute("DELETE FROM persons WHERE id=?", (person_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        current_app.logger.error(f"delete_person error: {e}")
        return False