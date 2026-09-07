# Thermal — ranked sources (24 evaluated, 22 verified by fetch)

| # | Source | Type | Openness | Solver / answer-key | Rank |
|---|---|---|---|---|---|
| 1 | NAFEMS thermal benchmarks T2/T3/T4 + axisymmetric (definitions reproduced in MOOSE / Abaqus / Wolfram / DIANA docs) | Verification benchmark | NAFEMS P18 paid; definitions + targets are public facts | 1D FD (T3), 2D FE via scikit-fem/FiPy (T4); light | 5 |
| 2 | INL "Code Verification Matrix for Heat Conduction" (INL/JOU-20-58950) | Verification suite, analytic | Public DOE; Python analytic scripts in MOOSE (LGPL) | Closed-form / 1D FD; light | 5 |
| 3 | Lienhard & Lienhard, A Heat Transfer Textbook 6e + solutions manual (>520 solved) | Textbook + solutions | Free download, copyrighted, non-profit use; cite, don't copy | Closed-form/correlations; light | 5 |
| 4 | Howell, Catalog of Radiation Configuration Factors (thermalradiation.net) | Reference catalog (>350 view factors) | Free web, no license stated | Closed-form + numeric cross-check; light | 5 |
| 5 | Kunzi, "Thermal Design of Power Electronic Circuits", CERN-2015-003 / arXiv:1607.01578 | Tutorial paper | CC BY 4.0 | Rth networks, Foster/Cauer transient; light | 5 |
| 6 | FiPy (NIST) | Open FV solver, pip | Public domain | Grader itself | 5 |
| 7 | scikit-fem | Open FE solver, pip (thermal examples 17,19,25,26,28,39) | BSD-3 | Grader itself | 5 |
| 8 | code_aster Validation Manual V4 (69 heat-transfer cases) | Verification suite | Docs GNU FDL, solver GPL | Analytic refs closed-form; code_aster heavy | 4 |
| 9 | TI SPRA953D package thermal metrics | App note | Free, (c) TI | TJ = TT + PsiJT*P, Rth chains; trivial | 4 |
| 10 | Boyd/Aavid Board-Level Cooling catalog (worked selection examples) | Datasheet catalog | Free PDF, (c) Boyd | Rth chain + digitized Rsa-vs-airflow curve; light | 4 |
| 11 | Electronics Cooling — Simons plate-fin heat sink articles | Method article | Free to read, all rights reserved | Closed-form fin efficiency + Nu; light | 4 |
| 12 | NREL Kim & Pesaran 2006, Battery Thermal Management System Design Modeling | Lab paper | US-gov funded, free | Lumped/1D channel cooling; light | 4 |
| 13 | Sandia Hewson thermal-runaway reports (OSTI 1420927, 1249044) | Lab report w/ Arrhenius table | Public DOE | Lumped ODE (scipy); light | 4 |
| 14 | PyBaMM thermal models (lumped, x-lumped, pouch 1+1D/2+1D) | Open solver, pip | BSD-3 | Grader itself; medium | 4 |
| 15 | HotSpot 7.0 (UVA) chip RC thermal simulator | Open solver (C) | Custom permissive | Grader itself; medium (build) | 3 |
| 16 | NREL Moreno 2017 Power Electronics Thermal Management (LEAF inverter stack) | Lab slides | Public | 1D layer-stack Rth; light | 3 |
| 17 | NASA Battery Failure Databank (~300 S-FTRC tests) | Open dataset | Public domain | Dataset lookup + lumped neighbor heating; light | 3 |
| 18 | NASA TP-1998-207427 Juhasz, Lightweight Space Radiators | Lab report | Public domain | Radiating-fin BVP (scipy); light-medium | 3 |
| 19 | NED3 Lab datasets on Dryad (D5470 Rth, cold-plate CFD 2000 cases, liquid cooler) | Open datasets | Dryad (CC0 default, per-dataset unverified) | Interpolation/regression check; light | 3 |
| 20 | Saxon et al. 2024 (NREL) Li-Ion Battery Thermal Characterization | Open-access paper | CC BY 4.0 | Bernardi heat generation closed-form; light | 3 |
| 21 | Elmer FEM + nemocrys/elmer-verification | Open solver + verification | GPL/LGPL | Elmer run or closed-form; medium | 3 |
| 22 | MIT OCW 2.51 / 2.051 heat transfer | Courseware | CC BY-NC-SA; no solutions found | Closed-form; light | 2 |
| 23 | JEDEC JESD51 series | Standard | Free with registration, (c) JEDEC | Reference only | 2 |
| 24 | NIST SRD 81 insulation conductivity database | Open dataset | Free, DoC notice | Property lookup; trivial | 2 |

Key numbers verified: NAFEMS T3 target T(0.08 m, 32 s) = 36.6 C; T4 target T(E) = 18.3 C; T2 = 927 K. Boyd example: PD 12 W, RthJC 2.5, TJmax 140, TA 50, TIM 1.15 -> Rsa 3.85 C/W. Sandia Arrhenius table (SEI: A=1.67e15, E=135 kJ/mol, dH=257 kJ/mol).

Recommended grader stack: numpy/scipy closed-form for most; scikit-fem or FiPy for 2D/axisymmetric keys; PyBaMM for battery lumped-thermal; HotSpot only for chip-level.

Contamination: every canonical number is memorized; every listed source allows parameter perturbation with a recomputable key.

Unverified: Kunzi full text (arXiv CC-BY confirmed), MOOSE web pages (raw GitHub confirmed), Intel Xeon thermal guide, per-dataset Dryad licenses.

Extracted texts saved in scratchpad: INLmatrix.txt, SPRA953.txt, BoydCatalog.txt, SandiaHewson.txt, NREL40446.txt, NREL68077.txt, Saxon2024.txt, NASATP1998.txt, InfineonAN1057.txt, onsemiAND9859.txt.
