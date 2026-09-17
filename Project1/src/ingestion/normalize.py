from __future__ import annotations

import hashlib
import re
import unicodedata

_COLLAPSE_SPACES_RE = re.compile(r"[ \t]+")
_COLLAPSE_ALL_WS_RE = re.compile(r"\s+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

DISAMBIG_TITLE_MARKERS = ("(значения)",)

DISAMBIG_TEXT_MARKERS = (
    "может означать",
    "многозначное слово",
    "многозначное понятие",
    "список значений",
)


def normalize_text(text: str) -> str:
    """
    Нормализует текст для хранения.

    - Unicode NFC
    - нормализует переводы строк
    - убирает лишние пробелы и табуляции
    - схлопывает несколько пустых строк
    - сохраняет исходный регистр текста
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFC", str(text))
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")

    lines = [_COLLAPSE_SPACES_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)

    return text.strip()


def normalize_title(title: str) -> str:
    """
    Нормализует заголовок для хранения.
    """
    if not title:
        return ""

    title = unicodedata.normalize("NFC", str(title))
    title = title.replace("\t", " ")
    title = _COLLAPSE_SPACES_RE.sub(" ", title)

    return title.strip()


def normalize_for_hash(text: str) -> str:
    """
    Нормализует текст только для дедупликации.

    - переводит в нижний регистр
    - схлопывает любые пробельные символы
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFC", str(text).lower())
    return _COLLAPSE_ALL_WS_RE.sub(" ", text).strip()


def sha256_hex(text: str) -> str:
    """
    Считает sha256 от строки.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_disambiguation(title: str, text: str) -> bool:
    """
    Пытается определить страницу-неоднозначность.

    Используем простые эвристики:
    - в заголовке есть '(значения)'
    - в начале текста встречаются маркеры неоднозначности
    """
    title_norm = normalize_for_hash(title)

    if any(marker in title_norm for marker in DISAMBIG_TITLE_MARKERS):
        return True

    head = normalize_for_hash(text[:500])

    return any(marker in head for marker in DISAMBIG_TEXT_MARKERS)