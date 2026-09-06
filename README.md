# EngBench

A benchmark for LLM engineering reasoning that grades **design artifacts**
with real solvers — not an LLM judge.

See [VISION.md](VISION.md) for why this exists and what's in/out of scope.

## How it works

1. A task (`tasks/*.json`) describes an engineering problem in plain language
   plus machine-checkable constraints.
2. A model reads the task and produces a design artifact — component
   placements (mechanical) or a SPICE netlist (electrical).
3. A grader (`solvers/mechanical.py` or `solvers/electrical.py`) checks the
   artifact against the task's constraints and returns pass/fail + a list of
   violations. No LLM is involved in grading.

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

**Combined** tasks (`domain: "combined"`) carry both a mechanical and an
electrical section and must pass both graders.

## Setup

```bash
pip install -r requirements.txt
```

The electrical grader shells out to the `ngspice` CLI — install it from
[ngspice.sourceforge.io](https://ngspice.sourceforge.io) and make sure
`ngspice` is on your PATH. The mechanical grader has no external dependency.

## Running the self-checks

```bash
cd solvers
python test_solvers.py
```

## Running the full eval

```bash
python harness/run_eval.py
```

Results land in `results/` as one JSON file per model with per-task
pass/fail and violation detail, plus a leaderboard summary printed to stdout.

## Status

- [x] Task schema
- [x] Mechanical grader (validated against golden + broken solutions)
- [ ] Electrical grader (implemented, pending ngspice validation)
- [ ] Full 30-task set (3 example tasks so far)
- [ ] Model harness (API wiring)
- [ ] Results + leaderboard

## License

MIT — see [LICENSE](LICENSE).
