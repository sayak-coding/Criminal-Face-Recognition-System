"""
Face Recognition Image Download Pipeline
Uses icrawler (Bing + Google + Baidu backends) — no API key needed.
Install: pip install icrawler
"""

import re
import time
import logging
import argparse
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


def download_for_person(name: str, output_root: Path, target: int = 50) -> int:
    """Download `target` face images for `name` using icrawler."""
    from icrawler.builtin import BingImageCrawler, GoogleImageCrawler

    safe_name = re.sub(r"[^\w\-]", "_", name.strip()).lower()
    person_dir = output_root / safe_name
    person_dir.mkdir(parents=True, exist_ok=True)

    query = f"{name} face portrait"
    saved = 0

    # ── Try Bing first ────────────────────────────────────────────────────────
    log.info("[%s] Trying Bing...", name)
    try:
        bing = BingImageCrawler(
            storage={"root_dir": str(person_dir)},
            feeder_threads=2,
            parser_threads=2,
            downloader_threads=6,
            log_level=logging.WARNING,
        )
        bing.crawl(
            keyword=query,
            max_num=target,
            min_size=(100, 100),
            file_idx_offset="auto",
        )
        saved = len(list(person_dir.glob("*.*")))
        log.info("[%s] Bing saved %d images", name, saved)
    except Exception as e:
        log.warning("[%s] Bing failed: %s", name, e)

    # ── Top up with Google if needed ──────────────────────────────────────────
    if saved < target:
        remaining = target - saved
        log.info("[%s] Topping up %d more via Google...", name, remaining)
        try:
            google = GoogleImageCrawler(
                storage={"root_dir": str(person_dir)},
                feeder_threads=2,
                parser_threads=2,
                downloader_threads=6,
                log_level=logging.WARNING,
            )
            google.crawl(
                keyword=query,
                max_num=remaining,
                min_size=(100, 100),
                file_idx_offset="auto",
            )
            saved = len(list(person_dir.glob("*.*")))
            log.info("[%s] After Google: %d images total", name, saved)
        except Exception as e:
            log.warning("[%s] Google failed: %s", name, e)

    log.info("[%s] ✓ Done — %d images → %s", name, saved, person_dir)
    return saved


def main():
    parser = argparse.ArgumentParser(
        description="Download face images for face recognition."
    )
    parser.add_argument("names", nargs="*", help="Person names (positional).")
    parser.add_argument("--names-file", "-f", type=Path, help="Text file, one name per line.")
    parser.add_argument("--output",    "-o", type=Path, default=Path("face_dataset"))
    parser.add_argument("--count",     "-n", type=int,  default=50)
    args = parser.parse_args()

    names = list(args.names)
    if args.names_file and args.names_file.exists():
        lines = args.names_file.read_text(encoding="utf-8").splitlines()
        names += [l.strip() for l in lines if l.strip()]

    if not names:
        parser.error("Provide at least one name via CLI or --names-file.")

    args.output.mkdir(parents=True, exist_ok=True)
    log.info("Pipeline start — %d person(s), %d images each", len(names), args.count)

    results = {}
    for name in names:
        count = download_for_person(name, args.output, args.count)
        results[name] = count
        time.sleep(1)

    print("\n" + "=" * 52)
    print(f"  {'PERSON':<30} {'IMAGES':>6}  STATUS")
    print("=" * 52)
    for name, cnt in results.items():
        status = "OK" if cnt >= args.count else f"only {cnt}"
        print(f"  {name:<30} {cnt:>6}  {status}")
    print("=" * 52)
    print(f"  Total : {sum(results.values())} images")
    print(f"  Saved : {args.output.resolve()}")


if __name__ == "__main__":
    main()