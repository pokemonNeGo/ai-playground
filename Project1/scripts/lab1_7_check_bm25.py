"""Check BM25/FTS5 index for Lab 1.7."""

from __future__ import annotations

import sqlite3

from src.indexing.bm25_index import (
    CHUNKS_TABLE,
    DB_PATH,
    FTS_TABLE,
    search_bm25,
)


def main() -> None:
    print(f"DB path: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)

    try:
        chunks_count = conn.execute(
            f"SELECT COUNT(*) FROM {CHUNKS_TABLE};"
        ).fetchone()[0]
    except sqlite3.OperationalError as exc:
        raise SystemExit(f"Chunks table not found: {exc}")

    try:
        fts_count = conn.execute(
            f"SELECT COUNT(*) FROM {FTS_TABLE};"
        ).fetchone()[0]
    except sqlite3.OperationalError as exc:
        raise SystemExit(
            "FTS table not found. Run: python -m scripts.lab1_7_build_bm25"
        )

    try:
        sample_title = conn.execute(
            "SELECT title FROM documents ORDER BY doc_id LIMIT 1;"
        ).fetchone()
    except sqlite3.OperationalError:
        sample_title = None

    finally:
        conn.close()

    print(f"chunks rows: {chunks_count}")
    print(f"fts rows: {fts_count}")

    if chunks_count != fts_count:
        raise SystemExit("FTS row count does not match chunks table.")

    query = sample_title[0] if sample_title else "Россия"
    print(f"Sample query: {query}")

    results = search_bm25(query, top_k=3)

    if not results:
        print("Sample search returned no results. Try another query.")
        return

    for i, row in enumerate(results, 1):
        text = " ".join(row["text"].split())

        print(
            f"{i}. score={row['score']:.4f} "
            f"chunk_id={row['chunk_id']} "
            f"doc_id={row['doc_id']}"
        )
        print(f"   {text[:120]}")


if __name__ == "__main__":
    main()