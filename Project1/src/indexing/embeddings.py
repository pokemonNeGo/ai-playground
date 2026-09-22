from __future__ import annotations

from typing import List, Optional

from sentence_transformers import SentenceTransformer


def uses_e5_prefix(model_name: str) -> bool:
    """
    Возвращает True, если используется мультиязычная e5-модель,
    для которой нужны префиксы passage/query.
    """
    name = model_name.lower()
    return "e5" in name and "multilingual" in name


def prepare_doc_texts(texts: List[str], model_name: str) -> List[str]:
    """
    Готовит тексты документов/чанков к эмбеддингу.

    Для multilingual-e5 добавляет префикс 'passage: '.
    В payload сохраняем чистый текст без префикса.
    """
    prefix = "passage: " if uses_e5_prefix(model_name) else ""
    return [prefix + text.strip() for text in texts]


def load_embedding_model(model_name: str, device: Optional[str] = None) -> SentenceTransformer:
    """
    Загружает модель эмбеддингов.

    model_name: например 'BAAI/bge-m3' или 'intfloat/multilingual-e5-base'
    device: 'cpu', 'cuda' или None для автоопределения
    """
    return SentenceTransformer(model_name, device=device)


def encode_batch(
    model: SentenceTransformer,
    texts: List[str],
    model_name: str,
    batch_size: int = 32,
    normalize: bool = True,
):
    """
    Кодирует список текстов в векторы.

    Возвращает numpy-массив формы (len(texts), vector_size).
    """
    prepared_texts = prepare_doc_texts(texts, model_name)

    return model.encode(
        prepared_texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=normalize,
    )


def get_vector_size(model: SentenceTransformer, model_name: str) -> int:
    """
    Определяет размерность вектора для модели.
    """
    vector = encode_batch(
        model,
        ["тестовый текст для определения размерности"],
        model_name,
        batch_size=1,
        normalize=True,
    )
    return int(vector.shape[1])