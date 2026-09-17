"""
Лаб 1.2, пункт 15: быстрая проверка качества очищенного текста.

Сканирует распарсенный корпус и считает остатки разметки и артефакты.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARSED = PROJECT_ROOT / "data/processed/ru_wikipedia_5000_parsed.jsonl"

PATTERNS = {
    "wiki_links_[[": re.compile(r"\[\["),
    "templates_{{": re.compile(r"\{\{"),
    "ref_tags": re.compile(r"<ref", re.I),
    "html_tags": re.compile(r"<[a-zA-Z/][^>]*>"),
    "urls_http": re.compile(r"https?://"),
    "empty_parens": re.compile(r"\([^()A-Za-zА-Яа-яЁё0-9]*\)"),
    "double_spaces": re.compile(r"[ ]{2,}"),
}


def main() -> int:
    if not PARSED.exists():
        print(f"File not found: {PARSED}")
        return 1

    total = 0
    total_chars = 0
    counts = {name: 0 for name in PATTERNS}
    docs_with = {name: 0 for name in PATTERNS}

    with PARSED.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            doc = json.loads(line)
            text = doc.get("text", "")

            total += 1
            total_chars += len(text)

            for name, rx in PATTERNS.items():
                n = len(rx.findall(text))
                if n:
                    counts[name] += n
                    docs_with[name] += 1

    print(f"Documents: {total}")
    if total:
        print(f"Avg text length: {total_chars / total:.0f} chars")

    print(f"{'marker':<18}{'occurrences':>14}{'documents':>12}")
    for name in PATTERNS:
        print(f"{name:<18}{counts[name]:>14}{docs_with[name]:>12}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())