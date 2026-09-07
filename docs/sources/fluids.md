# Fluids — ranked sources (21 evaluated)

Notes: NREL docs host renamed docs.nrel.gov -> docs.nlr.gov. NASA TMR moved to https://tmbwg.github.io/turbmodels/.

| # | Source | Type | Openness | Solver / answer-key | Rank |
|---|---|---|---|---|---|
| 1 | fluids (CalebBell/fluids) | open solver library | MIT | IS the grader: Colebrook/Churchill, Crane TP-410 K-factors, pump affinity, Fanno/isothermal, orifices | 5 |
| 2 | EPANET (OWA 2.2 / USEPA) + WNTR example networks (Net1/2/3/6) | open 1D network solver + datasets | MIT / public domain / BSD-3 | EPANET solve; light (ms) | 5 |
| 3 | CoolProp (incl. INCOMP::MEG/MPG glycol 0-60%, -100..100 C) | property library | MIT | property lookups; trivial | 5 |
| 4 | NREL/CP-540-40446 Kim & Pesaran 2006 battery thermal management | lab paper | US-gov, free | laminar channel relations (cf*Re=24, Nu=5.385) + property table; light | 5 |
| 5 | NASA Turbulence Modeling Resource (TMR) | V&V suite | US-gov | grid-converged CFL3D/FUN3D refs; needs RANS CFD; heavy | 4 |
| 6 | NPARC Alliance V&V Archive (NASA Glenn) | V&V suite, 28 cases | US-gov | analytic cases (Blasius, Prandtl-Meyer, oblique shock, Sod) -> closed-form keys | 4 |
| 7 | Jeppson 1974 "Steady Flow Analysis of Pipe Networks" (USU) + jeppson-python port | courseware w/ worked networks | free PDF, rights unstated | Hardy-Cross/Newton or EPANET; light | 4 |
| 8 | U. Kentucky Water Distribution System Research Database (40+ EPANET .inp) | open dataset | CC BY-NC 4.0 (download at build time, don't vendor) | EPANET/WNTR; light | 4 |
| 9 | AFT Fathom Verification Cases (80 cases; Crane, Fox&McDonald, Jeppson, Cameron, HI 9.6.7) | vendor verification suite | free to read, copyrighted | archetype catalog; regrade with fluids/EPANET after re-parameterizing | 4 |
| 10 | NASA Glenn compressible-flow pages + Bar-Meir Fundamentals of Compressible Flow | textbook/courseware | public domain / CC BY | isentropic/shock/Fanno/Rayleigh closed-form; trivial | 4 |
| 11 | Featflow DFG 2D-1/2/3 flow-around-cylinder (CD=5.5795, CL=0.010619, dp=0.11752 at Re=20) | CFD benchmark | free, unlicensed | needs NS solver; heavy | 3 |
| 12 | OpenFOAM-12 tutorials (cavity, pitzDaily, planarPoiseuille+WatersKing analytic, channel395) | open solver + cases | GPL-3 | OpenFOAM run vs analytic; heavy | 3 |
| 13 | SU2 V&V + tutorials (flat plate vs Blasius) | open solver + cases | LGPL-2.1 | SU2 run; heavy | 3 |
| 14 | DOE/ORNL MEASUR-Tools-Suite (PSAT/FSAT) | open calculator library | open source, license unverified | independent grader for pump/fan efficiency; light | 3 |
| 15 | MIT OCW 2.25 (solutions posted) + 2.06 | courseware | CC BY-NC-SA | analytic; high contamination | 3 |
| 16 | DOE "Improving Pumping/Fan System Performance" sourcebooks | gov guidance | US-gov (HI/AMCA figures may be 3rd-party) | affinity laws, hydraulic power; light | 3 |
| 17 | Bar-Meir Basics of Fluid Mechanics (Potto) | open textbook | modified GNU FDL | statics/control-volume only; no Moody/pipe flow | 2 |
| 18 | Ghia, Ghia & Shin 1982 cavity data (gist mirrors) | benchmark data | Elsevier paper; gists unlicensed | needs CFD; very high contamination | 2 |
| 19 | ERCOFTAC Classic Collection | exp/DNS database | CC BY-NC-SA, registration; server down at check | needs CFD | 2 |
| 20 | Fan/pump manufacturer curves (Delta AFB1212SH, ebm-papst note, Grundfos The Centrifugal Pump, Sanyo Denki note [unverified]) | datasheets/app notes | free, copyrighted; PQ curves are images | operating point = fan curve x system curve; light once tabulated; author synthetic curves | 2 |
| 21 | NREL power-electronics thermal reports (PR-5400-68077; TP-5700-72325/66554 unverified) | lab reports | US-gov | no cold-plate flow/dP data confirmed | 2 |

Verified numbers (NREL 40446): cell 50 mm x 100 mm, 2 W; coolant table air/mineral oil/water-glycol; constraints Re<2300, dP<110 Pa, dTmax<4.5 C; chosen Dh=2.2 mm, mdot=1.33 g/s; predicted dP=109.1 Pa (air), h=59.24 W/m2K.

Strongest low-risk task families: pipe/fitting dP + pump operating point (fluids + synthetic pump curve); EPANET network analysis/design; water-glycol coolant loop sizing (CoolProp + fluids + NREL 40446 archetype); laminar cold-plate design-space search; compressible nozzle/shock/Fanno; enclosure fan selection vs synthetic PQ curve.

CFD verification cases (TMR, NPARC, Featflow, Ghia, OpenFOAM/SU2) only trustworthy if EngBench runs the submitted case itself; reference numbers are heavily contaminated. Prefer analytic-reference cases at perturbed Re/M.

Paywalled standards (Crane TP-410, Idelchik, Cameron, HI, Miller): cite as origin, use fluids library as executable key.
