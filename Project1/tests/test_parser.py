"""
Тесты
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.parser import ParserError, parse, safe_parse  # noqa: E402

GOOD_DOC = {
    "doc_id": "123",
    "title": "Тестовая статья",
    "text": "Это достаточно длинный текст статьи, чтобы пройти минимальную проверку длины после очистки. " * 3,
    "source": "https://ru.wikipedia.org/wiki/Тест",
    "date": "",
    "metadata": {
        "wiki": True,
    },
}


def test_parse_good_dict():
    result = parse(GOOD_DOC)

    assert result["text"].startswith("Это достаточно длинный текст")
    assert result["metadata"]["doc_id"] == "123"
    assert result["metadata"]["title"] == "Тестовая статья"
    assert result["metadata"]["source"] == "https://ru.wikipedia.org/wiki/Тест"


def test_parse_json_string():
    result = parse(json.dumps(GOOD_DOC, ensure_ascii=False))

    assert result["metadata"]["doc_id"] == "123"
    assert result["metadata"]["title"] == "Тестовая статья"


def test_parse_cleans_wiki_markup():
    doc = dict(GOOD_DOC)
    doc["text"] = (
        "Заголовок [[Москва|Москве]] {{cite web|url=x}} <ref>ref</ref> "
        + doc["text"]
    )

    result = parse(doc)

    assert "Москве" in result["text"]
    assert "[[" not in result["text"]
    assert "{{" not in result["text"]
    assert "<ref>" not in result["text"]


def test_parse_missing_text():
    parsed, error = safe_parse({"title": "No text"})

    assert parsed is None
    assert error is not None
    assert "text" in error["message"].lower()


def test_parse_invalid_json():
    parsed, error = safe_parse("{bad json")

    assert parsed is None
    assert error is not None
    assert error["type"] == "ParserError"


def test_parse_too_short():
    parsed, error = safe_parse(
        {
            "title": "Short",
            "text": "Коротко",
        }
    )

    assert parsed is None
    assert error is not None


def test_parse_removes_nested_leftovers():
    doc = dict(GOOD_DOC)
    doc["text"] = (
        "Вложено [[а [[б]] в]] и шаблон {{а {{б}} в}} и скобки ( , , ). "
        + doc["text"]
    )

    result = parse(doc)

    assert "[[" not in result["text"]
    assert "{{" not in result["text"]
    assert "( , , )" not in result["text"]