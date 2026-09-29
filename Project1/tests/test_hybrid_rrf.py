from src.retrieval.hybrid_search import fuse_rrf, rrf_scores


def test_rrf_item_present_in_both_lists_gets_higher_score():
    bm25_ids = ["a", "b", "c"]
    dense_ids = ["b", "c", "d"]

    scores = rrf_scores([bm25_ids, dense_ids], k=60)

    # "b" есть в обоих списках:
    # в первом списке ранг 2, во втором ранг 1.
    # "a" есть только в первом списке и стоит рангом 1.
    assert scores["b"] > scores["a"]

    # "c" есть в обоих списках, "d" только в одном.
    assert scores["c"] > scores["d"]


def test_rrf_exact_score_for_single_item_in_two_lists():
    scores = rrf_scores([["x"], ["x"]], k=60)

    expected = 1.0 / 61.0 + 1.0 / 61.0
    assert abs(scores["x"] - expected) < 1e-12


def test_fuse_rrf_top_k_and_deterministic_tie():
    # "a" и "b" имеют одинаковый RRF-скор.
    # Ожидаем детерминированную сортировку по алфавиту.
    fused = fuse_rrf([["a"], ["b"]], k=60, top_k=2)

    ids = [item_id for item_id, _ in fused]
    assert ids == ["a", "b"]


def test_fuse_rrf_empty_lists():
    fused = fuse_rrf([[], []], k=60, top_k=10)
    assert fused == []