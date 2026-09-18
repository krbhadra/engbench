# bess — knowledge-required systems chain (draft spec)

Status: draft for review. Grader and generator follow this document once agreed.
Mode: `named` (methods and standards are named and cited in the task, never restated).
Disciplines: electrical, electronics, thermal, systems.

## The problem the model gets

Design a grid-connected LFP battery energy storage system for a site. Given:

- **Requirements:** usable energy E_req (MWh) at the point of connection over the
  service life, rated discharge and charge power P_req (MW), duration, service
  life (years) and cycles per day, site ambient range and altitude, grid
  connection level (MV, voltage stated), required power factor range at the
  point of connection per VDE-AR-N 4110.
- **Margin policy:** NASA SE Handbook Table 7.8-3 convention at a stated
  milestone (e.g. CDR: 15 % on energy and power). Named, not restated.
- **Cell datasheet values:** nominal voltage, capacity, voltage limits, DC
  resistance at BOL and its growth factor at EOL, continuous and pulse C-rates,
  temperature limits, cycle life to 80 % SOH at a stated DOD.
- **Catalogs:** PCS units (DC window, DC current limit, kVA at 25/40/50 C,
  efficiency, price); MV transformers (kVA, vector group, losses, price);
  DC fuses (rated current, rated DC voltage with time constant, breaking
  capacity, class gBat/aR, price); DC contactors (rated current, max breaking
  current, price); DC cables (cross-section, base ampacity per DIN VDE 0298-4
  reference method, price per metre); cooling units (kW thermal, price).
- **Site data:** DC cable route length rack-to-PCS, installation method,
  grouping, ambient for cables, prospective short-circuit current per rack
  (or the parameters to compute it per IEC 61660).

The task names: 80 % SOH end-of-life; VDE-AR-E 2510-50 for the storage
system; DIN VDE 0298-4 / IEC 60364-5-52 and IEC 60364-4-43 for conductors and
their coordination with protection; IEC 60269-7 for DC fuses; IEC 61660 for
string short-circuit current; VDE-AR-N 4110 for the connection point;
IEC 60076-11 for the transformer; NASA SE Handbook 7.8 for margins; PNNL ESGC
2022 definitions for RTE and usable energy.

## What the model returns

```json
{
  "cells_series": 416, "strings_parallel": 12, "racks": 12,
  "pcs": "PCS-3", "pcs_count": 2,
  "transformer": "TX-4",
  "string_fuse": "FU-7", "string_contactor": "CT-3",
  "dc_cable": "C-185", "dc_cables_parallel": 2,
  "cooling_unit": "CU-2", "cooling_count": 3
}
```

Every id comes from the task's catalogs. Counts are integers.

## What the grader closes (every check names its value and its limit)

1. **Energy at EOL.** E_usable = N_s N_p V_nom Q_nom (SOC_max - SOC_min) x 0.80
   x eta_DC x eta_PCS x eta_TX >= E_req x (1 + m_E). Trap: nameplate sizing.
2. **Power.** P_req x (1 + m_P) <= min(PCS AC rating at site T_max, cell
   continuous C-rate x N_p x V_min_string, PCS DC current limit x V_min_string).
   Trap: PCS derating at site temperature; DC current limit binding first.
3. **Voltage window.** N_s V_cell,min - I_max R_string,EOL >= V_PCS,min and
   N_s V_cell,max <= V_PCS,max. Trap: nominal-voltage arithmetic.
4. **Thermal.** Q = N_cells I_cell^2 R_EOL at rated power; sum of cooling unit
   capacity >= Q x (1 + m); cell stays within datasheet limits at site T_max
   with the stated cooling delta. Trap: EOL resistance, not BOL.
5. **String fuse (IEC 60269-7).** Class gBat; U_n,DC >= N_s V_cell,max at the
   stated time constant; I_n >= I_string,cont / k_load / k_amb (manufacturer
   factors from the catalog); breaking capacity >= prospective short-circuit
   current of all parallel strings feeding the fault (IEC 61660 quasi-steady
   value from the task's R and L). Trap: AC-rated or under-derated fuse;
   breaking capacity vs one string instead of all.
6. **Contactor.** I_rated >= I_string,cont; max breaking current >= fuse
   minimum breaking current so there is no gap (Eaton coordination rule, named).
   Trap: contactor sized to load current only.
7. **DC cable (DIN VDE 0298-4 + IEC 60364-4-43).** I_z = I_base x f_amb x
   f_group; I_B <= I_n,fuse <= I_z and I_2 <= 1.45 I_z with I_2 from the fuse
   class convention; voltage drop at I_max over the route within the stated
   limit. Trap: 30 C air base, grouping factor, the 1.45 rule.
8. **Grid side (VDE-AR-N 4110 + IEC 60076-11).** S_req = P_req / PF_min at the
   connection point; S_TX x k_alt x k_amb >= S_req; PCS reactive capability
   covers PF_min. Trap: kW vs kVA; altitude derating.
9. **Interface consistency.** Racks x strings match; PCS count x DC inputs >=
   strings (or combiner rule stated); contactor rated voltage >= string max;
   cable rated voltage >= string max; every count >= 1.

## Objective

Minimize total price = cells + PCS + transformer + fuses + contactors + cables
+ cooling. A design passes only if it closes every check and is within 5 % of
the brute-force optimum. Brute force: N_s from the voltage window (small
range), N_p from energy and power, then the catalog choices; the space is
enumerable in seconds.

## Broken cases derived from the golden

nameplate sizing (N_p from 100 % SOH), N_s from nominal voltage only, PCS
picked at 25 C rating, fuse picked at I_string without derating, contactor at
load current, cable without grouping factor, transformer at kW, cooling at
BOL resistance, feasible but most expensive.

## Generation

Per seed: perturb requirements, site, cell values and every catalog price and
rating within stated ranges; calibrate margins and site conditions so the
feasible fraction lands in 0.2-3 % of the enumerated space; reject seeds
where more than 25 % of feasible designs are near-optimal. Golden and broken
into `solvers/solutions.json`.

## Open points for review

- Which rack architecture to fix: one string per rack (simplest, common for
  280 Ah LFP) vs. rack-internal parallel. Proposal: one string per rack.
- Whether to require a combiner/DC panel fuse level between racks and PCS
  (rack fuse and PCS input fuse). Proposal: v1 has the string fuse only;
  PCS input fuse from the PCS catalog as a stated value.
- Cell-to-cell delta-T: keep out of v1 (needs a flow model) or state a cooling
  unit "delta-T at rated flow" and check it. Proposal: out of v1.
