"""Build BM25/FTS5 index for Lab 1.7."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.indexing.bm25_index import build_bm25_index, fts5_available

REPORT_PATH = Path("data/processed/lab1_7_bm25_report.json")
LOG_PATH = Path("data/processed/lab1_7_bm25.log")


def main() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    if not fts5_available():
        raise SystemExit("FTS5 is unavailable. Use the rank-bm25 fallback.")

    logging.info("Starting BM25/FTS5 index build")

    report = build_bm25_index()
    report["built_at"] = datetime.now(timezone.utc).isoformat()

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logging.info("BM25 index built: %s", report)


if __name__ == "__main__":
    main()