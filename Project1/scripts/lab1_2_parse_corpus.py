"""
Скрипт запускает парсер по всему корпусу:
- читает data/raw/ru_wikipedia_5000.jsonl;
- парсит документы;
- пишет успешные документы в data/processed/ru_wikipedia_5000_parsed.jsonl;
- пишет ошибки в data/processed/lab1_2_parse_errors.jsonl;
- пишет статистику в data/processed/lab1_2_parse_stats.json;
- пишет лог в data/processed/lab1_2_parse.log.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.parser import safe_parse  # noqa: E402


def configure_logging(log_path: Path) -> None:
    """
    Настраивает логирование в консоль и файл.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, mode="w", encoding="utf-8"),
        ],
    )


def to_document(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Преобразует результат parse() к виду, который удобно использовать дальше.

    parse() возвращает:
        {
            "text": "...",
            "metadata": {...}
        }

    Здесь мы приводим документ к схеме, близкой к Document Schema из проектного файла.
    """
    metadata = parsed["metadata"]

    return {
        "doc_id": metadata["doc_id"],
        "title": metadata["title"],
        "text": parsed["text"],
        "source": metadata["source"],
        "date": metadata["date"],
        "metadata": {
            **metadata.get("original_metadata", {}),
            "parser": metadata.get("parser", {}),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse raw JSONL corpus for Lab 1.2"
    )

    parser.add_argument(
        "--input",
        default="data/raw/ru_wikipedia_5000.jsonl",
        help="Входной файл с сырыми документами",
    )
    parser.add_argument(
        "--output",
        default="data/processed/ru_wikipedia_5000_parsed.jsonl",
        help="Выходной файл с распарсенными документами",
    )
    parser.add_argument(
        "--errors",
        default="data/processed/lab1_2_parse_errors.jsonl",
        help="Файл с ошибками парсинга",
    )
    parser.add_argument(
        "--stats",
        default="data/processed/lab1_2_parse_stats.json",
        help="Файл со статистикой",
    )
    parser.add_argument(
        "--log",
        default="data/processed/lab1_2_parse.log",
        help="Файл лога",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Обработать только первые N документов. 0 - обработать все.",
    )

    args = parser.parse_args()

    input_path = PROJECT_ROOT / args.input
    output_path = PROJECT_ROOT / args.output
    errors_path = PROJECT_ROOT / args.errors
    stats_path = PROJECT_ROOT / args.stats
    log_path = PROJECT_ROOT / args.log

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 1

    configure_logging(log_path)
    logger = logging.getLogger("project1.lab1_2.script")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    errors_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    ok = 0
    failed = 0
    skipped_empty = 0

    with (
        input_path.open("r", encoding="utf-8") as fin,
        output_path.open("w", encoding="utf-8") as fout,
        errors_path.open("w", encoding="utf-8") as ferr,
    ):
        for line_no, line in enumerate(fin, start=1):
            if args.limit and total >= args.limit:
                break

            line = line.strip()
            if not line:
                skipped_empty += 1
                continue

            total += 1

            parsed, error = safe_parse(line, line_no=line_no)

            if parsed is not None:
                doc = to_document(parsed)
                fout.write(json.dumps(doc, ensure_ascii=False) + "\n")
                ok += 1
            else:
                ferr.write(json.dumps(error, ensure_ascii=False) + "\n")
                failed += 1

    stats = {
        "lab": "1.2",
        "input": str(input_path.relative_to(PROJECT_ROOT)),
        "output": str(output_path.relative_to(PROJECT_ROOT)),
        "errors": str(errors_path.relative_to(PROJECT_ROOT)),
        "total_processed": total,
        "ok": ok,
        "failed": failed,
        "skipped_empty_lines": skipped_empty,
        "success_rate": round(ok / total, 4) if total else 0.0,
    }

    stats_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "Done. total=%s ok=%s failed=%s empty=%s",
        total,
        ok,
        failed,
        skipped_empty,
    )

    print(f"OK: {ok}, failed: {failed}, total: {total}")
    print(f"Stats: {stats_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())