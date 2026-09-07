# Controls — ranked sources (27 evaluated)

| # | Source | Type | Openness | Solver needed | Rank |
|---|---|---|---|---|---|
| 1 | Michigan CTMS (7 benchmark plants: cruise, DC motor speed/position, suspension, inverted pendulum, aircraft pitch, ball & beam) | courseware w/ worked designs | CC BY-SA 4.0 (verified) | python-control step_info/margin/place/lqr/c2d | 5 |
| 2 | python-control + examples (PVTOL, steering, MRAC, H2/Hinf) | solver + example plants | BSD-3 | itself (slycot only for H2/Hinf) | 5 |
| 3 | NASA CR-2144 Heffley & Jewell, Aircraft Handling Qualities Data (10 aircraft x 10 flight conditions) | research report | public domain | state-space, LQR, pole placement | 5 |
| 4 | Skogestad 2003 SIMC rules (15 test plants E1-E15 with PI/PID tables, IAE, Ms) | paper, author PDF | free-to-read, Elsevier (c) | closed-form + scipy step/IAE | 5 |
| 5 | Astrom & Murray Feedback Systems 2e + FBSwiki | textbook, free PDF | free-to-read, (c) | python-control | 4 |
| 6 | Astrom-Hagglund PID test batch (via Astrom Control System Design ch. 6) | benchmark plant family | free notes; IFAC paper openness unverified | ZN/AMIGO closed-form + Ms, IAE | 4 |
| 7 | Johansson quadruple-tank (CDC'99 PDF) | MIMO benchmark w/ adjustable RHP zero | free author PDF (text layer unreadable; params from literature) | scipy ODE + python-control RGA/zeros | 4 |
| 8 | Wie-Bernstein ACC two-mass-spring benchmark (restated in arXiv math/0603681) | robust-control benchmark | AIAA paywalled; open restatements | closed-loop poles over k in [0.5,2] + impulse sim | 4 |
| 9 | COMPleib (124+44 LTI models: aircraft, helicopters, reactors, wind turbine) | benchmark library | free; "use it, reference it" | scipy Riccati / python-control; slycot for Hinf | 4 |
| 10 | LibreTexts Iqbal, Introduction to Control Systems (numeric lead/lag/PID/digital examples) | open textbook | CC BY-NC-SA 4.0 | python-control margin/step_info | 4 |
| 11 | TI SLVA662 Type II/III compensator (full numeric worked example) | app note | free, TI (c) | closed-form k-factor + scipy bode | 4 |
| 12 | Plett BMS ESC toolbox + batterysim/esctoolbox-python | textbook code + cell data; EKF/SPKF SOC | Python port MIT; original terms unstated | numpy EKF sim, DARE | 4 |
| 13 | Landau flexible-transmission benchmark (ARX, Ts=50 ms, 3 load cases) | digital robust-control benchmark | paper paywalled; coefficients widely reproduced | python-control discrete margins | 4 |
| 14 | NASA CR-135174 Cuk & Middlebrook state-space averaging (buck/boost small-signal) | research report | public domain | closed-form + scipy bode | 4 |
| 15 | TI TIDUB21 grid-connected inverter (LCL Li=3mH, Cf=1uF, Lg=0.94mH; PR + PLL + notch) | design guide | free, TI (c) | scipy bode of LCL + PR loop | 3 |
| 16 | TI SPRACL1B fast current loop (PMSM FOC; BW=fs/18 default, fs/6 max) | app note | free, TI (c) | closed-form + Pade delay margin | 3 |
| 17 | MIT OCW 2.14 (2014, no solutions) + 2.14 F2003 archive (PS1-8 with solutions) | courseware | CC BY-NC-SA / MIT (c) | python-control | 3 |
| 18 | MIT OCW 16.30 Feedback Control Systems | courseware (no solutions) | CC BY-NC-SA | python-control | 3 |
| 19 | Gymnasium CartPole (Barto-Sutton-Anderson params, Euler 0.02 s) | open simulator | MIT | numpy dynamics; digital-control angle | 3 |
| 20 | DaISy (KU Leuven, 24 system-ID datasets) | open dataset | free, citation required | scipy least squares | 3 |
| 21 | APMonitor PDC / TCLab (FOPDT Kp=0.9, tau=175 s, theta=15 s) | courseware w/ Python solutions | no LICENSE file | closed-form IMC/ITAE + scipy | 3 |
| 22 | Tennessee Eastman: pyTEP (BSD-3) / tep2py (MIT) | open simulator | permissive | Fortran wrapper; heavy | 3 |
| 23 | Doyle-Francis-Tannenbaum Feedback Control Theory (author PDF) | textbook | free-to-read | python-control norm (slycot) | 3 |
| 24 | Wood-Berry distillation column 2x2 FOPDT | MIMO benchmark | paywalled paper; model ubiquitous | Pade / discrete sim | 3 |
| 25 | Vendor FOC tuning docs (Microchip AN1078/MCAF, ST UM1052, NXP MCAT, Infineon) | app notes | vendor (c) | closed-form Kp=L*wc, Ki=R*wc | 2 |
| 26 | Morilla Benchmark PID 2012 (boiler) | Simulink .mdl/.p | unstated; MATLAB-only | not portable | 2 |
| 27 | ControlBench (147, LLM-judged) / ControlAgent ControlEval (500 tasks, control==0.10.1) | LLM benchmarks | no LICENSE files | python-control | 2 |

Verified CTMS DC motor: J=0.01, b=0.1, K=0.01, R=1, L=0.5; specs ts<2 s, OS<5%, ess<1%. Inverted pendulum M=0.5, m=0.2, b=0.1, I=0.006, l=0.3.
Verified SLVA662 Type III example: fc=1 kHz, 130 deg boost -> fz1=87.7 Hz, fp2=11.4 kHz, fz2=456 Hz, fp1=2.1 kHz; C1=14.7 nF, C2=9.2 nF, C3=113.5 pF, R2=123.9 k, R3=50.

Best plant families for perturbation: CTMS seven plants; Astrom-Hagglund/Skogestad FOPDT batches; NASA CR-2144 (100 aircraft/condition combos); COMPleib (168 models); DaISy (24 datasets).
Solver weight: python-control + scipy covers >=90%; slycot for H2/Hinf; scipy ODE for tank/cart-pole/EKF; Fortran only for TE.
Unverified: Astrom-Hagglund IFAC 2000 openness; quadruple-tank params (from literature); ST UM1052 formula; Wie-Bernstein and Landau primaries paywalled.
