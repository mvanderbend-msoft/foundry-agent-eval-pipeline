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


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return " ".join(c.get("text", "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text")


def _query(item: dict) -> str:
    # Trace rows put the system prompt in front of the question in 'query'; the user turn in 'messages' is clean.
    for m in reversed((item.get("messages") or [])[: item.get("response_start_index")]):
        if m.get("role") == "user" and _text(m.get("content")).strip():
            return _text(m["content"]).strip()
    q = item.get("query")
    return q if isinstance(q, str) or q is None else json.dumps(q, ensure_ascii=False)


def _response(item: dict) -> str:
    return item.get("sample.output_text") or item.get("response") or ""


def _one_per_trace(items: list[dict]) -> list[dict]:
    """One trace can yield several agent spans; keep the one that holds the final answer."""
    best: dict[str, dict] = {}
    for n, item in enumerate(items):
        key = item.get("datasource_item", {}).get("trace_id") or f"row-{n}"
        if key not in best or len(_response(item["datasource_item"])) > len(_response(best[key]["datasource_item"])):
            best[key] = item
    return list(best.values())


def harvest(export_file: Path, golden: Path = GOLDEN, today: dt.date | None = None) -> int:
    """Append failing production rows as 'needs_review' cases. Returns how many were added."""
    today = today or dt.date.today()
    known = {r.get("query") for r in read_jsonl(golden)}
    items = json.loads(export_file.read_text(encoding="utf-8")).get("items", [])
    new_rows = []
    for item in _one_per_trace(items):
        failed = [r for r in item.get("results", []) if r.get("passed") is False]
        if not failed:
            continue
        src = item.get("datasource_item", {})
        query = _query(src)
        if not query or query in known:
            continue
        known.add(query)
        new_rows.append({
            "id": f"prod-{today:%Y%m%d}-{len(new_rows) + 1:03d}",
            "query": query,
            "agent_response": _response(src),
            "judge_verdict": "fail",
            "judge_reason": " | ".join(f"{r.get('name')}: {r.get('reason', '')}" for r in failed),
            "trace_id": src.get("trace_id", ""),
            "status": "needs_review",
            "human_verdict": "",
            "ground_truth": "",
        })
    if new_rows:
        # Append only, so the review PR shows just the new cases.
        text = golden.read_text(encoding="utf-8")
        sep = "" if not text or text.endswith("\n") else "\n"
        with golden.open("a", encoding="utf-8", newline="\n") as f:
            f.write(sep + "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in new_rows))
    return len(new_rows)


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
