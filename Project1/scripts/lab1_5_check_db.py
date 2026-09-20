from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path('data/processed/ru_wikipedia_5000_normalized.sqlite3')


def main() -> None:
    conn = sqlite3.connect(DB_PATH)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    print('Tables:', ', '.join(sorted(tables)))
    print()

    for table in ['chunks', 'chunks_structural']:
        if table not in tables:
            print(f'{table}: MISSING')
            continue

        count = conn.execute(
            f'SELECT COUNT(*) FROM {table}'
        ).fetchone()[0]

        docs = conn.execute(
            f'SELECT COUNT(DISTINCT doc_id) FROM {table}'
        ).fetchone()[0]

        min_len, max_len, avg_len = conn.execute(
            f"""
            SELECT
                MIN(LENGTH(text)),
                MAX(LENGTH(text)),
                AVG(LENGTH(text))
            FROM {table}
            """
        ).fetchone()

        empty = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE text IS NULL OR text = ''
            """
        ).fetchone()[0]

        print(f'{table}:')
        print(f'  rows: {count}')
        print(f'  distinct docs: {docs}')
        print(f'  min length: {min_len}')
        print(f'  max length: {max_len}')
        print(f'  avg length: {float(avg_len or 0):.1f}')
        print(f'  empty chunks: {empty}')
        print()

    if 'chunks_structural' in tables:
        checks = [
            (
                'duplicate chunk_id',
                """
                SELECT COUNT(*) FROM (
                    SELECT chunk_id
                    FROM chunks_structural
                    GROUP BY chunk_id
                    HAVING COUNT(*) > 1
                )
                """,
            ),
            (
                'duplicate doc_id + chunk_index',
                """
                SELECT COUNT(*) FROM (
                    SELECT doc_id, chunk_index
                    FROM chunks_structural
                    GROUP BY doc_id, chunk_index
                    HAVING COUNT(*) > 1
                )
                """,
            ),
            (
                'chunks with start_char >= end_char',
                """
                SELECT COUNT(*)
                FROM chunks_structural
                WHERE start_char >= end_char
                """,
            ),
            (
                'documents without structural chunks',
                """
                SELECT COUNT(*)
                FROM documents d
                LEFT JOIN chunks_structural c
                    ON d.doc_id = c.doc_id
                WHERE c.doc_id IS NULL
                """,
            ),
        ]

        print('Structural checks:')
        for label, query in checks:
            value = conn.execute(query).fetchone()[0]
            print(f'  {label}: {value}')

        print()

    fk_violations = conn.execute('PRAGMA foreign_key_check').fetchall()
    print('foreign_key_violations:', len(fk_violations))

    conn.close()


if __name__ == '__main__':
    main()