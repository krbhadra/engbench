# bess3: storage system, level 3

Level 2 (`bess`) with the scaffolding removed. Same plant, same chain from
cells to the medium-voltage connection, but:

- **Nothing is named.** The prompt reads like a project brief: requirements,
  site, duty, the network operator's connection letter, and datasheets.
  Datasheets keep the tables a real datasheet carries (ambient and grouping
  factors, fuse derating and load factor, ageing and low-temperature charge
  tables) without saying what to do with them. The connection letter says the
  operator's medium-voltage connection rules apply, without saying what they
  require. Knowing that VDE-AR-N 4110, IEC 60269-7, IEC 61660-1,
  DIN VDE 0298-4, IEC 60364-4-43, IEC 60076-11, IEC 60909 and IEC 62271 apply,
  and what they demand, is part of the test.
- **The first design is final** (`max_grades: 1`). Python stays available.
- **Hidden requirements.** The grader checks everything level 2 checks, plus
  the items below, which the prompt never mentions.
- **A seed is kept only if at least three hidden requirements bind**: for each
  one, the optimum of the same task without it must fail the real grader.
  Those designs ship as broken solutions, so the self-check proves every kept
  task tests the hidden knowledge.
- **Private seeds** (`--private`, 1001 and up) go to `tasks_private/` and
  their results to `results_private/`, both outside git. The official level-3
  score comes from them; the public seeds let anyone reproduce the method.

One grader serves both levels: `solvers/bess.py` switches each level-3 check
on from the task's own data, and level-2 tasks carry none of it (verified:
identical metrics and verdicts on all 188 level-2 designs).

## Hidden requirements (author review: accepted 2026-10-24)

| # | Hidden requirement | Data in the task | Check |
|---|---|---|---|
| H1 | Size for capacity at end of service life; no state of health is given. | Duty in equivalent full cycles per day, service life, cell ageing tables (capacity retention and resistance growth by cycles). | State of health and resistance factor at cycles/day × 365 × years, interpolated; used for energy, voltage window, current and heat. |
| H2 | Connection-point requirements are net of auxiliaries. | EER of the cooling units, rack electronics W per rack, site systems kW; auxiliaries fed from the MV busbar behind the connection point. | Plant delivers P_net + P_aux with P_aux = rack × N_p + site + heat / EER, solved with the string current; E_net = E − P_aux × duration. The transformer carries the gross active power. |
| H3 | Reactive power at the bottom of the voltage band. | PCS rated at nominal AC voltage, output current-limited. | VDE-AR-N 4110 asks for Q = ±0.33 P_b,inst (cos φ 0.95) across 0.9–1.1 U_c without voltage-based reduction, so S_pcs(site T) × 0.9 ≥ S needed. |
| H4 | MV switchgear rated for the network fault level. | Connection letter S_k″ and R/X; PCS AC fault contribution; switchgear catalog. | U_r ≥ highest system voltage (12 / 24 / 36 kV); I_k = S_k″ / (√3 U_n) + PCS contribution ≤ short-time current; κ √2 I_k ≤ making current, κ = 1.02 + 0.98 e^(−3 R/X); rated current ≥ connection current. |
| H5 | Cells warm enough to charge in winter. | Charge rate by cell temperature, site minimum, enclosure heat loss per rack, unit heating capacity. | Cell temperature needed for the string current as a charge rate, from the table; heating × count ≥ UA × N_p × (T_needed − T_site_min). |
| H6 | FCR prequalification (half the plants; the brief names the FCR power only). | FCR power, symmetric. | German TSO PQ-Bedingungen v1.06 (2026-10-07) sec. 3.1.6, chosen by the author: power at the connection point ≥ 1.25 × P_FCR; usable energy ≥ (½ + ¼ + ⅙) h × P_FCR (endangered state, max of prior call and storage-management lag, reserve-mode bridging); both with the project margin. |

Sources for H3 (the standard is paywalled; these are public carriers, found
2026-10-24):
- M.O.E., VDE-AR-N 4110 and 4120 overview, Windenergietage 2018:
  <https://windenergietage.de/2018/wp-content/uploads/sites/3/2018/11/27WT07_F07_0945_4110_und_4120MOE_JM.pdf>
- Kommenergie, TAR Mittelspannung application notes, 2026, sec. 8.13.2:
  <https://www.kommenergie.de/_Resources/Persistent/b/5/0/3/b5030e5eb1dbd8b614881e5f709abfcdfcd77072/20260915-anwendungshinweise-kommenergie-tar-mittelspannung.pdf>
- The "Variante 1/2/3" PQ diagrams belong to VDE-AR-N 4120 (high voltage),
  not 4110: IEA PVPS Task 14 (2024),
  <https://iea-pvps.org/wp-content/uploads/2024/04/Reactive_power_management_with_DERs.pdf>

## Open items

1. **H6, FCR window.** v1.06 also sets SOC operating limits of 1/3 h × P_FCR
   from each end of the usable energy. The energy check above covers the
   reserved energy; the operating-window limits themselves (a control setting)
   are not graded.
   v1.06: <https://www.regelleistung.net/cdn/files/64507326-b71c-41b0-cdb6-08df1e03d14c/pq-bedingungen-2026_10_07.pdf>
2. **H3 corners.** The exact voltages where full Q ends at the edges of the
   0.9–1.1 U_c band (VDE-AR-N 4110, Bild 5) are unverified; the check uses
   full Q at 0.9 U_c.
3. **Storage while charging.** Operators differ on whether the reactive
   requirement applies when charging (Kulmbach and Kommenergie: yes; TEN: no).
   The check uses rated power with full Q, which covers both.
