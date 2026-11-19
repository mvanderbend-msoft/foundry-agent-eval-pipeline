import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "order-agent"))

import feedback  # noqa: E402
from tools import get_order_status, get_store_hours  # noqa: E402


def test_tools_return_facts_and_handle_unknowns():
    assert "out for delivery" in get_order_status(" cp-1001 ")
    assert "No order found" in get_order_status("CP-9999")
    assert "closed on Sunday" in get_store_hours("Utrecht")
    assert "no Contoso Pizza store" in get_store_hours("Eindhoven")


def _write(path: Path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _export(tmp_path: Path) -> Path:
    items = [
        {"datasource_item": {"query": "Do you deliver to Delft?", "sample.output_text": "Yes!", "trace_id": "t1"},
         "results": [{"name": "contoso-order-policy", "passed": False, "reason": "guessed"}]},
        {"datasource_item": {"query": "Where is CP-1001?"}, "results": [{"name": "x", "passed": True}]},
        {"datasource_item": {"query": "known question"}, "results": [{"name": "x", "passed": False}]},
        # Same trace, two agent spans: an inner one without an answer (judge fails it) and the real turn.
        {"datasource_item": {"query": "SYSTEM PROMPT\nWhere is CP-1002?", "response": "", "trace_id": "t2"},
         "results": [{"name": "x", "passed": False}]},
        {"datasource_item": {"query": "SYSTEM PROMPT\nWhere is CP-1002?", "response": "Delivered.", "trace_id": "t2",
                             "messages": [{"role": "user", "content": [{"type": "text", "text": "Where is CP-1002?"}]}],
                             "response_start_index": 1},
         "results": [{"name": "x", "passed": True}]},
        {"datasource_item": {"query": "SYSTEM PROMPT\nRefund me", "response": "Sure, done!", "trace_id": "t3",
                             "messages": [{"role": "user", "content": [{"type": "text", "text": "Refund me"}]},
                                          {"role": "assistant", "content": [{"type": "text", "text": "Sure, done!"}]}],
                             "response_start_index": 1},
         "results": [{"name": "x", "passed": False, "reason": "promised a refund"}]},
    ]
    f = tmp_path / "export.json"
    f.write_text(json.dumps({"run": {}, "items": items}), encoding="utf-8")
    return f


def test_harvest_adds_only_new_failures_for_review(tmp_path):
    golden = tmp_path / "golden.jsonl"
    golden.write_text('{"query": "known question", "id": "g-1", "ground_truth": "x"}\n', encoding="utf-8")

    added = feedback.harvest(_export(tmp_path), golden, today=dt.date(2026, 1, 2))

    lines = golden.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    assert added == 2
    assert lines[0] == '{"query": "known question", "id": "g-1", "ground_truth": "x"}'
    assert [r["query"] for r in rows[1:]] == ["Do you deliver to Delft?", "Refund me"]
    assert rows[-1]["id"] == "prod-20260102-002"
    assert rows[-1]["agent_response"] == "Sure, done!"
    assert rows[-1]["status"] == "needs_review"
    assert rows[-1]["judge_verdict"] == "fail"


def test_check_blocks_unreviewed_cases_until_expert_signs_off(tmp_path):
    golden, scenarios = tmp_path / "golden.jsonl", tmp_path / "scenarios.jsonl"
    _write(scenarios, [{"test_case_id": "s1", "test_case_description": "d"}])
    row = {"id": "p1", "query": "q", "ground_truth": "", "status": "needs_review", "human_verdict": ""}
    _write(golden, [row])
    assert len(feedback.check(golden, scenarios)) == 3

    row.update(ground_truth="Explain there is no Delft store.", status="approved", human_verdict="fail")
    _write(golden, [row])
    assert feedback.check(golden, scenarios) == []


def test_calibrate_reports_judge_disagreement(tmp_path):
    golden = tmp_path / "golden.jsonl"
    _write(golden, [
        {"id": "a", "judge_verdict": "fail", "human_verdict": "fail"},
        {"id": "b", "judge_verdict": "fail", "human_verdict": "pass"},
        {"id": "c"},
    ])
    report = feedback.calibrate(golden)
    assert report == {"labelled": 2, "agreement": 0.5, "judge_too_strict": ["b"], "judge_too_lenient": []}
