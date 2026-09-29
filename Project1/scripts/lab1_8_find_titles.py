from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Поиск заголовков документов в SQLite"
    )
    parser.add_argument(
        "pattern",
        help="Подстрока для поиска в title",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/processed/ru_wikipedia_5000_normalized.sqlite3"),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
    )

    args = parser.parse_args()

    if not args.db.exists():
        raise FileNotFoundError(f"Файл базы не найден: {args.db}")

    connection = sqlite3.connect(args.db)
    cursor = connection.cursor()

    like_pattern = f"%{args.pattern}%"

    rows = cursor.execute(
        """
        SELECT doc_id, title
        FROM documents
        WHERE title LIKE ?
        ORDER BY title
        LIMIT ?
        """,
        (like_pattern, args.limit),
    ).fetchall()

    if not rows:
        print("Ничего не найдено")
        return

    for doc_id, title in rows:
        print(f"{doc_id}\t{title}")

    connection.close()


if __name__ == "__main__":
    main()