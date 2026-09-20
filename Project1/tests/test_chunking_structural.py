from src.chunking.structural import chunk_text_structural


def test_empty_text():
    chunks = chunk_text_structural("", max_chars=500)
    assert chunks == []


def test_whitespace_only_text():
    chunks = chunk_text_structural("\n\n   \n", max_chars=500)
    assert chunks == []


def test_short_paragraphs_are_merged():
    text = "Первый абзац.\n\nВторой абзац."
    chunks = chunk_text_structural(text, max_chars=500)

    assert len(chunks) == 1

    chunk = chunks[0]
    assert chunk["heading_path"] == ""
    assert "Первый абзац." in chunk["text"]
    assert "Второй абзац." in chunk["text"]

    # Проверка, что границы корректны.
    assert text[chunk["start_char"]:chunk["end_char"]] == chunk["text"]


def test_headings_create_separate_chunks():
    text = (
        "Введение.\n\n"
        "== История ==\n"
        "Исторический текст.\n\n"
        "== Наука ==\n"
        "Научный текст."
    )

    chunks = chunk_text_structural(text, max_chars=500)

    paths = [chunk["heading_path"] for chunk in chunks]

    assert "" in paths
    assert "История" in paths
    assert "Наука" in paths

    # Как минимум введение + два раздела.
    assert len(chunks) >= 3


def test_long_text_respects_max_chars():
    text = "Это отдельное предложение. " * 200
    chunks = chunk_text_structural(text, max_chars=100)

    assert len(chunks) > 1

    for chunk in chunks:
        # Небольшой допуск нужен из-за обрезки пробелов и границ предложений.
        assert len(chunk["text"]) <= 110
        assert chunk["end_char"] >= chunk["start_char"]


def test_offsets_match_original_text():
    text = (
        "Первый абзац.\n\n"
        "Второй абзац.\n\n"
        "Третий абзац."
    )

    chunks = chunk_text_structural(text, max_chars=25)

    assert len(chunks) > 0

    for chunk in chunks:
        start = chunk["start_char"]
        end = chunk["end_char"]
        assert text[start:end] == chunk["text"]