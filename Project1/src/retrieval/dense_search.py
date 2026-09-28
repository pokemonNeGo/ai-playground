from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class DenseHit:
    rank: int
    chunk_id: str
    doc_id: str
    title: str
    text: str
    score: float
    chunk_index: int | None = None
    start_char: int | None = None
    end_char: int | None = None
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DenseSearcher:
    """
    Плотный поиск по Qdrant через REST API.

    Используется та же эмбеддинг-модель, что и при индексации:
    BAAI/bge-m3, normalize_embeddings=True.

    Запрос эмбеддится без специальных префиксов.
    """

    def __init__(
        self,
        model_path: str | None = None,
        device: str | None = None,
        qdrant_host: str | None = None,
        qdrant_port: int | None = None,
        collection_name: str | None = None,
    ) -> None:
        load_dotenv()

        self.host = qdrant_host or os.getenv("QDRANT_HOST", "localhost")
        self.port = int(qdrant_port or os.getenv("QDRANT_PORT", "6333"))
        self.collection = collection_name or os.getenv(
            "QDRANT_COLLECTION",
            "rag_documents",
        )

        model_path = model_path or os.getenv("EMBEDDING_MODEL", "models/bge-m3")
        device = device or os.getenv("EMBEDDING_DEVICE", "cuda")

        logger.info("Loading embedding model: %s", model_path)
        logger.info("Device: %s", device)

        self.model = SentenceTransformer(model_path, device=device)

    def encode_query(self, query: str) -> list[float]:
        """
        Превращает запрос в нормализованный вектор размера 1024.
        """
        query = " ".join(query.strip().split())
        vector = self.model.encode(
            [query],
            normalize_embeddings=True,
        )[0]
        return [float(x) for x in vector]

    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> tuple[list[DenseHit], float]:
        """
        Возвращает топ-k результатов из Qdrant и время поиска в миллисекундах.
        """
        vector = self.encode_query(query)

        url = (
            f"http://{self.host}:{self.port}"
            f"/collections/{self.collection}/points/search"
        )

        body = {
            "vector": vector,
            "limit": top_k,
            "with_payload": True,
            "with_vector": False,
        }

        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        started = time.perf_counter()

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                answer = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Qdrant HTTP error {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "Qdrant недоступен. Проверь, запущен ли контейнер: docker start qdrant"
            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000.0

        points = answer.get("result", []) or []

        hits: list[DenseHit] = []

        for rank, point in enumerate(points, start=1):
            payload = point.get("payload") or {}

            hits.append(
                DenseHit(
                    rank=rank,
                    chunk_id=str(payload.get("chunk_id", point.get("id", ""))),
                    doc_id=str(payload.get("doc_id", "")),
                    title=str(payload.get("title", "")),
                    text=str(payload.get("text", "")),
                    score=float(point.get("score", 0.0)),
                    chunk_index=payload.get("chunk_index"),
                    start_char=payload.get("start_char"),
                    end_char=payload.get("end_char"),
                    payload=payload,
                )
            )

        return hits, latency_ms