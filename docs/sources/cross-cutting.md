# Cross-cutting — benchmarks, verification suites, datasets, solvers

## A. Existing LLM engineering benchmarks (deterministic = solver/exact/tolerance, no LLM)

| # | Source | Content | License | Grading | Deterministic | Contam. | Rank |
|---|---|---|---|---|---|---|---|
| 1 | ABench-Physics (github inclusionAI/ABench) | 400 static + 100 parameterized physics problems; "variation engine" regenerates numbers + answers | Apache-2.0 | Numeric, 1% rel tol | Yes | High static; low for variants | 5 |
| 2 | EngDesign (github AGI4Engineering/EngDesign) | 101 design tasks / 473 items, 9 domains (control, mech, structural, analog IC, digital HW, DSP, robotics...) | Not stated (check) | Simulation (SPICE, FEA, MATLAB/Cadence); 53/101 open-source graded | Yes (53) | Medium | 5 |
| 3 | AnalogCoder benchmark (used by AnalogAgent) | 24-30 analog design tasks | No LICENSE file | PySpice/ngspice testbenches | Yes | Medium | 4 |
| 4 | CircuitSense (HF) | 8,006 circuit problems; 5,020 synthetic w/ symbolic derivations | MIT | Symbolic + MC | Mostly | High (textbook half) | 4 |
| 5 | EEE-Bench (HF) | 2,860 multimodal EE problems, 10 subdomains | MIT | MC + free-form match | Mostly | High | 4 |
| 6 | EngChain / EngTrace | 90 template-generated problems, 9 domains, randomized | CC BY 4.0 | Step-level numeric 2% tol (LLM only labels error type) | Yes | Low | 4 |
| 7 | FEM-Bench (arXiv 2512.20732) | 33 FEM code-gen tasks | CC BY 4.0 (paper) | numeric match + unit tests that must FAIL on known-bad impls | Yes | Medium | 4 |
| 8 | EngiBench (IDEALLab), pip | Design-optimization problems with simulators | Code GPLv3, data CC BY-NC-SA | Simulator objective | Yes | n/a | 4 |
| 9 | UGPhysics | 5,520 undergrad physics | CC BY-NC-SA | rule-based then model-assisted | Partial | High | 3 |
| 10 | PhysReason | 1,200 olympiad problems | MIT wrapper (textbook copyright) | answer match + LLM step scoring | Answer-level | High | 3 |
| 11 | SciBench | 789 textbook problems | MIT wrapper | numeric tol | Yes | High | 3 |
| 12 | PHYSICS (Yale) | 1,297 PhD-qualifying | MIT wrapper | regex+SymPy, LLM fallback | Mostly | High | 3 |
| 13 | Omni-CAD / Text2CAD / Text2CAD-Bench / P3D-Bench | CAD gen | MIT / CC BY-NC-SA / TBD | Chamfer, IoU, executability (+VLM for top level) | Mostly | n/a | 3 |
| 14 | MMLU-Pro eng subset, GPQA-Diamond | MC | MIT / CC BY | exact match | Yes | Very high | 2 |
| 15 | MechVQA | 21K QA on drawings | Apache-2.0 | LLM judge | No | Medium | 2 |
| 16 | CircuitLM, CIRCUIT (MIT/ADI), ElecBench, MMCircuitEval, DesignQA | various | unverified / not released / DataPort | mixed, several LLM-judged | Partial | - | 2 |
| - | "ENGINEBench" | not found; likely conflation with EngiBench/EngDesign | | | | | - |

Takeaways: deterministic grading is the norm in the strongest recent work (ABench 1% tol, EngChain 2%, FEM-Bench adversarial unit tests, EngDesign simulation, AnalogCoder ngspice testbenches). EngDesign is the nearest competitor. FEM-Bench's "grader must fail on known-bad" = our golden/broken rule. ABench-Physics's variation engine = our perturbation plan, Apache-2.0 so the pattern is reusable.

## B. Solver verification suites with analytic solutions

| # | Source | Content | Openness | Rank |
|---|---|---|---|---|
| 1 | CalculiX test suite + CalculiX-Examples (Kraska) | ~1,000 .inp regression cases w/ reference outputs; NAFEMS LE1/LE10 | GPL-2 solver; conda-forge on Linux/mac/Win | 5 |
| 2 | Code_Aster Validation manual (V-docs) | 1,262 validation docs, many closed-form refs | GPL; conda-forge Linux only; heavy | 4 |
| 3 | NAFEMS Standard Benchmarks (P18) as reproduced in Abaqus Benchmarks mirrors, FeenoX, bconverged | LE1, LE10 (sigma_yy=-5.38 MPa at D), LE11, FV52, T1-T4 | P18 paid (GBP 45); reproductions free | 4 |
| 4 | ngspice tests + benchmarks (Quarles Spice3 bench, CircuitSim90, ISCAS85) | self-checking regression suite | ngspice BSD; bench suites unlicensed | 4 |
| 5 | MATPOWER test suite + case files | solved PF/OPF for case14/30/39/57/118/300 | BSD-3 code; case data per-file | 4 |
| 6 | Elmer fem/tests + nemocrys/elmer-verification | ~900 tests; analytic conduction+radiation | GPL/LGPL; no pip/conda | 3 |
| 7 | NASA Turbulence Modeling Resource | verification cases w/ grids + reference solutions | Public domain | 3 |
| 8 | NAFEMS vibration benchmarks R0015/R0016 | modal targets | paid | 2 |

## C. Open datasets, reports, catalogs, hardware

| # | Source | License | Yields | Rank |
|---|---|---|---|---|
| 1 | IEEE test systems via pandapower.networks / MATPOWER (case14/39/118/300, PEGASE, ACTIVSg) | BSD-3 code; case data per-file | power-flow, contingency, OPF tasks | 5 |
| 2 | NASA PCoE battery datasets (B0005 series, Randomized Usage 1-4) | US Gov public domain | capacity fade, SoH/RUL, ECM fitting | 4 |
| 3 | foxBMS 2 + foxBMS-hardware | SW BSD-3; HW/docs CC BY 4.0 | BOM/derating/fault-tree | 4 |
| 4 | Libre Solar (mppt-2420-hc, bms-c1) | CERN-OHL-W 2.0; KiCad + BOM CSV | power-electronics sizing, BOM costing | 4 |
| 5 | NREL/DOE/Sandia via OSTI: NREL 5-MW turbine, IEA-15-240-RWT, Sandia PV model + pvlib (BSD-3) | free; per-report license line | turbine/PV performance tasks | 4 |
| 6 | Oxford Battery Degradation Dataset 1 | ODbL + DbCL | degradation fitting | 3 |
| 7 | CALCE battery data | attribution | SoH tasks | 3 |
| 8 | Component catalogs: Nexar/Octopart API, Digi-Key API, jlcparts, jlcpcb-parts-database | free tiers; scraped data ToS unverified | BOM costing; needs FROZEN SNAPSHOT | 3 |
| 9 | OpenEVSE_PLUS, openinverter hardware | CC BY-SA | charger/inverter design | 3 |

## D. Script-driven solvers that could become graders

| # | Solver | Domain | Install | License | Run time | Rank |
|---|---|---|---|---|---|---|
| 1 | pandapower | power systems PF/OPF/SC | pip | BSD-3 | case118 <1 s | 5 |
| 2 | ngspice (subprocess; avoid PySpice GPL-3, stale) | circuits | conda/OS pkgs; have it | BSD | ms-s | 5 |
| 3 | python-control (+slycot opt.) | controls | pip | BSD-3 | ms | 5 |
| 4 | scikit-fem | thermal/structural FEA | pip pure Python | BSD-3 | <1 s 2D | 5 |
| 5 | PyBaMM | batteries SPM/DFN/ECM + thermal | pip | BSD-3 | 1-5 s | 5 |
| 6 | CalculiX | structural/thermal FEA | conda-forge ~50 MB | GPL-2 | <1 s | 4 |
| 7 | SfePy | multiphysics FEA | pip | BSD-3 | s | 4 |
| 8 | PyNite | frames/trusses/plates | pip | MIT | ms | 4 |
| 9 | lcapy | symbolic circuits (SymPy) | pip | LGPL-3 | ms-s | 4 |
| 10 | CoolProp; fluids / ht / thermo (ChEDL) | properties; pipe flow; HT correlations | pip | MIT | ms | 4 |
| 11 | CadQuery / build123d + trimesh | CAD geometry grading | pip (~200 MB) | Apache-2.0 | s | 4 |
| 12 | PYPOWER | power flow cross-check | pip | BSD-3 | <1 s | 3 |
| 13 | PyPSA | energy-system optimisation | pip + LP solver | MIT | s | 3 |
| 14 | ANDES | power-system dynamics | pip | GPL-3 | s | 3 |
| 15 | FEniCSx/dolfinx | general PDE | conda/Docker | LGPL-3 | s | 3 |
| 16 | Code_Aster | structural FEA | conda Linux only | GPL | s | 3 |
| 17 | OpenSeesPy | structural/seismic | pip | research/edu; commercial redistribution restricted | ms-s | 2 |
| 18 | PyFR, fluidsim, phiflow | CFD | pip | BSD/CeCILL/MIT | s-min | 2 |
| 19 | Elmer | multiphysics | binaries/Docker | GPL/LGPL | s | 2 |
| 20 | OpenFOAM, SU2 | full CFD | Docker/apt | GPL/LGPL | min+ | 1 |

Also: `pint` (BSD-3) for unit-aware answer keys.

## License traps for an MIT repo
- Non-commercial data (UGPhysics, Text2CAD, EngiBench data) and GPL code (PySpice, EngiBench, ANDES, CalculiX, Code_Aster): depend on / cite, never vendor.
- Textbook-sourced QA sets (SciBench, PhysReason, CircuitSense curated half, CIRCUIT) carry upstream copyright regardless of wrapper: use for topic taxonomy, not items.
- Live component APIs are non-deterministic: freeze a dated snapshot.

## Unverified, check before use
Licenses: AnalogCoder, EngDesign, CircuitLM, P3D-Bench, MMCircuitEval, AMSbench, DesignQA. CIRCUIT availability. FEM-Bench repo URL. SciBench exact tolerance. dolfinx pip wheels. Per-report NREL license lines. JLCPCB redistribution terms. IEA-15-240-RWT license. Free NAFEMS PDFs.
