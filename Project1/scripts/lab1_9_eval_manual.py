from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate manually judged Lab 1.9 retrieval results"
    )
    parser.add_argument("--input", default="data/processed/lab1_9_manual_template.csv")
    parser.add_argument("--metrics-csv", default="data/processed/lab1_9_metrics.csv")
    parser.add_argument("--by-query-csv", default="data/processed/lab1_9_metrics_by_query.csv")
    parser.add_argument("--markdown", default="data/processed/lab1_9_metrics.md")
    parser.add_argument("--exclude-query-ids", default="")
    parser.add_argument("--min-relevance", type=int, default=1)
    return parser.parse_args()


def parse_relevance(value: Optional[str]) -> int:
    if value is None:
        return 0
    value = str(value).strip()
    if not value:
        return 0
    try:
        return int(float(value))
    except Exception:
        return 0


def avg(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def compute_metrics_for_hits(
    hits: List[Dict[str, int]],
    min_relevance: int,
) -> Dict[str, float]:
    hits = sorted(hits, key=lambda item: item["rank"])

    relevant_at_5 = 0
    relevant_at_10 = 0

    for hit in hits:
        if hit["rank"] <= 5 and hit["rel"] >= min_relevance:
            relevant_at_5 += 1
        if hit["rank"] <= 10 and hit["rel"] >= min_relevance:
            relevant_at_10 += 1

    first_relevant_rank: Optional[int] = None
    for hit in hits:
        if hit["rel"] >= min_relevance:
            first_relevant_rank = hit["rank"]
            break

    mrr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0

    return {
        "p@5": relevant_at_5 / 5.0,
        "p@10": relevant_at_10 / 10.0,
        "mrr": mrr,
        "relevant_hits": float(relevant_at_10),
        "judged_hits": float(len(hits)),
    }


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(
            f"Manual CSV not found: {input_path}. Fill relevance column first."
        )

    exclude_ids = {
        item.strip()
        for item in args.exclude_query_ids.split(",")
        if item.strip()
    }

    groups: Dict[tuple, List[Dict[str, int]]] = defaultdict(list)
    queries: Dict[str, str] = {}
    methods = set()

    with input_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            query_id = str(row.get("query_id", "")).strip()
            query_text = str(row.get("query", "")).strip()
            method = str(row.get("method", "")).strip()

            if not query_id or not method:
                continue
            if query_id in exclude_ids:
                continue

            try:
                rank = int(row.get("rank", "0") or 0)
            except Exception:
                rank = 0
            if rank <= 0:
                continue

            rel = parse_relevance(row.get("relevance"))

            queries[query_id] = query_text
            methods.add(method)
            groups[(query_id, method)].append({"rank": rank, "rel": rel})

    if not queries:
        raise RuntimeError("No valid rows found in manual CSV")

    query_ids = sorted(queries.keys())
    method_names = sorted(methods)

    per_query_rows: List[Dict[str, object]] = []
    for query_id in query_ids:
        row: Dict[str, object] = {
            "query_id": query_id,
            "query": queries[query_id],
        }
        for method in method_names:
            metrics = compute_metrics_for_hits(
                groups.get((query_id, method), []), args.min_relevance
            )
            row[f"{method}_p@5"] = metrics["p@5"]
            row[f"{method}_p@10"] = metrics["p@10"]
            row[f"{method}_mrr"] = metrics["mrr"]
            row[f"{method}_relevant_at_10"] = metrics["relevant_hits"]
        per_query_rows.append(row)

    summary_rows: List[Dict[str, object]] = []
    for method in method_names:
        p5: List[float] = []
        p10: List[float] = []
        mrr: List[float] = []
        rel_hits: List[float] = []
        judged: List[float] = []

        for query_id in query_ids:
            metrics = compute_metrics_for_hits(
                groups.get((query_id, method), []), args.min_relevance
            )
            p5.append(metrics["p@5"])
            p10.append(metrics["p@10"])
            mrr.append(metrics["mrr"])
            rel_hits.append(metrics["relevant_hits"])
            judged.append(metrics["judged_hits"])

        summary_rows.append(
            {
                "method": method,
                "queries": len(query_ids),
                "P@5": avg(p5),
                "P@10": avg(p10),
                "MRR": avg(mrr),
                "avg_relevant_hits_at_10": avg(rel_hits),
                "avg_judged_hits": avg(judged),
            }
        )

    metrics_path = Path(args.metrics_csv)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "method",
                "queries",
                "P@5",
                "P@10",
                "MRR",
                "avg_relevant_hits_at_10",
                "avg_judged_hits",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    by_query_path = Path(args.by_query_csv)
    by_query_fields = ["query_id", "query"]
    for method in method_names:
        by_query_fields.extend(
            [
                f"{method}_p@5",
                f"{method}_p@10",
                f"{method}_mrr",
                f"{method}_relevant_at_10",
            ]
        )
    with by_query_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=by_query_fields)
        writer.writeheader()
        writer.writerows(per_query_rows)

    lines = [
        "# Lab 1.9 Manual Retrieval Metrics",
        "",
        f"Input: `{input_path}`",
        "",
        f"Excluded query ids: {', '.join(sorted(exclude_ids)) if exclude_ids else 'none'}",
        "",
        "| Method | Queries | P@5 | P@10 | MRR | Avg relevant @10 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            "| {method} | {queries} | {p5:.3f} | {p10:.3f} | {mrr:.3f} | {rel:.2f} |".format(
                method=row["method"],
                queries=row["queries"],
                p5=float(row["P@5"]),
                p10=float(row["P@10"]),
                mrr=float(row["MRR"]),
                rel=float(row["avg_relevant_hits_at_10"]),
            )
        )

    markdown_path = Path(args.markdown)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    print()
    print(f"Saved metrics CSV: {metrics_path}")
    print(f"Saved per-query CSV: {by_query_path}")
    print(f"Saved markdown: {markdown_path}")


if __name__ == "__main__":
    main()