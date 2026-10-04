# EngBench

A benchmark for LLM engineering reasoning that grades **design artifacts**
with real solvers — not an LLM judge — and scores every model two ways:
**single-shot** (one answer, no tools) and **agentic** (a Python tool to
compute and self-check, plus a grader that says which check failed).

See [VISION.md](VISION.md) for why this exists, the two-track design, and
what's in/out of scope.

## How it works

1. A task (`tasks/*.json`) describes an engineering problem in plain language
   plus machine-checkable constraints.
2. A model reads the task and produces a design artifact — component
   placements (mechanical), a SPICE netlist (electrical), or both (combined).
3. A grader in `solvers/` (one module per domain) checks the artifact
   against the task's constraints and returns pass/fail + a list of
   violations. No LLM is involved in grading. Generated families
   (`pe_cooling`, `coolant_loop`) also carry an objective: the design must be
   within a stated tolerance of the brute-force optimum, not merely feasible.
4. On the **single-shot** track the model gets one response. On the
   **agentic** track the model gets `run_python` (standard library, no network,
   up to 15 runs) and `grade` (up to 5 calls), and the grader reports which
   checks failed without the numbers (`--feedback full` restores them).

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
Optional mechanical keys, used by the harder tasks:
```json
{
  "fixed":        [{ "id": "usb_conn", "position": [0, 50, 0] }],
  "keep_out":     [{ "id": "boss", "min": [65, 40, 0], "max": [85, 60, 40] }],
  "max_distance": [{ "pair": ["usb_conn", "mcu"], "distance": 30 }]
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
  "required_elements": [{ "name": "V1", "nodes": ["vin", "0"], "value": 12 }],
  "voltage_checks": [{ "node": "vout", "min": 5, "max": 7 }],
  "drop_checks": [{ "between": ["vin", "vout"], "min_drop": 0, "max_drop": 7 }]
}
```
`required_elements` pins the source and any fixed loads so the model cannot
redefine the problem. Current limits are expressed as the drop across a
required sense resistor.

Expected model output:
```json
{ "netlist": "V1 vin 0 DC 12\nR1 vin vout 100\nR2 vout 0 100" }
```

**Combined** (`domain: "combined"`) carries both sections (including
`required_elements`) plus a `wires` list that couples them:
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

**Generated families** (`domain: "pe_cooling"`, `"coolant_loop"`) are produced
by `taskgen/<family>.py --seeds ...`. Each seed perturbs every parameter,
brute-forces the whole design space with the grader, calibrates the limits so
0.2-3% of designs are feasible, stores the optimum under `objective`, and
rejects seeds where the objective is trivial. The task text states the full
physics model, the catalogs, the constraints, and the objective; the model
returns a small JSON design (see `output_shape` in the task). Rules are in
[docs/TASK_STANDARD.md](docs/TASK_STANDARD.md).

- `pe_cooling` (electronics + thermal + fluids): switching frequency,
  inductor, heat sink, fan for a buck converter in an enclosure; minimize
  component cost.
- `coolant_loop` (thermal + fluids): coolant, pump, pump speed, channel
  diameter, parallel channels for a battery module cold plate; minimize pump
  power. Property tables come from CoolProp at generation time.
- `bess` (electrical + electronics + thermal + systems, **knowledge-required**):
  a grid-connected LFP storage system from cells to the MV connection. The
  task names the rules (IEC 60269-7, IEC 61660-1, DIN VDE 0298-4 with
  IEC 60364-4-43, VDE-AR-N 4110, IEC 60076-11, PNNL and NASA definitions)
  and gives the data; the grader implements them. Eleven decisions, nine
  closure checks, minimize total price. Spec: `docs/families/bess.md`.

## Setup

```bash
pip install -r requirements.txt
```

The electrical grader shells out to the `ngspice` CLI — install it from
[ngspice.sourceforge.io](https://ngspice.sourceforge.io) (or
`choco install ngspice` / `apt install ngspice` / `brew install ngspice`)
and make sure `ngspice` is on your PATH. Every other grader is stdlib.
Generating new `coolant_loop` seeds needs `pip install CoolProp` (grading
does not).

Model calls go through one of two transports:

- **OpenRouter** (default): any model, native tool calls. Put your key in a
  `.env` file at the repo root as `OPENROUTER_API_KEY=sk-or-...` and turn on
  OpenRouter's no-logging provider filter so the tasks don't leak into
  anyone's training data.
- **claude-cli**: Claude models on a Claude subscription via the `claude` CLI
  in headless mode. Built-in tools, MCP servers, skills and settings are all
  disabled so the model sees only the task. The agentic loop is a text
  protocol (a fenced Python block runs; a JSON object is graded; DONE stops)
  instead of native tool calls, and extended thinking is on by default. Results are labeled
  `[claude-cli]` so they are never mixed with API runs.

## Running the self-checks

```bash
python solvers/test_solvers.py
python harness/test_harness.py
```

Every task has a golden solution that must pass and at least one broken
solution that must fail, all in `solvers/solutions.json`. Electrical checks
are skipped when ngspice is missing.

## Running the eval

One model, one track:
```bash
python harness/run_eval.py --track single-shot --model anthropic/claude-...
python harness/run_eval.py --track agentic --model anthropic/claude-... --provider Fireworks
python harness/run_eval.py --transport claude-cli --track agentic --model sonnet
python harness/leaderboard.py
```
Everything (edit the `MODELS` list in `harness/run_all.py` first, and verify
the ids on openrouter.ai/models):
```bash
python harness/run_all.py --trials 1                 # smoke run
python harness/run_all.py                            # full 3-trial run
python harness/run_all.py --transport claude-cli     # Claude models on a subscription
```
Runs are resumable: records already in the results file are skipped.

Results land in `results/` as one JSON file per model per track, with the
full attempt trajectory for every trial. The leaderboard script prints
single-shot pass rate beside the agentic first-design rate, plus the gap.

## Results page

```bash
python harness/report.py
```

Renders every file in `results/` into `docs/index.html`: leaderboard, pass
rate by family and track, and a per-task matrix where each mark opens the
model's design and the grader's violations. Static, no dependencies. `docs/`
is what GitHub Pages serves, so the same file is the public site.

## Metrics

Agentic headline: first-design pass rate (the first graded design passes);
passing within 5 grader calls saturates for strong models, so it sits beside
it. Also per model, per track: pass rate over 3 trials, pass^3, grader calls
to pass, mean tokens and cost per task. See VISION.md for the
reasoning behind the budget.

## Status

- [x] Task schema
- [x] Mechanical grader (validated against golden + broken solutions)
- [x] Electrical grader (validated against ngspice 47: 12 goldens pass, 17 broken fail)
- [x] Combined grader (wire-resistance coupling, validated the same way)
- [x] Full 30-task set: 12 mechanical, 12 electrical, 6 combined, each with golden + broken solutions
- [x] Harness: single-shot runner, agentic runner, run-all, leaderboard (live-tested on the claude-cli transport; OpenRouter transport pending a key)
- [x] `pe_cooling` family: 26 tasks; feasibility alone was saturated by every model, the cost objective is not
- [x] `coolant_loop` family: 32 tasks, self-checked; model runs pending
- [x] `bess` family: 17 tasks, self-checked; first knowledge-required systems chain
- [ ] Thermal, controls, fluids single-discipline families from the source survey
- [ ] Results + writeup

## License

MIT — see [LICENSE](LICENSE).
