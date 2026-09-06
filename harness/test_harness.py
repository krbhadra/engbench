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


def test_parse_artifact_garbage():
    assert run_eval.parse_artifact("no json here") is None
    assert run_eval.parse_artifact(None) is None


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} checks ran")
