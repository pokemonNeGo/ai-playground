from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from src.indexing.embeddings import load_embedding_model, uses_e5_prefix
from src.indexing.qdrant_index import get_qdrant_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Qdrant collection and run sample search")

    parser.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION", "rag_documents"))
    parser.add_argument("--model", default=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"))
    parser.add_argument("--device", default=os.getenv("EMBEDDING_DEVICE", ""))
    parser.add_argument("--query", default="Что такое Википедия?")
    parser.add_argument("--qdrant-mode", default=os.getenv("QDRANT_MODE", "server"))
    parser.add_argument("--qdrant-host", default=os.getenv("QDRANT_HOST", "localhost"))
    parser.add_argument("--qdrant-port", type=int, default=int(os.getenv("QDRANT_PORT", "6333")))
    parser.add_argument("--qdrant-local-path", default=os.getenv("QDRANT_LOCAL_PATH", "data/qdrant_storage"))
    parser.add_argument("--limit", type=int, default=5)

    return parser.parse_args()


def main() -> None:
    load_dotenv(ROOT / ".env")
    args = parse_args()

    qdrant_local_path = args.qdrant_local_path
    if not Path(qdrant_local_path).is_absolute():
        qdrant_local_path = str((ROOT / qdrant_local_path).resolve())

    client = get_qdrant_client(
        mode=args.qdrant_mode,
        host=args.qdrant_host,
        port=args.qdrant_port,
        path=qdrant_local_path,
    )

    info = client.get_collection(args.collection)

    print("Collection:", args.collection)
    print("Points count:", info.points_count)
    print()

    model = load_embedding_model(args.model, args.device or None)

    if uses_e5_prefix(args.model):
        query_text = f"query: {args.query}"
    else:
        query_text = args.query

    query_vector = model.encode(
        [query_text],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0]

    search_url = (
        f"http://{args.qdrant_host}:{args.qdrant_port}"
        f"/collections/{args.collection}/points/search"
    )
    request_body = {
        "vector": query_vector.tolist(),
        "limit": args.limit,
        "with_payload": True,
    }
    request = urllib.request.Request(
        search_url,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        answer = json.loads(response.read().decode("utf-8"))

    results = answer.get("result", [])

    print("Query:", args.query)
    print("Prepared query:", query_text)
    print()

    if not results:
        print("No results found")
        return

    for index, item in enumerate(results, start=1):
        payload = item.get("payload") or {}

        print(f"Result {index}")
        print("score:", item.get("score"))
        print("chunk_id:", payload.get("chunk_id"))
        print("doc_id:", payload.get("doc_id"))
        print("title:", payload.get("title"))
        print("strategy:", payload.get("chunking_strategy"))
        print("text:", str(payload.get("text", ""))[:180].replace("\n", " "))
        print("-" * 80)


if __name__ == "__main__":
    main()