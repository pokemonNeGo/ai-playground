"""CLI BM25 search for Lab 1.7."""

from __future__ import annotations

import argparse

from src.indexing.bm25_index import search_bm25


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BM25/FTS5 search over chunks"
    )

    parser.add_argument("query", help="Search query")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--db", default=None, help="Path to SQLite database")
    parser.add_argument("--max-text", type=int, default=180)

    args = parser.parse_args()

    results = search_bm25(
        args.query,
        top_k=args.top_k,
        db_path=args.db,
    )

    if not results:
        print("No results.")
        return

    for i, row in enumerate(results, 1):
        text = " ".join(row["text"].split())

        if len(text) > args.max_text:
            text = text[: args.max_text] + "..."

        print(
            f"{i:2d}. score={row['score']: .4f} "
            f"chunk_id={row['chunk_id']} "
            f"doc_id={row['doc_id']}"
        )
        print(f"    {text}")
        print()


if __name__ == "__main__":
    main()