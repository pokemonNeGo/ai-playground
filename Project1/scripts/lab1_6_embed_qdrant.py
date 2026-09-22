from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from tqdm import tqdm

from src.indexing.embeddings import (
    encode_batch,
    get_vector_size,
    load_embedding_model,
    uses_e5_prefix,
)
from src.indexing.qdrant_index import (
    build_points,
    ensure_collection,
    get_qdrant_client,
    recreate_collection,
)


ALLOWED_TABLES = {"chunks", "chunks_structural"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed chunks and upload them to Qdrant")

    parser.add_argument(
        "--db",
        default=os.getenv("DB_PATH", "data/processed/ru_wikipedia_5000_normalized.sqlite3"),
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--table",
        default=os.getenv("CHUNKS_TABLE", "chunks"),
        choices=sorted(ALLOWED_TABLES),
        help="Chunks table to embed",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
        help="Embedding model name",
    )
    parser.add_argument(
        "--device",
        default=os.getenv("EMBEDDING_DEVICE", ""),
        help="cpu, cuda or empty for auto",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
        help="Batch size for embedding and upload",
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("QDRANT_COLLECTION", "rag_documents"),
        help="Qdrant collection name",
    )
    parser.add_argument(
        "--qdrant-mode",
        default=os.getenv("QDRANT_MODE", "server"),
        help="server or local",
    )
    parser.add_argument(
        "--qdrant-host",
        default=os.getenv("QDRANT_HOST", "localhost"),
    )
    parser.add_argument(
        "--qdrant-port",
        type=int,
        default=int(os.getenv("QDRANT_PORT", "6333")),
    )
    parser.add_argument(
        "--qdrant-local-path",
        default=os.getenv("QDRANT_LOCAL_PATH", "data/qdrant_storage"),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only first N chunks. 0 means all chunks",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate Qdrant collection before upload",
    )

    return parser.parse_args()


def setup_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("lab1_6")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


def get_count(conn: sqlite3.Connection, table: str, limit: int) -> int:
    query = f"""
        SELECT COUNT(*)
        FROM {table} AS c
        JOIN documents AS d ON d.doc_id = c.doc_id
    """
    total = conn.execute(query).fetchone()[0]

    if limit > 0:
        return min(total, limit)

    return total


def iter_batches(conn: sqlite3.Connection, table: str, limit: int, batch_size: int):
    query = f"""
        SELECT
            c.chunk_id,
            c.doc_id,
            c.chunk_index,
            c.text,
            c.start_char,
            c.end_char,
            c.metadata_json,
            d.title,
            d.source
        FROM {table} AS c
        JOIN documents AS d ON d.doc_id = c.doc_id
        ORDER BY c.doc_id, c.chunk_index, c.chunk_id
    """

    params = ()
    if limit > 0:
        query += " LIMIT ?"
        params = (limit,)

    cursor = conn.cursor()
    cursor.execute(query, params)

    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break

        yield [dict(row) for row in rows]


def main() -> None:
    load_dotenv(ROOT / ".env")
    args = parse_args()

    processed_dir = ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logger(processed_dir / "lab1_6_embedding.log")

    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = (ROOT / db_path).resolve()

    qdrant_local_path = args.qdrant_local_path
    if not Path(qdrant_local_path).is_absolute():
        qdrant_local_path = str((ROOT / qdrant_local_path).resolve())

    if args.table not in ALLOWED_TABLES:
        raise ValueError(f"table must be one of {sorted(ALLOWED_TABLES)}")

    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")

    started_at = datetime.now(timezone.utc)

    logger.info("=== Lab 1.6: embeddings and Qdrant upload ===")
    logger.info("DB path: %s", db_path)
    logger.info("Table: %s", args.table)
    logger.info("Model: %s", args.model)
    logger.info("Device: %s", args.device or "auto")
    logger.info("Batch size: %s", args.batch_size)
    logger.info("Collection: %s", args.collection)
    logger.info("Qdrant mode: %s", args.qdrant_mode)
    logger.info("Limit: %s", args.limit if args.limit > 0 else "all")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    total = get_count(conn, args.table, args.limit)
    logger.info("Chunks to process: %s", total)

    model = load_embedding_model(args.model, args.device or None)
    vector_size = get_vector_size(model, args.model)
    logger.info("Vector size: %s", vector_size)

    client = get_qdrant_client(
        mode=args.qdrant_mode,
        host=args.qdrant_host,
        port=args.qdrant_port,
        path=qdrant_local_path,
    )

    if args.recreate:
        logger.info("Recreating collection: %s", args.collection)
        recreate_collection(client, args.collection, vector_size)
    else:
        ensure_collection(client, args.collection, vector_size)

    uploaded = 0
    embedded_at = started_at.isoformat()
    default_strategy = "fixed_size" if args.table == "chunks" else "structural"

    with tqdm(total=total, desc="Embedding and upload") as progress_bar:
        for rows in iter_batches(conn, args.table, args.limit, args.batch_size):
            texts = [row["text"] for row in rows]

            vectors = encode_batch(
                model=model,
                texts=texts,
                model_name=args.model,
                batch_size=args.batch_size,
                normalize=True,
            )

            points = build_points(
                rows=rows,
                vectors=vectors,
                model_name=args.model,
                default_strategy=default_strategy,
                embedded_at=embedded_at,
            )

            client.upsert(
                collection_name=args.collection,
                points=points,
                wait=True,
            )

            uploaded += len(points)
            progress_bar.update(len(points))

    conn.close()

    finished_at = datetime.now(timezone.utc)

    report = {
        "lab": "1.6",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "db_path": str(db_path),
        "table": args.table,
        "embedding_model": args.model,
        "device": args.device or "auto",
        "batch_size": args.batch_size,
        "normalize_embeddings": True,
        "document_prefix": "passage: " if uses_e5_prefix(args.model) else "",
        "qdrant_mode": args.qdrant_mode,
        "collection_name": args.collection,
        "vector_size": vector_size,
        "chunks_total": total,
        "points_uploaded": uploaded,
        "errors": 0,
    }

    report_path = processed_dir / "lab1_6_embedding_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("Uploaded points: %s", uploaded)
    logger.info("Report saved to: %s", report_path)
    logger.info("Done")


if __name__ == "__main__":
    main()