"""Self-check for the harness loop, no API calls: a stub model that fails once then fixes itself.

Run with: python harness/test_harness.py
"""
import json
from pathlib import Path

import run_eval

TASK = json.loads((Path(__file__).parent.parent / "tasks" / "mech_001.json").read_text())
BAD = {"placements": [{"id": "comp_a", "position": [0, 0, 0]}, {"id": "comp_b", "position": [10, 0, 0]},
                      {"id": "comp_c", "position": [0, 40, 0]}]}
GOOD = {"placements": [{"id": "comp_a", "position": [0, 0, 0]}, {"id": "comp_b", "position": [50, 0, 0]},
                       {"id": "comp_c", "position": [0, 40, 0]}]}


def _resp(content=None, tool_artifact=None):
    msg = {"role": "assistant", "content": content}
    if tool_artifact is not None:
        msg["tool_calls"] = [{"id": "c1", "type": "function", "function": {
            "name": "grade", "arguments": json.dumps({"artifact": tool_artifact})}}]
    return {"choices": [{"message": msg}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001},
            "provider": "Stub", "model": "stub/model"}


def stub_chat(model, messages, tools=None, *, opts):
    if tools is None:  # single-shot
        return _resp(content="```json\n" + json.dumps(GOOD) + "\n```")
    seen = sum(m.get("role") == "tool" for m in messages)
    if seen == 0:
        return _resp(tool_artifact=BAD)
    if seen == 1:
        return _resp(tool_artifact=GOOD)
    return _resp(content="done")


def test_single_shot_parses_fenced_json():
    rec = run_eval.run_single_shot("stub", TASK, {}, chat=stub_chat)
    assert rec["passed"] is True, rec
    assert rec["usage"]["cost"] == 0.001


def test_agentic_recovers_on_second_attempt():
    rec = run_eval.run_agentic("stub", TASK, {}, chat=stub_chat)
    assert rec["passed"] is True, rec
    assert [a["passed"] for a in rec["attempts"]] == [False, True]
    assert rec["provider"] == "Stub"


def test_agentic_budget_cap():
    def always_bad(model, messages, tools=None, *, opts):
        return _resp(tool_artifact=BAD)
    rec = run_eval.run_agentic("stub", TASK, {}, chat=always_bad)
    assert rec["passed"] is False
    assert len(rec["attempts"]) == run_eval.MAX_ATTEMPTS


def test_agentic_python_then_grade():
    def with_python(model, messages, tools=None, *, opts):
        seen = [m for m in messages if m.get("role") == "tool"]
        if not seen:
            return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{
                "id": "p1", "type": "function", "function": {"name": "run_python", "arguments": json.dumps({"code": "print(6*7)"})}}]}}],
                "usage": {}, "provider": "Stub", "model": "stub/model"}
        if len(seen) == 1:
            assert seen[0]["content"].strip() == "42", seen[0]
            return _resp(tool_artifact=GOOD)
        return _resp(content="done")
    rec = run_eval.run_agentic("stub", TASK, {}, chat=with_python)
    assert rec["passed"] is True and rec["python_calls"] == 1, rec


def test_test_report_hides_cause_and_numbers():
    bess_task = json.loads((Path(__file__).parent.parent / "tasks" / "bess_001.json").read_text())
    out = run_eval.grader.report(bess_task, ["fuse breaking capacity 100 kA is below the prospective bus fault current 121.4 kA",
                                             "fuse rating 400 A exceeds the corrected cable ampacity I_z 261.0 A"])
    assert out == ["Short-circuit test at the DC bus: a string fuse failed to interrupt and ruptured.",
                   "Overload trial: a string cable overheated before its fuse operated."], out
    mech = run_eval.grader.report(TASK, ["comp_a overlaps comp_b by 4.5 mm"])  # component level: numbers stripped
    assert not any(ch.isdigit() for v in mech for ch in v), mech


def test_python_block_formats():
    assert run_eval.python_block("Let me check.\n```python\nprint(1)\n```") == "print(1)\n"
    assert run_eval.python_block('<invoke name="python">\n<parameter name="code">print(2)</parameter>\n</invoke>\n_x') == "print(2)"
    assert run_eval.python_block('<ns:parameter name="code">print(3)</ns:parameter>') == "print(3)"
    assert run_eval.python_block('{"cells_series": 400}') is None


def test_parse_artifact_garbage():
    assert run_eval.parse_artifact("no json here") is None
    assert run_eval.parse_artifact(None) is None


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} checks ran")
