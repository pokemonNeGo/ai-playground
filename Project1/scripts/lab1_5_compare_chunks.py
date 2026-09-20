from __future__ import annotations

import csv
import json
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path('data/processed/ru_wikipedia_5000_normalized.sqlite3')
JSON_PATH = Path('reports/lab1_5_length_comparison.json')
CSV_PATH = Path('reports/lab1_5_length_histogram.csv')

TABLES = {
    'fixed': 'chunks',
    'structural': 'chunks_structural',
}

BUCKETS = [
    (0, 199),
    (200, 399),
    (400, 499),
    (500, 599),
    (600, 799),
    (800, 999),
    (1000, 1499),
    (1500, 999_999_999),
]


def percentile(sorted_values: list[int], p: float) -> float:
    if not sorted_values:
        return 0.0

    if len(sorted_values) == 1:
        return float(sorted_values[0])

    k = (len(sorted_values) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)

    if f == c:
        return float(sorted_values[f])

    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table,),
    ).fetchone()[0]

    return row > 0


def stats_from_lengths(lengths: list[int]) -> dict:
    if not lengths:
        return {
            'count': 0,
            'min': None,
            'max': None,
            'mean': None,
            'median': None,
            'stdev': None,
            'p50': None,
            'p90': None,
            'p95': None,
            'p99': None,
        }

    sorted_lengths = sorted(lengths)

    return {
        'count': len(lengths),
        'min': sorted_lengths[0],
        'max': sorted_lengths[-1],
        'mean': statistics.mean(lengths),
        'median': statistics.median(lengths),
        'stdev': statistics.pstdev(lengths),
        'p50': percentile(sorted_lengths, 50),
        'p90': percentile(sorted_lengths, 90),
        'p95': percentile(sorted_lengths, 95),
        'p99': percentile(sorted_lengths, 99),
    }


def doc_stats(conn: sqlite3.Connection, table: str) -> dict:
    total_docs = conn.execute(
        'SELECT COUNT(*) FROM documents'
    ).fetchone()[0]

    rows = conn.execute(
        f"""
        SELECT doc_id, COUNT(*) AS cnt
        FROM {table}
        GROUP BY doc_id
        """
    ).fetchall()

    counts = [row[1] for row in rows]

    if not counts:
        return {
            'docs_total': total_docs,
            'docs_with_chunks': 0,
            'docs_without_chunks': total_docs,
            'chunks_per_doc_mean': 0.0,
            'chunks_per_doc_median': 0.0,
            'chunks_per_doc_min': 0,
            'chunks_per_doc_max': 0,
        }

    return {
        'docs_total': total_docs,
        'docs_with_chunks': len(rows),
        'docs_without_chunks': total_docs - len(rows),
        'chunks_per_doc_mean': statistics.mean(counts),
        'chunks_per_doc_median': statistics.median(counts),
        'chunks_per_doc_min': min(counts),
        'chunks_per_doc_max': max(counts),
    }


def bucket_label(lo: int, hi: int) -> str:
    if hi >= 999_999_999:
        return f'{lo}+'
    return f'{lo}-{hi}'


def build_histogram(lengths_by_name: dict[str, list[int]]) -> list[dict]:
    counts = {
        name: [0 for _ in BUCKETS]
        for name in lengths_by_name
    }

    totals = {
        name: len(lengths)
        for name, lengths in lengths_by_name.items()
    }

    for name, lengths in lengths_by_name.items():
        for length in lengths:
            for i, (lo, hi) in enumerate(BUCKETS):
                if lo <= length <= hi:
                    counts[name][i] += 1
                    break

    rows = []

    for i, (lo, hi) in enumerate(BUCKETS):
        fixed_count = counts['fixed'][i]
        structural_count = counts['structural'][i]

        fixed_total = totals['fixed']
        structural_total = totals['structural']

        rows.append({
            'bucket': bucket_label(lo, hi),
            'fixed_count': fixed_count,
            'structural_count': structural_count,
            'fixed_percent': (
                100.0 * fixed_count / fixed_total if fixed_total else 0.0
            ),
            'structural_percent': (
                100.0 * structural_count / structural_total
                if structural_total else 0.0
            ),
        })

    return rows


def main() -> None:
    conn = sqlite3.connect(DB_PATH)

    for name, table in TABLES.items():
        if not table_exists(conn, table):
            raise SystemExit(
                f'Таблица {table} для стратегии {name} не найдена. '
                'Сначала выполните соответствующий скрипт чанкования.'
            )

    lengths_by_name: dict[str, list[int]] = {}

    for name, table in TABLES.items():
        lengths = [
            row[0]
            for row in conn.execute(f'SELECT LENGTH(text) FROM {table}')
        ]
        lengths_by_name[name] = lengths

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'db_path': str(DB_PATH),
        'fixed_params': {
            'strategy': 'fixed_size',
            'chunk_size': 500,
            'overlap': 50,
            'step': 450,
            'table': TABLES['fixed'],
        },
        'structural_params': {
            'strategy': 'structural',
            'max_chars': 500,
            'overlap': 0,
            'table': TABLES['structural'],
            'note': (
                'См. также reports/lab1_5_structural_stats.json, '
                'если вы меняли MAX_CHARS в скрипте.'
            ),
        },
        'length_stats': {
            name: stats_from_lengths(lengths_by_name[name])
            for name in TABLES
        },
        'doc_stats': {
            name: doc_stats(conn, TABLES[name])
            for name in TABLES
        },
        'histogram': build_histogram(lengths_by_name),
    }

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                'bucket',
                'fixed_count',
                'structural_count',
                'fixed_percent',
                'structural_percent',
            ],
        )
        writer.writeheader()
        writer.writerows(report['histogram'])

    print(f'JSON report: {JSON_PATH}')
    print(f'CSV histogram: {CSV_PATH}')
    print()

    print(json.dumps(report, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == '__main__':
    main()