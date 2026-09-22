"""Tests for Lab 1.7 BM25/FTS5 search."""

from __future__ import annotations

import sqlite3

import pytest

from src.indexing.bm25_index import (
    build_bm25_index,
    fts5_available,
    search_bm25,
)

pytestmark = pytest.mark.skipif(
    not fts5_available(),
    reason="SQLite FTS5 is not available",
)


@pytest.fixture()
def db_path(tmp_path):
    db = tmp_path / "test.sqlite3"

    conn = sqlite3.connect(db)

    conn.execute(
        """
        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            start_char INTEGER NOT NULL,
            end_char INTEGER NOT NULL,
            metadata_json TEXT NOT NULL
        );
        """
    )

    rows = [
        ("1_c0000", "1", 0, "Москва столица России", 0, 20, "{}"),
        ("2_c0000", "2", 0, "Москва город на реке", 0, 20, "{}"),
        ("3_c0000", "3", 0, "Волга впадает в Каспийское море", 0, 30, "{}"),
    ]

    conn.executemany(
        "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?);",
        rows,
    )

    conn.commit()
    conn.close()

    return db


def test_build_index_counts_chunks(db_path):
    report = build_bm25_index(db_path)

    assert report["indexed_chunks"] == 3


def test_search_returns_relevant_chunks(db_path):
    build_bm25_index(db_path)

    results = search_bm25(
        "Москва",
        top_k=10,
        db_path=db_path,
    )

    assert len(results) == 2
    assert {row["chunk_id"] for row in results} == {
        "1_c0000",
        "2_c0000",
    }


def test_search_empty_query_returns_empty_list(db_path):
    build_bm25_index(db_path)

    assert search_bm25("   ", db_path=db_path) == []


def test_search_respects_top_k(db_path):
    build_bm25_index(db_path)

    results = search_bm25(
        "Москва",
        top_k=1,
        db_path=db_path,
    )

    assert len(results) == 1