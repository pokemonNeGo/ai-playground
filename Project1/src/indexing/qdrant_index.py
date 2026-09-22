from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams


POINT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "project1.rag.chunk")


def make_point_id(chunk_id: str) -> str:
    """
    Создаёт детерминированный UUID для точки Qdrant из chunk_id.

    Повторный запуск скрипта не создаёт дубли,
    а обновляет те же самые точки.
    """
    return str(uuid.uuid5(POINT_NAMESPACE, chunk_id))


def get_qdrant_client(
    mode: str = "server",
    host: str = "localhost",
    port: int = 6333,
    path: str = "data/qdrant_storage",
) -> QdrantClient:
    """
    Создаёт клиент Qdrant.

    mode:
      - server: подключение по host/port (Docker)
      - local: локальное файловое хранилище
    """
    mode = (mode or "server").lower()

    if mode in {"local", "file", "embedded"}:
        return QdrantClient(path=path)

    return QdrantClient(host=host, port=port, timeout=60)


def collection_exists(client: QdrantClient, collection_name: str) -> bool:
    """
    Проверяет, существует ли коллекция.
    """
    try:
        return bool(client.collection_exists(collection_name))
    except Exception:
        collections = client.get_collections().collections
        return any(item.name == collection_name for item in collections)


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int) -> None:
    """
    Создаёт коллекцию, если её ещё нет.
    """
    if not collection_exists(client, collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def recreate_collection(client: QdrantClient, collection_name: str, vector_size: int) -> None:
    """
    Удаляет и заново создаёт коллекцию.

    Используй, если поменялась модель или размерность вектора.
    """
    if collection_exists(client, collection_name):
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def build_points(
    rows: List[Dict[str, Any]],
    vectors,
    model_name: str,
    default_strategy: str,
    embedded_at: str,
) -> List[PointStruct]:
    """
    Собирает точки Qdrant из строк SQLite и векторов.
    """
    points: List[PointStruct] = []

    for row, vector in zip(rows, vectors):
        try:
            chunk_meta = json.loads(row.get("metadata_json") or "{}")
        except json.JSONDecodeError:
            chunk_meta = {"parse_error": True}

        payload = {
            "chunk_id": row["chunk_id"],
            "doc_id": row["doc_id"],
            "title": row.get("title"),
            "source": row.get("source"),
            "chunk_index": row["chunk_index"],
            "start_char": row["start_char"],
            "end_char": row["end_char"],
            "text": row["text"],
            "chunking_strategy": chunk_meta.get("chunking_strategy", default_strategy),
            "chunk_metadata": chunk_meta,
            "embedding_model": model_name,
            "embedded_at": embedded_at,
        }

        points.append(
            PointStruct(
                id=make_point_id(row["chunk_id"]),
                vector=vector.tolist(),
                payload=payload,
            )
        )

    return points