# EngBench

A benchmark for LLM engineering reasoning that grades **design artifacts**
with real solvers — not an LLM judge — and scores every model two ways:
**single-shot** (raw reasoning) and **agentic** (iterating against solver
feedback).

See [VISION.md](VISION.md) for why this exists, the two-track design, and
what's in/out of scope.

## How it works

1. A task (`tasks/*.json`) describes an engineering problem in plain language
   plus machine-checkable constraints.
2. A model reads the task and produces a design artifact — component
   placements (mechanical), a SPICE netlist (electrical), or both (combined).
3. A grader (`solvers/mechanical.py` or `solvers/electrical.py`) checks the
   artifact against the task's constraints and returns pass/fail + a list of
   violations. No LLM is involved in grading.
4. On the **single-shot** track the model gets one response. On the
   **agentic** track the model gets a `grade` tool that returns the violation
   list, and up to 5 calls to converge.

## Task schema

**Mechanical** (`domain: "mechanical"`)
```json
{
  "id": "mech_001",
  "domain": "mechanical",
  "description": "plain-language problem statement",
  "enclosure": { "size": [x, y, z] },
  "components": [{ "id": "comp_a", "size": [w, d, h] }],
  "min_clearance": [{ "pair": ["comp_a", "comp_b"], "distance": 15 }]
}
```
Expected model output:
```json
{ "placements": [{ "id": "comp_a", "position": [x, y, z] }] }
```

**Electrical** (`domain: "electrical"`)
```json
{
  "id": "elec_001",
  "domain": "electrical",
  "description": "plain-language problem statement",
  "voltage_checks": [{ "node": "vout", "min": 5, "max": 7 }],
  "drop_checks": [{ "between": ["vin", "vout"], "max_drop": 7 }]
}
```
Expected model output:
```json
{ "netlist": "V1 vin 0 DC 12\nR1 vin vout 100\nR2 vout 0 100" }
```

**Combined** (`domain: "combined"`) carries both sections plus a `wires`
list that couples them:
```json
{
  "wires": [
    { "from": "psu", "to": "load", "nodes": ["psu_out", "load_in"], "ohms_per_mm": 0.002 }
  ]
}
```
The model outputs both `placements` and `netlist`. The grader measures the
distance between the placed components, computes the wire resistance,
inserts it between the named nodes, and only then simulates. A layout that
puts the load far from the supply fails the drop check — the model cannot
claim a shorter wire than its own placement implies.

## Setup

```bash
pip install -r requirements.txt
```

The electrical grader shells out to the `ngspice` CLI — install it from
[ngspice.sourceforge.io](https://ngspice.sourceforge.io) (or
`choco install ngspice` / `apt install ngspice` / `brew install ngspice`)
and make sure `ngspice` is on your PATH. The mechanical grader has no
external dependency.

Model calls go through [OpenRouter](https://openrouter.ai). Put your key in
a `.env` file at the repo root:
```
OPENROUTER_API_KEY=sk-or-...
```
Turn on OpenRouter's no-logging provider filter before running so the tasks
don't leak into anyone's training data.

## Running the self-checks

```bash
python solvers/test_solvers.py
python harness/test_harness.py
```

Every task has a golden solution that must pass and at least one broken
solution that must fail.

## Running the eval

```bash
python harness/run_eval.py --track single-shot --model anthropic/claude-...
python harness/run_eval.py --track agentic --model anthropic/claude-...
python harness/leaderboard.py
```

Results land in `results/` as one JSON file per model per track, with the
full attempt trajectory for every trial. The leaderboard script prints
single-shot and agentic pass rates side by side, plus the gap.

## Metrics

Per model, per track: mean pass rate over 3 trials, pass^3, mean attempts to
first pass (agentic), mean tokens and cost per task. See VISION.md for the
reasoning behind the budget.

## Status

- [x] Task schema
- [x] Mechanical grader (validated against golden + broken solutions)
- [ ] Electrical grader (implemented, pending ngspice validation)
- [x] Combined grader (wire-resistance coupling, pending ngspice validation)
- [ ] Full 30-task set (4 example tasks so far)
- [x] Harness: single-shot runner, agentic runner, leaderboard (stub-tested, pending first live run)
- [ ] Results + writeup

## License

MIT — see [LICENSE](LICENSE).
