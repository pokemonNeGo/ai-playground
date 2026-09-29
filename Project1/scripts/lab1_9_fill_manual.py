from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple

LINE_RE = re.compile(
    r"^\s*(?P<qid>q\d+)\s+(?P<method>bm25|dense|hybrid)\s*:\s*(?P<values>.+?)\s*$"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fill relevance column of Lab 1.9 manual template from agent scores file"
    )
    p.add_argument(
        "--analys",
        default="data/processed/lab1_9_analys.json",
        help="Text file with lines like: q01 bm25: 2,2,0,1,0,0,0,0,0,1",
    )
    p.add_argument(
        "--template",
        default="data/processed/lab1_9_manual_template.csv",
        help="Template CSV with empty relevance column",
    )
    p.add_argument(
        "--out",
        default="data/processed/lab1_9_manual_scores.csv",
        help="Output filled CSV",
    )
    return p.parse_args()


def parse_analys(path: Path) -> Dict[Tuple[str, str], List[int]]:
    if not path.exists():
        raise FileNotFoundError(f"Analys file not found: {path}")

    scores: Dict[Tuple[str, str], List[int]] = {}

    for line_no, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line:
            continue

        m = LINE_RE.match(line)
        if m is None:
            raise ValueError(f"{path} line {line_no}: cannot parse: {line!r}")

        qid = m.group("qid")
        method = m.group("method")
        raw_values = [v.strip() for v in m.group("values").split(",") if v.strip()]
        values = [int(v) for v in raw_values]

        if len(values) != 10:
            raise ValueError(
                f"{path} line {line_no}: expected 10 scores, got {len(values)}"
            )

        key = (qid, method)
        if key in scores:
            raise ValueError(f"{path} line {line_no}: duplicate pair {key}")

        scores[key] = values

    return scores


def main() -> None:
    args = parse_args()

    scores = parse_analys(Path(args.analys))
    print(f"Parsed score groups: {len(scores)} (expected 60 = 20 queries x 3 methods)")

    template_path = Path(args.template)
    if not template_path.exists():
        raise FileNotFoundError(f"Template CSV not found: {template_path}")

    with template_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "relevance" not in fieldnames:
        raise ValueError("Template CSV has no 'relevance' column")

    used_keys = set()
    filled = 0

    for row in rows:
        key = (row["query_id"].strip(), row["method"].strip())
        rank = int(row["rank"])

        values = scores.get(key)
        if values is None:
            raise ValueError(f"Template row has no scores in analys file: {key}")
        if not (1 <= rank <= len(values)):
            raise ValueError(f"Bad rank {rank} for {key}")

        row["relevance"] = str(values[rank - 1])
        used_keys.add(key)
        filled += 1

    missing = set(scores) - used_keys
    if missing:
        raise ValueError(f"Analys groups not found in template: {sorted(missing)}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Filled rows: {filled} (expected 600 = 20 x 3 x 10)")
    print(f"Saved: {out_path}")
    print("Next step:")
    print(f"  python -m scripts.lab1_9_eval_manual --input {out_path}")


if __name__ == "__main__":
    main()