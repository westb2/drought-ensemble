# Matched-deficit intermediate pumping runs

**Date submitted:** 2026-08-26  
**Agent handoff (full detail):** [`.cursor/skills/drought-ensemble/matched-deficit-pumping-runs.md`](../.cursor/skills/drought-ensemble/matched-deficit-pumping-runs.md)

## One-line goal

Add pumping rates `2×10⁻⁶`, `3×10⁻⁶`, `5×10⁻⁶`, `6×10⁻⁶` m/h so each domain can be compared to **10-yr drought** at similar **total storage deficit**, highlighting that **f_temp, depth, overland pattern, and recovery differ** even when totals match.

## Jobs (PBS, 2026-08-26)

| Job ID | Domain | Member |
|--------|--------|--------|
| 7254997–7255000 | potomac2 | pumping_2e-6 … pumping_6e-6 |
| 7255001–7255004 | wolf2 | pumping_2e-6 … pumping_6e-6 |

## Targets vs predictions (10⁶ m³, end of 3-yr pumping)

| | Potomac (10-yr drought = **214**) | Wolf (10-yr drought = **203**) |
|--|-----------------------------------|--------------------------------|
| 2×10⁻⁶ | ~182 | ~66 |
| 3×10⁻⁶ | ~274 | ~100 |
| 5×10⁻⁶ | ~458 | ~167 |
| 6×10⁻⁶ | ~550 | ~**201** |
| Interpolated match | **~2.4×10⁻⁶** | **~6.0×10⁻⁶** |

## Results (fill in when complete)

| Domain | Rate | Actual total deficit | f_temp | Persist NS/deep | Notes |
|--------|------|---------------------:|-------:|-----------------|-------|
| potomac2 | 2e-6 | | | | |
| potomac2 | 3e-6 | | | | |
| potomac2 | 5e-6 | | | | |
| potomac2 | 6e-6 | | | | |
| wolf2 | 2e-6 | | | | |
| wolf2 | 3e-6 | | | | |
| wolf2 | 5e-6 | | | | |
| wolf2 | 6e-6 | | | | |

## Next steps for analysis agent

1. Confirm completion via `years_to_run.py` and `file_locations_219h.json` (53 years).
2. Update `RATES` in `pumping_vs_drought_deficits.py` (+ related scripts); set `DROUGHT_MEMBER = "10_year_drought"`.
3. Interpolate matched rate per domain; build matched-deficit contrast figures (temp/persist, depth, overland, recovery).
4. Update this table and `analysis/FIGURES_INDEX.md`.
