from src.ingestion.normalize import (
    is_disambiguation,
    normalize_for_hash,
    normalize_text,
    normalize_title,
)


def test_normalize_text_collapses_whitespace():
    raw = "  Привет,   мир! \n Второй   абзац "
    expected = "Привет, мир!\nВторой абзац"
    assert normalize_text(raw) == expected


def test_normalize_title_strips_whitespace():
    raw = "   Тестовая   страница   "
    expected = "Тестовая страница"
    assert normalize_title(raw) == expected


def test_normalize_for_hash_lowercases_and_collapses_whitespace():
    raw = "  Привет,   МИР \n "
    expected = "привет, мир"
    assert normalize_for_hash(raw) == expected


def test_disambiguation_title_marker():
    assert is_disambiguation("Тест (значения)", "Обычный текст.")


def test_disambiguation_text_marker():
    title = "Волга"
    text = "Волга может означать: река в России, название корабля."
    assert is_disambiguation(title, text)


def test_not_disambiguation():
    title = "Обычная статья"
    text = "Это обычный энциклопедический текст про некоторый объект."
    assert not is_disambiguation(title, text)