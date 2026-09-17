from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.normalize import (
    is_disambiguation,
    normalize_for_hash,
    normalize_text,
    normalize_title,
    sha256_hex,
)

INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "ru_wikipedia_5000_parsed.jsonl"
DB_PATH = PROJECT_ROOT / "data" / "processed" / "ru_wikipedia_5000_normalized.sqlite3"
REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "lab1_3_dedup_report.json"
DUPLICATES_PATH = PROJECT_ROOT / "data" / "processed" / "lab1_3_duplicates.jsonl"
DISAMBIG_PATH = PROJECT_ROOT / "data" / "processed" / "lab1_3_disambig.jsonl"
LOG_PATH = PROJECT_ROOT / "data" / "processed" / "lab1_3_normalize.log"

# Если True — страницы-неоднозначности удаляются из финального корпуса.
# Если хочешь оставить их в таблице с флагом is_disambig=1, поставь False.
REMOVE_DISAMBIG = True


def pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


def main() -> None:
    started_at = datetime.now(timezone.utc).isoformat()
    logs = [f"Lab 1.3 started at {started_at}"]

    for path in (INPUT_PATH, DB_PATH, REPORT_PATH, DUPLICATES_PATH, DISAMBIG_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)

    if DB_PATH.exists():
        DB_PATH.unlink()

    input_docs = 0
    invalid_docs = 0
    duplicates_doc_id = 0
    duplicates_content = 0
    disambig_removed = 0

    seen_doc_ids = set()
    seen_full_hashes = {}

    rows = []
    duplicates = []
    disambigs = []

    with INPUT_PATH.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            input_docs += 1

            if input_docs % 1000 == 0:
                print(f"processed {input_docs} lines")

            try:
                doc = json.loads(line)
            except json.JSONDecodeError as exc:
                invalid_docs += 1
                logs.append(f"Invalid JSON line {line_no}: {exc}")
                continue

            doc_id = str(doc.get("doc_id") or "").strip()
            title_raw = str(doc.get("title") or "").strip()
            text_raw = str(doc.get("text") or "").strip()
            source = str(doc.get("source") or "").strip()
            date = doc.get("date")

            if date is not None:
                date = str(date)

            if not doc_id or not text_raw:
                invalid_docs += 1
                logs.append(f"Line {line_no}: missing doc_id/text")
                continue

            title = normalize_title(title_raw)
            text = normalize_text(text_raw)

            if not text:
                invalid_docs += 1
                logs.append(f"Line {line_no}: text empty after normalization")
                continue

            # Дубли по doc_id.
            if doc_id in seen_doc_ids:
                duplicates_doc_id += 1
                duplicates.append(
                    {
                        "reason": "doc_id",
                        "duplicate_doc_id": doc_id,
                        "kept_doc_id": doc_id,
                        "title": title,
                    }
                )
                continue

            seen_doc_ids.add(doc_id)

            # Страницы-неоднозначности.
            disambig = is_disambiguation(title, text)

            if REMOVE_DISAMBIG and disambig:
                disambig_removed += 1
                disambigs.append(
                    {
                        "doc_id": doc_id,
                        "title": title,
                        "text_chars": len(text),
                    }
                )
                continue

            # Дедупликация по нормализованному заголовку и тексту.
            title_key = normalize_for_hash(title)
            text_key = normalize_for_hash(text)

            title_hash = sha256_hex(title_key)
            text_hash = sha256_hex(text_key)
            full_hash = sha256_hex(f"{title_key}\n{text_key}")

            if full_hash in seen_full_hashes:
                duplicates_content += 1
                duplicates.append(
                    {
                        "reason": "normalized_title_and_text",
                        "duplicate_doc_id": doc_id,
                        "kept_doc_id": seen_full_hashes[full_hash],
                        "title": title,
                    }
                )
                continue

            seen_full_hashes[full_hash] = doc_id

            meta_raw = doc.get("metadata")
            metadata = meta_raw if isinstance(meta_raw, dict) else {"raw_metadata": meta_raw}

            metadata["normalization"] = {
                "lab": "1.3",
                "normalized_at": started_at,
                "title_norm_hash": title_hash,
                "text_norm_hash": text_hash,
                "full_hash": full_hash,
                "is_disambig": disambig,
            }

            rows.append(
                (
                    doc_id,
                    title,
                    text,
                    source,
                    date,
                    len(text),
                    len(text.split()),
                    title_hash,
                    text_hash,
                    full_hash,
                    1 if disambig else 0,
                    json.dumps(metadata, ensure_ascii=False),
                )
            )

    # Сохраняем в SQLite.
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS documents")

    cur.execute(
        """
        CREATE TABLE documents (
            doc_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            text TEXT NOT NULL,
            source TEXT,
            date TEXT,
            text_chars INTEGER NOT NULL,
            text_words INTEGER NOT NULL,
            title_norm_hash TEXT NOT NULL,
            text_norm_hash TEXT NOT NULL,
            full_hash TEXT NOT NULL,
            is_disambig INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL
        )
        """
    )

    cur.executemany(
        """
        INSERT INTO documents
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )

    cur.execute("CREATE INDEX idx_documents_title ON documents(title)")
    cur.execute("CREATE INDEX idx_documents_full_hash ON documents(full_hash)")

    conn.commit()
    conn.close()

    # Сохраняем удалённые дубликаты для аудита.
    with DUPLICATES_PATH.open("w", encoding="utf-8") as f:
        for item in duplicates:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    # Сохраняем удалённые неоднозначности для аудита.
    with DISAMBIG_PATH.open("w", encoding="utf-8") as f:
        for item in disambigs:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    valid_before_removal = input_docs - invalid_docs
    duplicates_total = duplicates_doc_id + duplicates_content
    output_docs = len(rows)

    report = {
        "lab": "1.3",
        "generated_at": started_at,
        "storage_format": "sqlite",
        "input_path": str(INPUT_PATH.relative_to(PROJECT_ROOT)),
        "output_db": str(DB_PATH.relative_to(PROJECT_ROOT)),
        "table_name": "documents",
        "settings": {
            "remove_disambig": REMOVE_DISAMBIG,
            "dedup_key": "normalized_title_and_text",
            "normalization": "NFC + whitespace cleanup; hash key lowercased and whitespace collapsed",
        },
        "counts": {
            "input_docs": input_docs,
            "invalid_docs": invalid_docs,
            "valid_before_removal": valid_before_removal,
            "duplicates_doc_id": duplicates_doc_id,
            "duplicates_content": duplicates_content,
            "duplicates_total": duplicates_total,
            "disambig_removed": disambig_removed,
            "output_docs": output_docs,
        },
        "shares_percent": {
            "invalid_of_input": pct(invalid_docs, input_docs),
            "duplicates_of_valid": pct(duplicates_total, valid_before_removal),
            "doc_id_duplicates_of_valid": pct(duplicates_doc_id, valid_before_removal),
            "content_duplicates_of_valid": pct(duplicates_content, valid_before_removal),
            "disambig_of_valid": pct(disambig_removed, valid_before_removal),
            "final_of_input": pct(output_docs, input_docs),
        },
        "output_paths": {
            "report": str(REPORT_PATH.relative_to(PROJECT_ROOT)),
            "duplicates": str(DUPLICATES_PATH.relative_to(PROJECT_ROOT)),
            "disambig": str(DISAMBIG_PATH.relative_to(PROJECT_ROOT)),
        },
    }

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logs.append(f"input_docs={input_docs}")
    logs.append(f"invalid_docs={invalid_docs}")
    logs.append(f"duplicates_doc_id={duplicates_doc_id}")
    logs.append(f"duplicates_content={duplicates_content}")
    logs.append(f"disambig_removed={disambig_removed}")
    logs.append(f"output_docs={output_docs}")
    logs.append(f"db={DB_PATH}")

    LOG_PATH.write_text("\n".join(logs) + "\n", encoding="utf-8")

    print("\nLab 1.3 report:")
    print(json.dumps(report["counts"], ensure_ascii=False, indent=2))
    print(json.dumps(report["shares_percent"], ensure_ascii=False, indent=2))
    print(f"\nSaved: {DB_PATH}")
    print(f"Saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()