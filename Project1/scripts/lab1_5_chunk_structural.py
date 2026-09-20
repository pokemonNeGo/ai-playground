from __future__ import annotations

import json
import logging
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path

from src.chunking.structural import chunk_text_structural

DB_PATH = Path('data/processed/ru_wikipedia_5000_normalized.sqlite3')
LOG_PATH = Path('logs/lab1_5_chunking.log')
REPORT_PATH = Path('reports/lab1_5_structural_stats.json')

# Главный параметр стратегии B.
# Для первого сравнения рекомендуется 500, как в стратегии A.
MAX_CHARS = 500

BATCH_SIZE = 5000

INSERT_SQL = """
INSERT INTO chunks_structural (
    chunk_id,
    doc_id,
    chunk_index,
    heading_path,
    text,
    text_words,
    start_char,
    end_char,
    chunking_strategy,
    max_chars
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'structural', ?)
"""


def setup_logger() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler(LOG_PATH, encoding='utf-8'),
            logging.StreamHandler(),
        ],
    )


def get_text_column(conn: sqlite3.Connection) -> str:
    """
    Пытается автоматически найти колонку с текстом в таблице documents.
    """
    cols = [row[1] for row in conn.execute('PRAGMA table_info(documents)')]

    for col in ('normalized_text', 'text', 'normalized_body', 'body', 'content'):
        if col in cols:
            return col

    raise RuntimeError(
        f'Не найден текстовый столбец в таблице documents. Доступные колонки: {cols}'
    )


def create_table(conn: sqlite3.Connection) -> None:
    conn.execute('DROP TABLE IF EXISTS chunks_structural')

    conn.execute("""
        CREATE TABLE chunks_structural (
            chunk_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL REFERENCES documents(doc_id),
            chunk_index INTEGER NOT NULL,
            heading_path TEXT NOT NULL DEFAULT '',
            text TEXT NOT NULL,
            text_words INTEGER NOT NULL,
            start_char INTEGER NOT NULL,
            end_char INTEGER NOT NULL,
            chunking_strategy TEXT NOT NULL DEFAULT 'structural',
            max_chars INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (doc_id, chunk_index)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_structural_doc_id
        ON chunks_structural(doc_id)
    """)


def main() -> None:
    setup_logger()

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f'База не найдена: {DB_PATH}. '
            'Сначала выполните скрипты Лаб 1.3 и 1.4.'
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')

    create_table(conn)

    text_col = get_text_column(conn)
    logging.info('Используется колонка текста: %s', text_col)

    docs = conn.execute(
        f'SELECT doc_id, {text_col} FROM documents ORDER BY doc_id'
    ).fetchall()

    logging.info('Документов к обработке: %d', len(docs))

    rows = []
    lengths = []
    failed = []

    total_chunks = 0
    docs_with_chunks = 0

    for processed, (doc_id, text) in enumerate(docs, start=1):
        try:
            text = text or ''
            doc_chunks = chunk_text_structural(text, max_chars=MAX_CHARS)

            if doc_chunks:
                docs_with_chunks += 1

            for idx, ch in enumerate(doc_chunks):
                chunk_id = f'{doc_id}_s{idx:04d}'
                chunk_text = ch['text']

                rows.append((
                    chunk_id,
                    doc_id,
                    idx,
                    ch['heading_path'],
                    chunk_text,
                    len(chunk_text.split()),
                    ch['start_char'],
                    ch['end_char'],
                    MAX_CHARS,
                ))

                lengths.append(len(chunk_text))
                total_chunks += 1

        except Exception as exc:
            logging.exception('Ошибка обработки документа %s', doc_id)
            failed.append({'doc_id': doc_id, 'error': str(exc)})

        if len(rows) >= BATCH_SIZE:
            conn.executemany(INSERT_SQL, rows)
            conn.commit()
            rows = []

        if processed % 500 == 0:
            logging.info('Обработано %d/%d документов', processed, len(docs))

    if rows:
        conn.executemany(INSERT_SQL, rows)
        conn.commit()

    report = {
        'lab': '1.5',
        'strategy': 'structural',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'db_path': str(DB_PATH),
        'params': {
            'max_chars': MAX_CHARS,
            'overlap': 0,
            'heading_detection': (
                'explicit wiki/markdown/numbered/all-caps; '
                'fallback to paragraphs/sentences'
            ),
            'long_block_split': 'sentences, then spaces',
        },
        'documents_total': len(docs),
        'documents_failed': len(failed),
        'documents_with_chunks': docs_with_chunks,
        'chunks_total': total_chunks,
        'chunks_per_doc_mean_over_all_docs': (
            total_chunks / len(docs) if docs else 0.0
        ),
        'chunks_per_doc_mean_over_docs_with_chunks': (
            total_chunks / docs_with_chunks if docs_with_chunks else 0.0
        ),
        'chunk_length_mean': statistics.mean(lengths) if lengths else 0.0,
        'chunk_length_median': statistics.median(lengths) if lengths else 0.0,
        'chunk_length_min': min(lengths) if lengths else 0,
        'chunk_length_max': max(lengths) if lengths else 0,
        'failed_examples': failed[:10],
    }

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    logging.info(
        'Готово. Чанков: %d. Отчёт: %s',
        total_chunks,
        REPORT_PATH,
    )

    conn.close()


if __name__ == '__main__':
    main()