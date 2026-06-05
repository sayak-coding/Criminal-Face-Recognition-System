"""
validate_dataset.py
───────────────────
Scans the downloaded face dataset and:
  1. Removes corrupt / non-image files
  2. Detects faces using OpenCV Haar Cascade
  3. Crops & saves face regions (optional)
  4. Prints a per-person quality report

Requirements:
    pip install opencv-python Pillow tqdm
"""

import os
import sys
import argparse
import logging
from pathlib import Path

try:
    import cv2
except ImportError:
    sys.exit("opencv-python not found. Run: pip install opencv-python")

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:
    sys.exit("Pillow not found. Run: pip install Pillow")

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # graceful fallback


log = logging.getLogger("validator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"}

# OpenCV ships with a frontal-face cascade
CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(CASCADE_PATH)


# ── Helpers ──────────────────────────────────────────────────────────────────
def is_valid_image(path: Path) -> bool:
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except (UnidentifiedImageError, Exception):
        return False


def detect_faces(path: Path) -> list[tuple[int, int, int, int]]:
    """Return list of (x, y, w, h) bounding boxes for detected faces."""
    img = cv2.imread(str(path))
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(60, 60),
    )
    return list(faces) if len(faces) else []


def crop_face(src: Path, dest_dir: Path, boxes: list, padding: float = 0.2):
    """Crop the largest detected face and save to dest_dir."""
    img = cv2.imread(str(src))
    h_img, w_img = img.shape[:2]

    # Pick largest face
    x, y, w, h = max(boxes, key=lambda b: b[2] * b[3])

    # Add padding
    pad_x = int(w * padding)
    pad_y = int(h * padding)
    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(w_img, x + w + pad_x)
    y2 = min(h_img, y + h + pad_y)

    face_crop = img[y1:y2, x1:x2]
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / src.name
    cv2.imwrite(str(out_path), face_crop)


# ── Main Validation Loop ─────────────────────────────────────────────────────
def validate_dataset(
    dataset_dir: Path,
    crop_output: Path | None = None,
    remove_no_face: bool = False,
):
    person_dirs = [d for d in dataset_dir.iterdir() if d.is_dir()]
    if not person_dirs:
        log.error("No person subdirectories found in %s", dataset_dir)
        return

    summary = []

    for person_dir in sorted(person_dirs):
        name = person_dir.name
        files = [f for f in person_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS]

        total = len(files)
        corrupt = 0
        no_face = 0
        with_face = 0

        iterator = tqdm(files, desc=name, unit="img") if tqdm else files

        for img_path in iterator:
            # 1. Validate image integrity
            if not is_valid_image(img_path):
                corrupt += 1
                img_path.unlink(missing_ok=True)
                continue

            # 2. Detect faces
            boxes = detect_faces(img_path)
            if not boxes:
                no_face += 1
                if remove_no_face:
                    img_path.unlink(missing_ok=True)
            else:
                with_face += 1
                if crop_output:
                    crop_dir = crop_output / name
                    crop_face(img_path, crop_dir, boxes)

        summary.append({
            "name": name,
            "total": total,
            "corrupt": corrupt,
            "no_face": no_face,
            "with_face": with_face,
        })

    # ── Report ────────────────────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print(f"{'PERSON':<28} {'TOTAL':>6} {'CORRUPT':>8} {'NO FACE':>8} {'WITH FACE':>10}")
    print("─" * 70)
    for r in summary:
        pct = (r["with_face"] / r["total"] * 100) if r["total"] else 0
        print(
            f"{r['name']:<28} {r['total']:>6} {r['corrupt']:>8} "
            f"{r['no_face']:>8} {r['with_face']:>9} ({pct:.0f}%)"
        )
    print("═" * 70)

    grand_total = sum(r["total"] for r in summary)
    grand_faces = sum(r["with_face"] for r in summary)
    print(f"  Grand total images : {grand_total}")
    print(f"  Images with faces  : {grand_faces}")
    if crop_output:
        print(f"  Cropped faces saved: {crop_output.resolve()}")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate & QC a face image dataset.")
    parser.add_argument("dataset", type=Path, help="Root dataset directory (e.g. face_dataset/)")
    parser.add_argument("--crop-output", "-c", type=Path, default=None,
                        help="Directory to save cropped face images.")
    parser.add_argument("--remove-no-face", action="store_true",
                        help="Delete images where no face was detected.")
    args = parser.parse_args()

    validate_dataset(
        dataset_dir=args.dataset,
        crop_output=args.crop_output,
        remove_no_face=args.remove_no_face,
    )