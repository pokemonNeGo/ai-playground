"""BM25 text search for Lab 1.7 using SQLite FTS5.

This module builds a full-text search index over the chunks table and provides
a BM25-ranked text search function returning top-k chunks.
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(
    os.getenv(
        "DB_PATH",
        "data/processed/ru_wikipedia_5000_normalized.sqlite3",
    )
)

CHUNKS_TABLE = os.getenv("CHUNKS_TABLE", "chunks")
FTS_TABLE = os.getenv("BM25_FTS_TABLE", "chunks_fts")

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_MAX_QUERY_TERMS = 32


def fts5_available() -> bool:
    """Return True if SQLite FTS5 is available in the current Python build."""
    conn = sqlite3.connect(":memory:")

    try:
        conn.execute("CREATE VIRTUAL TABLE fts5_check USING fts5(x);")
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def _resolve_db_path(db_path: Path | str | None = None) -> Path:
    return Path(db_path) if db_path is not None else DB_PATH


def _connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(_resolve_db_path(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def prepare_query(query: str) -> str:
    """Convert raw user text into a safe FTS5 query.

    Example:
        "Киевская Русь!" -> '"киевская" OR "русь"'
    """
    words = _WORD_RE.findall(query.lower())

    terms: list[str] = []
    seen: set[str] = set()

    for word in words:
        word = word.replace('"', "").strip()

        if not word or word in seen:
            continue

        seen.add(word)
        terms.append(f'"{word}"')

        if len(terms) >= _MAX_QUERY_TERMS:
            break

    return " OR ".join(terms)


def build_bm25_index(
    db_path: Path | str | None = None,
    *,
    chunks_table: str = CHUNKS_TABLE,
    fts_table: str = FTS_TABLE,
) -> dict[str, Any]:
    """Rebuild the FTS5 index for BM25 search.

    The index is stored inside the same SQLite database as the chunks table.
    """
    if not fts5_available():
        raise RuntimeError("SQLite FTS5 is unavailable in this Python build.")

    conn = _connect(db_path)

    try:
        conn.execute(f"DROP TABLE IF EXISTS {fts_table};")

        conn.execute(
            f"""
            CREATE VIRTUAL TABLE {fts_table}
            USING fts5(
                text,
                chunk_id UNINDEXED,
                doc_id UNINDEXED,
                tokenize='unicode61'
            );
            """
        )

        conn.execute(
            f"""
            INSERT INTO {fts_table}(text, chunk_id, doc_id)
            SELECT text, chunk_id, doc_id
            FROM {chunks_table};
            """
        )

        # Optional FTS5 maintenance command.
        conn.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES('optimize');")

        count = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM {fts_table};"
        ).fetchone()["cnt"]

        conn.commit()

        return {
            "backend": "sqlite_fts5",
            "db_path": str(_resolve_db_path(db_path)),
            "chunks_table": chunks_table,
            "fts_table": fts_table,
            "indexed_chunks": int(count),
        }
    finally:
        conn.close()


def search_bm25(
    query: str,
    top_k: int = 10,
    db_path: Path | str | None = None,
    *,
    chunks_table: str = CHUNKS_TABLE,
    fts_table: str = FTS_TABLE,
) -> list[dict[str, Any]]:
    """Search chunks using BM25 ranking and return top-k results."""
    if top_k <= 0:
        return []

    fts_query = prepare_query(query)

    if not fts_query:
        return []

    conn = _connect(db_path)

    try:
        sql = f"""
            SELECT
                c.chunk_id,
                c.doc_id,
                c.text,
                c.start_char,
                c.end_char,
                bm25({fts_table}) AS score
            FROM {fts_table}
            JOIN {chunks_table} AS c
              ON c.chunk_id = {fts_table}.chunk_id
            WHERE {fts_table} MATCH ?
            ORDER BY score ASC
            LIMIT ?;
        """

        rows = conn.execute(sql, (fts_query, int(top_k))).fetchall()
        return [dict(row) for row in rows]

    except sqlite3.OperationalError as exc:
        message = str(exc).lower()

        if "no such table" in message and fts_table.lower() in message:
            raise RuntimeError(
                "BM25 index not found. Run: python -m scripts.lab1_7_build_bm25"
            ) from exc

        raise

    finally:
        conn.close()


def search_bm25_top10(
    query: str,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Convenience wrapper required by the lab: return top-10 results."""
    return search_bm25(query, top_k=10, db_path=db_path)