"""
Парсер документов:
- принимает документ как dict или JSON-строку;
- извлекает текст;
- извлекает метаданные: заголовок, источник, дату, doc_id;
- очищает текст от части wiki-разметки и лишних пробелов;
- логирует ошибки на повреждённых документах.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

logger = logging.getLogger("project1.lab1_2.parser")

MIN_TEXT_CHARS = 100


class ParserError(Exception):
    """Базовая ошибка парсера."""


def _as_dict(doc: Any) -> Dict[str, Any]:
    """
    Приводит входной документ к словарке.

    Поддерживаются:
    - dict;
    - JSON-строка.
    """
    if doc is None:
        raise ParserError("doc is None")

    if isinstance(doc, dict):
        return doc

    if isinstance(doc, str):
        text = doc.strip()
        if not text:
            raise ParserError("doc string is empty")

        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ParserError(f"doc is not valid JSON: {exc}") from exc

        if not isinstance(obj, dict):
            raise ParserError("JSON doc is not an object")

        return obj

    raise ParserError(f"unsupported doc type: {type(doc).__name__}")


def _first_str(payload: Dict[str, Any], keys: List[str]) -> Optional[str]:
    """
    Возвращает первое непустое строковое значение по списку ключей.
    """
    for key in keys:
        value = payload.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value_str = str(value).strip()
            if value_str:
                return value_str

    return None


def _remove_nested(
    text: str,
    pattern: str,
    repl: str = " ",
    flags: int = re.S | re.I,
) -> str:
    """
    Удаляет вложенные конструкции в несколько проходов.

    Полностью универсальная очистка сложных шаблонов регулярками невозможна,
    но для этого достаточно.
    """
    for _ in range(3):
        new_text = re.sub(pattern, repl, text, flags=flags)
        if new_text == text:
            break
        text = new_text

    return text


def clean_text(value: Any) -> str:
    """
    Очищает текст документа.

    Удаляет или упрощает:
    - HTML-комментарии;
    - шаблоны вида {{...}};
    - теги <ref>...</ref>;
    - HTML-теги;
    - служебные wiki-ссылки на файлы, категории и изображения;
    - внутренние ссылки вида [[Статья|Текст]] -> Текст;
    - внешние ссылки;
    - лишние пробелы и переводы строк.
    """
    if value is None:
        raise ParserError("text is missing")

    if not isinstance(value, str):
        raise ParserError(f"text has unsupported type: {type(value).__name__}")

    text = value.replace("\r\n", "\n").replace("\r", "\n")

    # HTML-комментарии.
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)

    # Шаблоны вида {{...}}.
    text = _remove_nested(text, r"{{[^{}]*}}", " ")

    # Сноски и ссылки вида <ref /> и <ref>...</ref>.
    text = re.sub(r"<ref[^>]*?/>", " ", text, flags=re.I)
    text = re.sub(r"<ref[^>]*?>.*?</ref>", " ", text, flags=re.S | re.I)

    # Остальные HTML-теги.
    text = re.sub(r"<[^>]+>", " ", text)

    # Служебные wiki-ссылки: файлы, изображения, категории.
    text = re.sub(
        r"\[\[\s*(?:Файл|File|Изображение|Image|Категория|Category|Википедия|Wikipedia)\s*:[^\]]*\]\]",
        " ",
        text,
        flags=re.I,
    )

    # Внутренние wiki-ссылки.
    # [[Статья|Отображаемый текст]] -> Отображаемый текст
    text = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", text)

    # [[Статья]] -> Статья
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)

    # Внешние ссылки в квадратных скобках и обычные ссылки.
    text = re.sub(r"\[https?://[^\]]*\]", " ", text, flags=re.I)
    text = re.sub(r"https?://\S+", " ", text)

        # Fallback: сложные вложенные ссылки и шаблоны, которые не взяли основные regex.
    text = re.sub(r"\[\[.*?\]\]", " ", text, flags=re.S)
    for _ in range(3):
        new_text = re.sub(r"\{\{.*?\}\}", " ", text, flags=re.S)
        if new_text == text:
            break
        text = new_text

    # Гарантия: если после всех проходов остались одинокие пары скобок разметки.
    text = text.replace("[[", " ").replace("]]", " ")
    text = text.replace("{{", " ").replace("}}", " ")

    # Пустые скобки, оставшиеся после удаления ссылок и шаблонов:
    # "( )", "( , , , )", "( ; )" -> убираем полностью. Два прохода на вложенность.
    for _ in range(2):
        text = re.sub(r"\([^()A-Za-zА-Яа-яЁё0-9]*\)", " ", text)

    # Висячая пунктуация на краях скобок:
    # "( ; от «жизнь»..." -> "(от «жизнь»...", "( — верхний город)" -> "(верхний город)"
    text = re.sub(r"\(\s*(?:[;,—-]\s*)+", "(", text)
    text = re.sub(r"\s*(?:[;,—-]\s*)+\)", ")", text)

    # Заголовки вида == Заголовок == -> Заголовок
    text = re.sub(r"(?m)^\s*={2,}\s*(.*?)\s*={2,}\s*$", r"\1", text)

    # Маркеры списков в начале строки.
    text = re.sub(r"(?m)^\s*[*#;:]+\s*", "", text)

    # Нормализация пробелов.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    text = text.strip()

    return text


def _make_doc_id(title: str, text: str) -> str:
    """
    Генерирует временный doc_id, если исходный ID отсутствует.

    Это не идеальная стратегия, но она лучше, чем вернуть документ без ID.
    """
    basis = f"{title}|{text[:1000]}"
    return "gen_" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def parse(doc: Any) -> Dict[str, Any]:
    """
    Принимает документ в виде словаря или JSON-строки.
    Возвращает словарь:

        {
            "text": "...",
            "metadata": {
                "doc_id": "...",
                "title": "...",
                "source": "...",
                "date": "...",
                ...
            }
        }
    """
    payload = _as_dict(doc)

    raw_text = payload.get("text")
    if raw_text is None:
        raw_text = (
            payload.get("content")
            or payload.get("body")
            or payload.get("page_text")
        )

    text = clean_text(raw_text)

    if len(text) < MIN_TEXT_CHARS:
        raise ParserError(
            f"text too short after cleaning: {len(text)} chars < {MIN_TEXT_CHARS}"
        )

    title = _first_str(payload, ["title", "name", "page_title"])

    if title is None:
        first_line = text.split("\n", 1)[0].strip()
        title = first_line[:200] if first_line else "untitled"
        logger.warning("Title missing; using first text line: %.50s", title)

    doc_id = _first_str(
        payload,
        ["doc_id", "id", "page_id", "document_id"],
    )

    if doc_id is None:
        doc_id = _make_doc_id(title, text)
        logger.warning("doc_id missing; generated id=%s", doc_id)

    source = _first_str(
        payload,
        ["source", "url", "page_url", "link"],
    )

    if source is None:
        source = "https://ru.wikipedia.org/wiki/" + quote(title.replace(" ", "_"))
        logger.warning("Source missing; built likely URL from title: %s", source)

    date = _first_str(
        payload,
        ["date", "published", "timestamp", "created"],
    )

    raw_metadata = payload.get("metadata")
    if not isinstance(raw_metadata, dict):
        raw_metadata = {}

    metadata = {
        "doc_id": doc_id,
        "title": title,
        "source": source,
        "date": date,
        "original_metadata": raw_metadata,
        "parser": {
            "lab": "1.2",
            "version": "v1",
            "text_chars": len(text),
        },
    }

    return {
        "text": text,
        "metadata": metadata,
    }


def safe_parse(
    doc: Any,
    line_no: Optional[int] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Безопасная обёртка над parse().

    Возвращает:

        (parsed_result, None)      если документ обработан успешно;
        (None, error_dict)         если была ошибка.

    Это нужно, чтобы один повреждённый документ не ломал обработку всего корпуса.
    """
    try:
        return parse(doc), None

    except ParserError as exc:
        error = {
            "line_no": line_no,
            "type": "ParserError",
            "message": str(exc),
        }
        logger.warning(
            "Parse error line=%s: %s",
            line_no if line_no is not None else "?",
            exc,
        )
        return None, error

    except Exception as exc:  # noqa: BLE001
        error = {
            "line_no": line_no,
            "type": type(exc).__name__,
            "message": str(exc),
        }
        logger.exception(
            "Unexpected parse error line=%s",
            line_no if line_no is not None else "?",
        )
        return None, error