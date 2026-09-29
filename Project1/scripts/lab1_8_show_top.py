import json
import sys
from pathlib import Path


def main() -> None:
    qid = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    path = Path("data/processed/lab1_8_dense_results.jsonl")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record["query_id"] != qid:
            continue

        print(record["query_id"], "|", record["query"])
        for hit in record["results"][:n]:
            print(f"  {hit['rank']}. score={hit['score']:.4f} title={hit['title']!r}")
            print(f"     text={hit['text'][:100]!r}")
        return

    print(f"Запрос {qid} не найден в результатах")


if __name__ == "__main__":
    main()