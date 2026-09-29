from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from src.indexing.bm25_index import search_bm25
from src.retrieval.dense_search import DenseSearcher
from src.retrieval.hybrid_search import fuse_rrf

DETAIL_FIELDS = [
    "query_id",
    "query",
    "method",
    "rank",
    "chunk_id",
    "doc_id",
    "title",
    "score",
    "bm25_rank",
    "dense_rank",
    "sources",
    "text_snippet",
]

SUMMARY_FIELDS = [
    "query_id",
    "query",
    "category",
    "bm25_hits_returned",
    "dense_hits_returned",
    "hybrid_hits_returned",
    "bm25_top1_chunk",
    "dense_top1_chunk",
    "hybrid_top1_chunk",
    "bm25_top1_title",
    "dense_top1_title",
    "hybrid_top1_title",
    "overlap_bm25_dense",
    "overlap_hybrid_bm25",
    "overlap_hybrid_dense",
    "bm25_latency_ms",
    "dense_latency_ms",
    "total_latency_ms",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lab 1.9: hybrid BM25 + dense retrieval with RRF"
    )

    parser.add_argument(
        "--queries",
        default="data/processed/lab1_8_queries.jsonl",
        help="JSONL file with 20 queries from Lab 1.8",
    )
    parser.add_argument(
        "--out",
        default="data/processed/lab1_9_hybrid_results.jsonl",
        help="Main JSONL output with BM25/dense/hybrid results",
    )
    parser.add_argument(
        "--report",
        default="data/processed/lab1_9_hybrid_report.json",
        help="JSON report with aggregate stats",
    )
    parser.add_argument(
        "--summary-csv",
        default="data/processed/lab1_9_comparison_summary.csv",
        help="One row per query, compact comparison table",
    )
    parser.add_argument(
        "--details-csv",
        default="data/processed/lab1_9_comparison_details.csv",
        help="Detailed top-k rows for BM25/dense/hybrid",
    )
    parser.add_argument(
        "--manual-template",
        default="data/processed/lab1_9_manual_template.csv",
        help="Template for manual relevance judgments",
    )
    parser.add_argument(
        "--log",
        default="data/processed/lab1_9_hybrid.log",
        help="Log file",
    )
    parser.add_argument(
        "--db",
        default=os.getenv(
            "DB_PATH",
            "data/processed/ru_wikipedia_5000_normalized.sqlite3",
        ),
        help="SQLite database path",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Primary retrieval depth for BM25 and dense",
    )
    parser.add_argument(
        "--eval-k",
        type=int,
        default=10,
        help="Top-k used for comparison tables and manual evaluation",
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=60,
        help="RRF smoothing parameter k",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="If > 0, process only first N queries. Useful for smoke test",
    )

    return parser.parse_args()


def get_field(obj: Any, name: str, default: Any = None) -> Any:
    """
    Универсально достаёт поле из dict / sqlite3.Row / dataclass / object.
    """
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(name, default)

    # Например, sqlite3.Row.
    if hasattr(obj, "keys"):
        try:
            return obj[name]
        except Exception:
            pass

    return getattr(obj, name, default)


def read_queries(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Queries file not found: {path}")

    queries: List[Dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            obj = json.loads(line)

            query_id = (
                obj.get("query_id")
                or obj.get("id")
                or obj.get("qid")
                or f"q{line_no:02d}"
            )

            query_text = (
                obj.get("query")
                or obj.get("text")
                or obj.get("question")
                or ""
            ).strip()

            category = obj.get("category") or obj.get("type") or ""

            if not query_text:
                raise ValueError(
                    f"Line {line_no}: cannot find query text. "
                    "Expected fields: query/text/question."
                )

            queries.append(
                {
                    "query_id": str(query_id),
                    "query": query_text,
                    "category": str(category),
                    "raw": obj,
                }
            )

    return queries


def load_titles(db_path: Path) -> Dict[str, str]:
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT doc_id, title FROM documents").fetchall()
        return {str(doc_id): str(title) for doc_id, title in rows}
    finally:
        conn.close()


def make_text_snippet(text: Optional[str], limit: int = 180) -> str:
    if not text:
        return ""
    normalized = " ".join(str(text).split())
    return normalized[:limit]


def hit_to_dict(
    item: Any,
    rank: int,
    titles: Dict[str, str],
) -> Dict[str, Any]:
    chunk_id = str(get_field(item, "chunk_id", "") or "")
    doc_id = str(get_field(item, "doc_id", "") or "")

    title = get_field(item, "title") or titles.get(doc_id, "")
    text = get_field(item, "text", "") or ""
    score = get_field(item, "score")

    try:
        score = float(score)
    except Exception:
        score = None

    return {
        "rank": rank,
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "title": str(title),
        "score": score,
        "text": str(text),
        "text_snippet": make_text_snippet(text),
    }


def unique_ids_from_hits(hits: List[Any]) -> List[str]:
    out: List[str] = []
    seen = set()

    for hit in hits:
        chunk_id = get_field(hit, "chunk_id")
        if not chunk_id:
            continue

        chunk_id = str(chunk_id)
        if chunk_id in seen:
            continue

        seen.add(chunk_id)
        out.append(chunk_id)

    return out


def make_id_map(hits: List[Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    for hit in hits:
        chunk_id = get_field(hit, "chunk_id")
        if not chunk_id:
            continue

        chunk_id = str(chunk_id)
        if chunk_id not in out:
            out[chunk_id] = hit

    return out


def to_hit_dicts(
    hits: List[Any],
    titles: Dict[str, str],
    limit: int,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    for rank, hit in enumerate(hits[:limit], start=1):
        out.append(hit_to_dict(hit, rank, titles))

    return out


def overlap_count(left: List[str], right: List[str], k: int) -> int:
    return len(set(left[:k]) & set(right[:k]))


def first_chunk_id(hits: List[Dict[str, Any]]) -> str:
    if not hits:
        return ""
    return hits[0].get("chunk_id", "")


def first_title(hits: List[Dict[str, Any]]) -> str:
    if not hits:
        return ""
    return hits[0].get("title", "")


def write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(
    path: Path,
    rows: List[Dict[str, Any]],
    fieldnames: List[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def avg(values: List[Optional[float]]) -> Optional[float]:
    cleaned = [float(v) for v in values if v is not None]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


def main() -> None:
    args = parse_args()
    load_dotenv()

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    queries_path = Path(args.queries)
    queries = read_queries(queries_path)

    if args.limit > 0:
        queries = queries[: args.limit]

    if not queries:
        raise RuntimeError("No queries to process")

    db_path = Path(args.db)
    titles = load_titles(db_path)

    logging.info("Initializing DenseSearcher...")
    searcher = DenseSearcher()

    records: List[Dict[str, Any]] = []
    detail_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []

    for query_meta in queries:
        query_id = query_meta["query_id"]
        query_text = query_meta["query"]
        category = query_meta["category"]

        logging.info("Processing query %s: %s", query_id, query_text)

        # ---------- BM25 ----------
        t0 = time.perf_counter()
        bm25_raw = search_bm25(query_text, top_k=args.top_k)
        bm25_elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # На случай, если реализация вдруг начнёт возвращать (hits, latency).
        if (
            isinstance(bm25_raw, tuple)
            and len(bm25_raw) == 2
            and isinstance(bm25_raw[0], list)
        ):
            bm25_hits, bm25_latency_ms = bm25_raw
            if bm25_latency_ms is None:
                bm25_latency_ms = bm25_elapsed_ms
        else:
            bm25_hits = bm25_raw
            bm25_latency_ms = bm25_elapsed_ms

        # ---------- Dense ----------
        t0 = time.perf_counter()
        dense_raw = searcher.search(query_text, top_k=args.top_k)
        dense_elapsed_ms = (time.perf_counter() - t0) * 1000.0

        if (
            isinstance(dense_raw, tuple)
            and len(dense_raw) == 2
            and isinstance(dense_raw[0], list)
        ):
            dense_hits, dense_latency_ms = dense_raw
            if dense_latency_ms is None:
                dense_latency_ms = dense_elapsed_ms
        else:
            dense_hits = dense_raw
            dense_latency_ms = dense_elapsed_ms

        # ---------- Подготовка идентификаторов ----------
        bm25_ids = unique_ids_from_hits(bm25_hits)[: args.top_k]
        dense_ids = unique_ids_from_hits(dense_hits)[: args.top_k]

        bm25_rank_by_id = {cid: idx + 1 for idx, cid in enumerate(bm25_ids)}
        dense_rank_by_id = {cid: idx + 1 for idx, cid in enumerate(dense_ids)}

        # ---------- RRF ----------
        fused_pairs = fuse_rrf(
            [bm25_ids, dense_ids],
            k=args.rrf_k,
            top_k=args.top_k,
        )

        hybrid_ids = [chunk_id for chunk_id, _ in fused_pairs]

        # ---------- Преобразование хитов в словари ----------
        bm25_dicts = to_hit_dicts(bm25_hits, titles, args.top_k)
        dense_dicts = to_hit_dicts(dense_hits, titles, args.top_k)

        bm25_map = make_id_map(bm25_hits)
        dense_map = make_id_map(dense_hits)

        hybrid_dicts: List[Dict[str, Any]] = []

        for fused_rank, (chunk_id, rrf_score) in enumerate(fused_pairs, start=1):
            base_hit = dense_map.get(chunk_id) or bm25_map.get(chunk_id)

            if base_hit is None:
                # Теоретически не должно случаться, потому что fused_ids
                # строятся из bm25_ids/dense_ids.
                continue

            hybrid_hit = hit_to_dict(base_hit, fused_rank, titles)
            hybrid_hit.update(
                {
                    "rrf_score": rrf_score,
                    "bm25_rank": bm25_rank_by_id.get(chunk_id),
                    "dense_rank": dense_rank_by_id.get(chunk_id),
                    "sources": [
                        source
                        for source, present in [
                            ("bm25", chunk_id in bm25_rank_by_id),
                            ("dense", chunk_id in dense_rank_by_id),
                        ]
                        if present
                    ],
                }
            )

            hybrid_dicts.append(hybrid_hit)

        # ---------- Overlaps ----------
        overlap_bm25_dense = overlap_count(bm25_ids, dense_ids, args.eval_k)
        overlap_hybrid_bm25 = overlap_count(hybrid_ids, bm25_ids, args.eval_k)
        overlap_hybrid_dense = overlap_count(hybrid_ids, dense_ids, args.eval_k)

        total_latency_ms = float(bm25_latency_ms or 0.0) + float(
            dense_latency_ms or 0.0
        )

        # ---------- Основной JSONL ----------
        record = {
            "query_id": query_id,
            "query": query_text,
            "category": category,
            "params": {
                "top_k": args.top_k,
                "eval_k": args.eval_k,
                "rrf_k": args.rrf_k,
            },
            "bm25_top_k": bm25_dicts,
            "dense_top_k": dense_dicts,
            "hybrid_top_k": hybrid_dicts,
            "overlaps": {
                "bm25_dense": overlap_bm25_dense,
                "hybrid_bm25": overlap_hybrid_bm25,
                "hybrid_dense": overlap_hybrid_dense,
                "eval_k": args.eval_k,
            },
            "latency_ms": {
                "bm25": bm25_latency_ms,
                "dense": dense_latency_ms,
                "total": total_latency_ms,
            },
        }

        records.append(record)

        # ---------- Детальные строки топ-10 ----------
        def add_detail_rows(
            method: str,
            hits: List[Dict[str, Any]],
        ) -> None:
            for hit in hits[: args.eval_k]:
                if method == "hybrid":
                    score = hit.get("rrf_score", hit.get("score"))
                    bm25_rank = hit.get("bm25_rank", "")
                    dense_rank = hit.get("dense_rank", "")
                    sources = ",".join(hit.get("sources", []))
                else:
                    score = hit.get("score")
                    bm25_rank = hit["rank"] if method == "bm25" else ""
                    dense_rank = hit["rank"] if method == "dense" else ""
                    sources = method

                detail_rows.append(
                    {
                        "query_id": query_id,
                        "query": query_text,
                        "method": method,
                        "rank": hit["rank"],
                        "chunk_id": hit["chunk_id"],
                        "doc_id": hit["doc_id"],
                        "title": hit["title"],
                        "score": score,
                        "bm25_rank": bm25_rank,
                        "dense_rank": dense_rank,
                        "sources": sources,
                        "text_snippet": hit.get("text_snippet", ""),
                    }
                )

        add_detail_rows("bm25", bm25_dicts)
        add_detail_rows("dense", dense_dicts)
        add_detail_rows("hybrid", hybrid_dicts)

        # ---------- Краткая сводка ----------
        summary_rows.append(
            {
                "query_id": query_id,
                "query": query_text,
                "category": category,
                "bm25_hits_returned": len(bm25_dicts),
                "dense_hits_returned": len(dense_dicts),
                "hybrid_hits_returned": len(hybrid_dicts),
                "bm25_top1_chunk": first_chunk_id(bm25_dicts),
                "dense_top1_chunk": first_chunk_id(dense_dicts),
                "hybrid_top1_chunk": first_chunk_id(hybrid_dicts),
                "bm25_top1_title": first_title(bm25_dicts),
                "dense_top1_title": first_title(dense_dicts),
                "hybrid_top1_title": first_title(hybrid_dicts),
                "overlap_bm25_dense": overlap_bm25_dense,
                "overlap_hybrid_bm25": overlap_hybrid_bm25,
                "overlap_hybrid_dense": overlap_hybrid_dense,
                "bm25_latency_ms": bm25_latency_ms,
                "dense_latency_ms": dense_latency_ms,
                "total_latency_ms": total_latency_ms,
            }
        )

    # ---------- Запись артефактов ----------
    write_jsonl(Path(args.out), records)
    write_csv(Path(args.summary_csv), summary_rows, SUMMARY_FIELDS)
    write_csv(Path(args.details_csv), detail_rows, DETAIL_FIELDS)

    manual_rows = [{**row, "relevance": ""} for row in detail_rows]
    manual_fields = DETAIL_FIELDS + ["relevance"]
    write_csv(Path(args.manual_template), manual_rows, manual_fields)

    report = {
        "lab": "1.9",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "params": {
            "queries_file": str(Path(args.queries).resolve()),
            "db_path": str(Path(args.db).resolve()),
            "top_k": args.top_k,
            "eval_k": args.eval_k,
            "rrf_k": args.rrf_k,
            "limit": args.limit,
        },
        "queries_total": len(records),
        "outputs": {
            "results_jsonl": str(Path(args.out).resolve()),
            "summary_csv": str(Path(args.summary_csv).resolve()),
            "details_csv": str(Path(args.details_csv).resolve()),
            "manual_template": str(Path(args.manual_template).resolve()),
            "log": str(Path(args.log).resolve()),
        },
        "avg_overlaps": {
            "bm25_dense": avg([r["overlaps"]["bm25_dense"] for r in records]),
            "hybrid_bm25": avg([r["overlaps"]["hybrid_bm25"] for r in records]),
            "hybrid_dense": avg([r["overlaps"]["hybrid_dense"] for r in records]),
        },
        "avg_latency_ms": {
            "bm25": avg([r["latency_ms"]["bm25"] for r in records]),
            "dense": avg([r["latency_ms"]["dense"] for r in records]),
            "total": avg([r["latency_ms"]["total"] for r in records]),
        },
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logging.info("Done")
    logging.info("Queries processed: %d", len(records))
    logging.info("Results JSONL: %s", args.out)
    logging.info("Summary CSV: %s", args.summary_csv)
    logging.info("Details CSV: %s", args.details_csv)
    logging.info("Manual template: %s", args.manual_template)
    logging.info("Report: %s", args.report)


if __name__ == "__main__":
    main()