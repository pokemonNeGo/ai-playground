from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple


def rrf_scores(
    ranked_lists: Sequence[Sequence[str]],
    k: int = 60,
) -> Dict[str, float]:
    """
    Считает RRF-скоры для нескольких ранжированных списков.

    Каждый список — это упорядоченные идентификаторы, например chunk_id.
    Ранги начинаются с 1.

    Формула:
        score(item) = sum(1 / (k + rank))

    Если один и тот же item есть в нескольких списках, его вклады суммируются.
    """
    if k <= 0:
        raise ValueError("RRF parameter k must be positive")

    scores: Dict[str, float] = {}

    for ranked_list in ranked_lists:
        seen = set()

        for rank, item_id in enumerate(ranked_list, start=1):
            if not item_id:
                continue

            # Защита от случайных дублей внутри одного списка.
            if item_id in seen:
                continue

            seen.add(item_id)
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)

    return scores


def fuse_rrf(
    ranked_lists: Sequence[Sequence[str]],
    k: int = 60,
    top_k: Optional[int] = None,
) -> List[Tuple[str, float]]:
    """
    Объединяет несколько ранжированных списков через RRF.

    Возвращает список вида:
        [(chunk_id, rrf_score), ...]

    Сортировка:
        1. По убыванию RRF-скора.
        2. При равенстве скора — лексикографически по chunk_id,
           чтобы результат был детерминированным.
    """
    scores = rrf_scores(ranked_lists, k=k)

    fused = sorted(
        scores.items(),
        key=lambda pair: (-pair[1], pair[0]),
    )

    if top_k is not None:
        fused = fused[:top_k]

    return fused