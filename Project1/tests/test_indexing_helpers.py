from src.indexing.embeddings import prepare_doc_texts, uses_e5_prefix
from src.indexing.qdrant_index import make_point_id


def test_uses_e5_prefix_for_multilingual_e5():
    assert uses_e5_prefix("intfloat/multilingual-e5-base") is True
    assert uses_e5_prefix("intfloat/multilingual-e5-large") is True


def test_no_e5_prefix_for_bge():
    assert uses_e5_prefix("BAAI/bge-m3") is False


def test_prepare_doc_texts_adds_prefix_for_e5():
    prepared = prepare_doc_texts(["текст"], "intfloat/multilingual-e5-base")
    assert prepared == ["passage: текст"]


def test_prepare_doc_texts_no_prefix_for_bge():
    prepared = prepare_doc_texts(["текст"], "BAAI/bge-m3")
    assert prepared == ["текст"]


def test_make_point_id_deterministic():
    first = make_point_id("7_c0000")
    second = make_point_id("7_c0000")
    third = make_point_id("7_c0001")

    assert first == second
    assert first != third