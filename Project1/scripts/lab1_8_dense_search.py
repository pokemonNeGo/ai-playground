from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.dense_search import DenseSearcher

logger = logging.getLogger(__name__)


def read_queries(path: Path) -> list[dict]:
    queries = []

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Некорректный JSON в строке {line_number}: {line}") from exc

            if "text" not in obj and "query" in obj:
                obj["text"] = obj["query"]

            if "text" not in obj:
                raise ValueError(f"В строке {line_number} нет поля text/query")

            if "query_id" not in obj:
                obj["query_id"] = f"q{line_number:02d}"

            queries.append(obj)

    return queries


def hit_to_dict(hit) -> dict:
    """
    Убираем payload, чтобы не дублировать текст и не раздувать файл.
    """
    data = hit.to_dict()
    data.pop("payload", None)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Плотный поиск по Qdrant для Лабораторной 1.8"
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=None,
        help="Путь к JSONL-файлу с запросами",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Одиночный запрос для быстрой проверки",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/processed/lab1_8_dense_results.jsonl"),
        help="Куда сохранить результаты поиска",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/processed/lab1_8_dense_report.json"),
        help="Куда сохранить отчёт о запуске",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Сколько результатов возвращать на запрос",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Обработать только первые N запросов",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    if args.query:
        queries = [
            {
                "query_id": "cli_q01",
                "text": args.query,
                "category": "cli",
                "expected_answer": None,
            }
        ]
    elif args.queries:
        queries = read_queries(args.queries)
    else:
        parser.error("Нужно указать --queries или --query")

    if args.limit:
        queries = queries[: args.limit]

    if not queries:
        raise ValueError("Список запросов пуст")

    searcher = DenseSearcher()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    total_hits = 0
    total_latency_ms = 0.0

    with args.out.open("w", encoding="utf-8") as out_file:
        for query_obj in queries:
            query_id = query_obj.get("query_id")
            query_text = query_obj.get("text")
            category = query_obj.get("category")
            expected_answer = query_obj.get("expected_answer")

            hits, latency_ms = searcher.search(
                query=query_text,
                top_k=args.top_k,
            )

            record = {
                "query_id": query_id,
                "query": query_text,
                "category": category,
                "expected_answer": expected_answer,
                "top_k": args.top_k,
                "latency_ms": round(latency_ms, 2),
                "results": [hit_to_dict(hit) for hit in hits],
            }

            out_file.write(json.dumps(record, ensure_ascii=False) + "\n")

            total_hits += len(hits)
            total_latency_ms += latency_ms

            print()
            print(f"[{query_id}] {query_text!r}")
            print(f"category={category}, latency={latency_ms:.0f} ms, hits={len(hits)}")

            for hit in hits[:3]:
                preview = hit.text.replace("\n", " ")[:80]
                print(
                    f"  {hit.rank}. score={hit.score:.4f} "
                    f"title={hit.title!r} text={preview!r}"
                )

    report = {
        "lab": "1.8",
        "task": "dense_search",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "collection": searcher.collection,
        "embedding_model": os.getenv("EMBEDDING_MODEL", "models/bge-m3"),
        "top_k": args.top_k,
        "queries_count": len(queries),
        "total_hits": total_hits,
        "avg_latency_ms": round(total_latency_ms / len(queries), 2),
        "queries_file": str(args.queries) if args.queries else None,
        "results_file": str(args.out),
    }

    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print(f"Saved results: {args.out}")
    print(f"Saved report: {args.report}")


if __name__ == "__main__":
    main()