"""Close the loop between production and the golden dataset.

  check      Fail if the golden dataset has unreviewed or incomplete cases.
  harvest    Add failing production conversations to the golden dataset for expert review.
  calibrate  Compare the judge's verdicts with the experts' verdicts.
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "datasets" / "golden.jsonl"
SCENARIOS = ROOT / "datasets" / "scenarios.jsonl"
VERDICTS = {"pass", "fail"}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path.name}:{n}: invalid JSON ({e})")
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def check(golden: Path = GOLDEN, scenarios: Path = SCENARIOS) -> list[str]:
    errors = []
    seen = set()
    for row in read_jsonl(golden):
        rid = row.get("id", "<no id>")
        if rid in seen:
            errors.append(f"{rid}: duplicate id")
        seen.add(rid)
        if not str(row.get("query", "")).strip():
            errors.append(f"{rid}: missing query")
        if not str(row.get("ground_truth", "")).strip():
            errors.append(f"{rid}: missing ground_truth (the expected behaviour)")
        if row.get("status") == "needs_review":
            errors.append(f"{rid}: waiting for expert review")
        if "human_verdict" in row and row["human_verdict"] not in VERDICTS:
            errors.append(f"{rid}: human_verdict must be 'pass' or 'fail'")
    for row in read_jsonl(scenarios):
        if not row.get("test_case_id") or not row.get("test_case_description"):
            errors.append(f"scenario {row}: needs test_case_id and test_case_description")
    return errors


def _query(item: dict) -> str:
    if item.get("query"):
        q = item["query"]
        return q if isinstance(q, str) else json.dumps(q, ensure_ascii=False)
    for m in item.get("messages") or []:
        if m.get("role") == "user":
            c = m.get("content")
            return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
    return ""


def harvest(export_file: Path, golden: Path = GOLDEN, today: dt.date | None = None) -> int:
    """Append failing production rows as 'needs_review' cases. Returns how many were added."""
    today = today or dt.date.today()
    rows = read_jsonl(golden)
    known = {r.get("query") for r in rows}
    items = json.loads(export_file.read_text(encoding="utf-8")).get("items", [])
    added = 0
    for item in items:
        failed = [r for r in item.get("results", []) if r.get("passed") is False]
        if not failed:
            continue
        src = item.get("datasource_item", {})
        query = _query(src)
        if not query or query in known:
            continue
        known.add(query)
        added += 1
        rows.append({
            "id": f"prod-{today:%Y%m%d}-{added:03d}",
            "query": query,
            "agent_response": src.get("sample.output_text") or src.get("response", ""),
            "judge_verdict": "fail",
            "judge_reason": " | ".join(f"{r.get('name')}: {r.get('reason', '')}" for r in failed),
            "trace_id": src.get("trace_id", ""),
            "status": "needs_review",
            "human_verdict": "",
            "ground_truth": "",
        })
    if added:
        write_jsonl(golden, rows)
    return added


def calibrate(golden: Path = GOLDEN) -> dict:
    labelled = [r for r in read_jsonl(golden) if r.get("judge_verdict") in VERDICTS and r.get("human_verdict") in VERDICTS]
    agree = sum(r["judge_verdict"] == r["human_verdict"] for r in labelled)
    false_fail = [r["id"] for r in labelled if r["judge_verdict"] == "fail" and r["human_verdict"] == "pass"]
    false_pass = [r["id"] for r in labelled if r["judge_verdict"] == "pass" and r["human_verdict"] == "fail"]
    return {
        "labelled": len(labelled),
        "agreement": round(agree / len(labelled), 3) if labelled else None,
        "judge_too_strict": false_fail,
        "judge_too_lenient": false_pass,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    h = sub.add_parser("harvest")
    h.add_argument("export_file", type=Path, help="Output of 'azd ai eval run output export'")
    sub.add_parser("calibrate")
    a = p.parse_args()

    if a.cmd == "check":
        errors = check()
        for e in errors:
            print(f"::error::{e}")
        if errors:
            sys.exit(1)
        print(f"Golden dataset OK ({len(read_jsonl(GOLDEN))} signed-off cases).")
    elif a.cmd == "harvest":
        print(f"Added {harvest(a.export_file)} production cases for expert review.")
    else:
        print(json.dumps(calibrate(), indent=2))


if __name__ == "__main__":
    main()
