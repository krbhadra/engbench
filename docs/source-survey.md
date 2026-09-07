# EngBench Source Survey

Open, citable material for grounding engineering benchmark tasks, ranked by how directly each source turns into a deterministically gradeable task. Four research passes on 2026-09-07: thermal, controls, fluids, and a cross-cutting pass on existing benchmarks, verification suites, datasets, and solvers. 96 sources evaluated. Every URL was fetched or resolved unless marked unverified.

Rank 5 = seeds tasks or graders directly with a compatible license. Rank 1 = marginal.

## Headline findings

1. **Deterministic grading is the norm in the best recent work, not an outlier.** ABench-Physics grades to 1% tolerance, EngChain to 2% per step, FEM-Bench with unit tests that must also fail on known-bad code, EngDesign and AnalogCoder by running simulators. EngBench's stance has clear precedents to cite.
2. **EngDesign is the nearest competitor.** 101 design tasks across 9 domains graded by simulation, 53 of them fully open. Its license is unstated. EngBench differentiates on two tracks, cross-discipline tasks, and source-grounded perturbation.
3. **The perturbation trick already exists and is Apache-licensed.** ABench-Physics stores parameterized solutions and regenerates numbers plus answers. The pattern is reusable.
4. **Every discipline has a pip-installable, permissively licensed grader.** scikit-fem and FiPy for thermal FEA, python-control for controls, the `fluids` library and EPANET for fluids, pandapower for power systems, PyBaMM for batteries, PyNite for structures, ngspice for circuits. No GPL code needs to be vendored.
5. **Every canonical number is memorized.** NAFEMS T4's 18.3 C, Featflow's CD 5.5795, the CTMS DC motor, Wood-Berry. Sources are safe only because parameters can be perturbed and the key recomputed. CFD reference cases are the exception: they cannot be perturbed without re-running the reference, so they are only trustworthy if EngBench runs the submitted case itself.
6. **License hygiene is manageable.** US government works, CC BY, MIT, and BSD can be cited freely. Non-commercial data (UGPhysics, Text2CAD, U. Kentucky water networks) and GPL solvers (CalculiX, Code_Aster, OpenFOAM) can be depended on or linked but never copied into the MIT repo. Textbook-derived QA sets carry upstream copyright regardless of wrapper license.

## Top sources by discipline

### Thermal (24 evaluated, 22 verified)

| Rank | Source | Yields | Grader |
|---|---|---|---|
| 5 | NAFEMS T2/T3/T4 thermal benchmarks, definitions reproduced in MOOSE, Abaqus, Wolfram docs | 1D transient and 2D steady conduction with convection; perturb k, h, geometry | scikit-fem / FiPy, sub-second |
| 5 | INL Code Verification Matrix for Heat Conduction (analytic Python scripts in MOOSE) | Cartesian, cylindrical, spherical conduction with generation and Robin BCs | closed-form |
| 5 | Lienhard, A Heat Transfer Textbook 6e + 520 solved problems | fins, transient lumped, composite walls, NTU exchangers, radiation | closed-form; templates only, cite not copy |
| 5 | Howell radiation configuration-factor catalog (350+ view factors) | view factors and gray-surface enclosure networks | closed-form + numeric cross-check |
| 5 | Kunzi, Thermal Design of Power Electronic Circuits, CERN / arXiv (CC BY 4.0) | multi-device heat-sink sizing, Foster/Cauer transient junction temperature | thermal-resistance network |
| 5 | FiPy (NIST, public domain) and scikit-fem (BSD-3) | the graders themselves | - |
| 4 | code_aster Validation Manual V4 (69 heat cases with analytic refs) | perturbed versions graded closed-form | closed-form; code_aster itself heavy |
| 4 | TI SPRA953D package thermal metrics; Boyd heat-sink catalog with worked selection; Electronics Cooling plate-fin method | junction temperature from PsiJT / Rth chains; heat-sink selection under perturbed power | closed-form; catalog curves need digitizing |
| 4 | NREL Kim & Pesaran 2006 battery thermal management; Sandia Hewson thermal-runaway Arrhenius tables; PyBaMM thermal models | cell-to-coolant lumped models; time-to-runaway ODE; pack peak temperature | scipy ODE; PyBaMM |

### Controls (27 evaluated)

| Rank | Source | Yields | Grader |
|---|---|---|---|
| 5 | Michigan CTMS, 7 benchmark plants (CC BY-SA 4.0) | PID / lead-lag / LQR / digital design to settling, overshoot, error specs on perturbed plants | python-control step_info, margin, place, lqr, c2d |
| 5 | python-control (BSD-3) + examples (PVTOL, steering, MRAC) | the grader; parameterized example plants | - |
| 5 | NASA CR-2144 Aircraft Handling Qualities Data, 10 aircraft x 10 flight conditions (public domain) | pitch and yaw damper design, LQR and observers to handling-quality bands | state-space, eigenvalues |
| 5 | Skogestad 2003 SIMC rules, 15 test plants with tuning tables | half-rule model reduction then PI/PID; IAE and Ms checks | closed-form + scipy lsim |
| 4 | Astrom & Murray Feedback Systems; Astrom-Hagglund PID test batch | loop shaping with sensitivity bounds; ZN/AMIGO tuning with Ms | python-control |
| 4 | Johansson quadruple-tank; Wie-Bernstein two-mass-spring; Landau flexible transmission; COMPleib 168 LTI models | MIMO zeros and RGA; robust stability over a parameter range; digital RST design; static output feedback | scipy ODE, python-control discrete, Riccati |
| 4 | TI SLVA662 Type II/III compensator with full numeric example; NASA CR-135174 Cuk & Middlebrook state-space averaging (public domain) | buck/boost small-signal model then compensator to crossover and phase margin | closed-form k-factor + scipy bode |
| 4 | Plett BMS ESC toolbox + MIT Python port; LibreTexts Iqbal (CC BY-NC-SA) | EKF SOC estimation RMSE; numeric lead/lag examples | numpy EKF, DARE |
| 3 | TI TIDUB21 grid inverter (LCL + PR + PLL); TI SPRACL1B PMSM current loop; DaISy system-ID datasets; Gymnasium CartPole | LCL resonance and PR gains; FOC loop bandwidth with delay margin; ARX fitting on held-out data | scipy bode, python-control, least squares |

### Fluids (21 evaluated)

| Rank | Source | Yields | Grader |
|---|---|---|---|
| 5 | fluids library (MIT): Colebrook, Crane TP-410 K-factors, pump affinity, Fanno, orifices | the grader for pipe, fitting, pump, and compressible tasks | - |
| 5 | EPANET (MIT / public domain) + WNTR example networks Net1/2/3/6 (BSD-3) | network pressure and flow with perturbed demands; minimum-diameter design; pump scheduling | EPANET, milliseconds |
| 5 | CoolProp (MIT) incl. glycol mixtures 0-60% | exact coolant properties for every loop task | - |
| 5 | NREL Kim & Pesaran 2006 | laminar channel cold-plate design-space search under Re, dP, dT constraints | closed-form |
| 4 | NPARC Alliance V&V archive (NASA Glenn); NASA Glenn compressible-flow pages; Bar-Meir compressible flow (CC BY) | Blasius, oblique shock, Prandtl-Meyer, Sod, nozzle sizing, Fanno choke length at perturbed M and gamma | closed-form |
| 4 | Jeppson 1974 pipe networks + Python port; U. Kentucky water network database (CC BY-NC, link only); AFT Fathom 80 verification cases as archetype catalog | multi-loop network flow; realistic 24 h tank and pump studies; task archetypes from Crane, Fox & McDonald, Cameron | EPANET or Hardy-Cross |
| 4 | NASA Turbulence Modeling Resource | flat plate Cf, backstep reattachment 6.26 +/- 0.1 | RANS CFD, heavy; contaminated unless EngBench runs the case |
| 3 | Featflow DFG cylinder benchmarks; OpenFOAM-12 tutorials incl. Waters-King analytic Poiseuille start-up; SU2 V&V; DOE MEASUR pump/fan calculators; DOE pump and fan sourcebooks | CFD verification; affinity-law energy tasks | OpenFOAM / SU2 heavy; MEASUR light |
| 2 | Manufacturer fan and pump curves (Delta, ebm-papst, Grundfos) | fan selection against a system curve; curves are images, so author synthetic tables in their style | closed-form intersection |

## Task families ready to build

Light solver, closed-form or sub-second key, freely perturbable, permissive source.

| Family | Discipline | Source | Grader |
|---|---|---|---|
| 2D steady conduction with convection at a probe point | thermal | NAFEMS T4 via MOOSE docs | scikit-fem |
| Multi-device heat-sink sizing with pulsed load | thermal | Kunzi CC BY; Boyd catalog | Rth network, Foster |
| Package junction temperature via PsiJT and Rth chain | thermal | TI SPRA953D | closed-form |
| Gray-surface enclosure radiation exchange | thermal | Howell catalog | closed-form |
| Time-to-thermal-runaway from Arrhenius parameters | thermal / battery | Sandia Hewson | scipy ODE |
| PID / lead design to settling and overshoot on perturbed plant | controls | CTMS CC BY-SA | python-control |
| Aircraft damper gain to handling-quality damping band | controls | NASA CR-2144 public domain | eigenvalues |
| SIMC tuning after half-rule reduction, IAE and Ms | controls | Skogestad 2003 | closed-form + lsim |
| Buck converter compensator to crossover and phase margin | controls / power electronics | NASA CR-135174 + TI SLVA662 | k-factor + bode |
| Robust stabilization of two-mass-spring over stiffness range | controls | Wie-Bernstein via arXiv | poles on k-grid |
| EKF SOC estimation on ECM with fixed-seed noise | controls / battery | Plett + MIT Python port | numpy |
| Pipe run with fittings: pressure drop and pump operating point | fluids | fluids library + synthetic pump curve | fluids |
| Water network minimum-diameter design to pressure floor | fluids | EPANET + WNTR nets | EPANET |
| Water-glycol coolant loop sizing | fluids / thermal | CoolProp + fluids + NREL 40446 | closed-form |
| Laminar cold-plate design-space search under Re, dP, dT | fluids / thermal | NREL 40446 | closed-form |
| Nozzle, shock, Fanno at perturbed Mach and gamma | fluids | NASA Glenn, Bar-Meir CC BY | closed-form |
| Enclosure fan selection against a system curve | fluids / thermal | manufacturer method, synthetic curve | closed-form |

Cross-discipline candidates fall out naturally: power-electronics loss to heat sink to fan selection; battery cell heat to coolant loop to pump; converter small-signal model to compensator to thermal derating. Each chains two or three of the families above through one shared parameter set.

## Grader stack

| Discipline | Recommended | Install | License |
|---|---|---|---|
| Thermal, closed-form | numpy / scipy; ht and thermo (ChEDL) for correlations | pip | MIT / BSD |
| Thermal, FEA | scikit-fem, FiPy | pip, pure Python | BSD-3, public domain |
| Battery thermal / electrochemical | PyBaMM | pip | BSD-3 |
| Controls | python-control + scipy.signal; slycot only for H2/Hinf | pip | BSD-3 |
| Fluids, correlations | fluids, CoolProp | pip | MIT |
| Fluids, networks | EPANET via WNTR | pip | MIT / BSD-3 |
| Circuits | ngspice as subprocess (already in use); lcapy for symbolic | have it | BSD; LGPL-3 |
| Power systems | pandapower; PYPOWER as cross-check | pip | BSD-3 |
| Structures | PyNite for frames; scikit-fem / SfePy for continuum; CalculiX via conda for shells and modal | pip / conda | MIT / BSD / GPL-2 external |
| CAD geometry | CadQuery or build123d + trimesh | pip, ~200 MB | Apache-2.0 |
| Units | pint | pip | BSD-3 |
| CFD | none for v2; OpenFOAM / SU2 only if a task requires it and EngBench runs it | Docker | GPL / LGPL |

## Existing benchmark landscape

| Benchmark | What | Grading | License | Borrow |
|---|---|---|---|---|
| ABench-Physics | 400 static + 100 parameterized physics | numeric 1% tol | Apache-2.0 | variation-engine pattern |
| EngDesign | 101 design tasks, 9 domains | simulation, 53 open | unstated | nearest competitor; study its open graders |
| AnalogCoder / AnalogAgent | 24-30 analog design tasks | ngspice testbenches | none found | testbench style |
| EngChain / EngTrace | 90 templated problems, 9 domains | 2% step tolerance | CC BY 4.0 | template taxonomy |
| FEM-Bench | 33 FEM code tasks | numeric match + adversarial unit tests | CC BY 4.0 | must-fail-on-bad rule |
| CircuitSense, EEE-Bench | 8k / 2.9k circuit and EE problems | symbolic, MC | MIT | synthetic generator idea; topic map |
| EngiBench (IDEALLab) | design-optimization simulators | simulator objective | GPLv3 / CC BY-NC-SA | external dependency only |
| UGPhysics, PhysReason, SciBench, PHYSICS | physics QA | mostly numeric | NC or textbook-derived | topic taxonomy only |
| ControlBench, ControlEval | 147 / 500 control tasks | LLM-judged / python-control | none | avoid duplicating their distribution |
| MechVQA, ElecBench, CircuitLM | drawings, power sector, schematics | LLM-judged | various | not usable |

"ENGINEBench" was not found; likely a conflation with EngiBench or EngDesign.

## Rules that fall out of this

- **Cite, link, restate. Never paste.** Every task carries its source and derivation. Problem text, tables, and figures from copyrighted sources are not reproduced.
- **Perturb everything.** A task is never the source's original numbers. The answer key is regenerated from the perturbed parameters by the grader, in the ABench-Physics pattern.
- **Golden and broken, and the grader must fail the broken one.** Kept from v1, and confirmed by FEM-Bench as the right pattern.
- **Permissive graders in the repo, GPL solvers as external tools.** CalculiX, Code_Aster, OpenFOAM are invoked, never vendored.
- **Non-commercial data is linked, not shipped.** U. Kentucky networks, UGPhysics, Text2CAD.
- **Freeze catalogs.** Component prices and availability change; any catalog-based task ships a dated snapshot.
- **CFD only if we run it.** Reference numbers for TMR, Featflow, Ghia are memorized. A CFD task means the model submits a case and EngBench executes it.

## Unverified, check before use

Licenses: AnalogCoder, EngDesign, CircuitLM, P3D-Bench, DesignQA, MEASUR-Tools-Suite, APMonitor pdc, Jeppson 1974 rights, per-dataset Dryad NED3 licenses, per-report NREL license lines, IEA-15-240-RWT. Availability: CIRCUIT dataset, FEM-Bench repo URL, Text2CAD-Bench data. Content: Kunzi full text (arXiv CC BY confirmed), quadruple-tank parameters (PDF text unreadable, values from literature), ST UM1052 formula, NREL TP-5700-72325 and 66554 cold-plate data, Sanyo Denki fan note, Astrom-Hagglund IFAC 2000 openness, dolfinx pip wheels, JLCPCB data redistribution terms, whether any NAFEMS PDFs are free to non-members.

Host changes noted: NREL docs moved from docs.nrel.gov to docs.nlr.gov. NASA TMR moved to tmbwg.github.io/turbmodels.

## Suggested next steps

1. Decide the v2 discipline set and its graders from the stack table. Thermal, controls, fluids on top of the existing mechanical and electrical needs four pip installs: scikit-fem, python-control, fluids, CoolProp, plus EPANET via WNTR if network tasks are wanted.
2. Pick 3 to 4 task families per discipline from the ready-to-build list and write a task-authoring standard: source citation, perturbation ranges, grader, golden, broken.
3. Build the cross-discipline chains first, since those are where the first run showed models breaking.
4. Resolve the unverified license items for anything that makes the cut.
