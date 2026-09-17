from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "ru_wikipedia_5000_normalized.sqlite3"


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(
            f"DB not found: {DB_PATH}. "
            "Сначала запусти скрипт лабораторной 1.3."
        )

    conn = sqlite3.connect(DB_PATH)

    print("DB:", DB_PATH)
    print()

    documents_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM documents
        """
    ).fetchone()[0]

    print("documents:", documents_count)

    disambig_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM documents
        WHERE is_disambig = 1
        """
    ).fetchone()[0]

    print("disambig_in_table:", disambig_count)

    duplicate_hashes = conn.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT full_hash
            FROM documents
            GROUP BY full_hash
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]

    print("duplicate_full_hashes:", duplicate_hashes)

    text_stats = conn.execute(
        """
        SELECT
            MIN(text_chars),
            MAX(text_chars),
            ROUND(AVG(text_chars), 1)
        FROM documents
        """
    ).fetchone()

    print("text_chars min/max/avg:", text_stats)

    print("\nSample rows:")

    sample_rows = conn.execute(
        """
        SELECT
            doc_id,
            title,
            text_chars,
            text_words
        FROM documents
        LIMIT 3
        """
    ).fetchall()

    for row in sample_rows:
        print(row)

    conn.close()


if __name__ == "__main__":
    main()