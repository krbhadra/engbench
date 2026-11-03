# Level 1: component families

The physics is stated in the task. Five families: `mech` (packing), `elec` (DC circuits, graded with ngspice), `comb` (both, coupled by wire resistance), and the generated families `pe_cooling` and `coolant_loop`.

## Task schema (hand-written families: mech, elec, comb)

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
