import pytest
from src.chunking.fixed_size import chunk_text_fixed_size

def test_empty_text():
    """Пустой текст должен давать 0 чанков"""
    chunks = chunk_text_fixed_size("doc1", "", chunk_size=100, overlap=20)
    assert len(chunks) == 0

def test_short_text():
    """Текст меньше размера чанка должен давать 1 чанк"""
    chunks = chunk_text_fixed_size("doc1", "Короткий текст.", chunk_size=100, overlap=20)
    assert len(chunks) == 1
    assert chunks[0]["text"] == "Короткий текст."
    assert chunks[0]["start_char"] == 0
    assert chunks[0]["end_char"] == 15

def test_overlap_logic():
    """Проверяем, что перекрытие работает корректно"""
    # Текст длиной 15 символов. Чанк 10, перекрытие 2.
    # Шаг = 10 - 2 = 8.
    # 1 чанк: 0..10
    # 2 чанк: 8..15 (так как текст кончился)
    text = "123456789012345" 
    chunks = chunk_text_fixed_size("doc1", text, chunk_size=10, overlap=2)
    
    assert len(chunks) == 2
    
    # Проверяем границы
    assert chunks[0]["start_char"] == 0
    assert chunks[0]["end_char"] == 10
    assert chunks[0]["text"] == "1234567890"
    
    assert chunks[1]["start_char"] == 8
    assert chunks[1]["end_char"] == 15
    assert chunks[1]["text"] == "9012345" # Видим, что '90' пересеклись!

def test_chunk_ids_and_metadata():
    """Проверяем формирование ID и метаданных"""
    chunks = chunk_text_fixed_size("doc_abc", "A" * 20, chunk_size=10, overlap=0)
    assert chunks[0]["chunk_id"] == "doc_abc_c0000"
    assert chunks[1]["chunk_id"] == "doc_abc_c0001"
    assert chunks[0]["metadata"]["chunking_strategy"] == "fixed_size"