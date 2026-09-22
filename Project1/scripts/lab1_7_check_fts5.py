"""Check that SQLite FTS5 is available."""

import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")

    try:
        conn.execute("CREATE VIRTUAL TABLE fts5_check USING fts5(x);")
        print("FTS5 OK")
    except sqlite3.Error as exc:
        raise SystemExit(f"FTS5 unavailable: {exc}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()