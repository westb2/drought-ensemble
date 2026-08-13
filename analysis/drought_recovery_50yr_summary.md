# Drought recovery analysis (including 50-year)

**Date:** August 2026  
**Script:** [`redo_recovery_with_50yr.py`](redo_recovery_with_50yr.py)  
**Notebook:** [`drought_recovery_comparison.ipynb`](drought_recovery_comparison.ipynb) (`DROUGHT_LENGTHS = [1, 3, 10, 50]`)  
**Figures:** [`figures/`](figures/)

Sequence: 40 yr average spinup → drought (`dry`) → 5 yr recovery (`average`). Recovery plots align \(t=0\) to drought end.

**Baseline for anomalies**

| Domain | Member | Notes |
|--------|--------|-------|
| Wolf | `baseline` (95 yr) | Same paths as `short_baseline` for years 0–54 |
| Potomac | `short_baseline` (55 yr) + end-year snapshots | Long baseline raw exists through year 94 but 219 h is incomplete after year 70. Spatial maps at years 89/90/94 use cached snapshots under `domains/potomac2/.../baseline/snapshots/`. Recovery timeseries remap onto short_baseline years 50–54 (same intra-year phase) with a storage offset so year-1 end matches the year-90 snapshot. An earlier off-by-one phase slip made Potomac 50-yr ΔS look jagged; that is fixed. |

---

## Domain-total temporary vs persistent storage deficit

Temporary = recovered in recovery year 1; persistent = still missing after year 1 (10⁶ m³).

| Domain | 1-yr temp / persist | 3-yr | 10-yr | 50-yr |
|--------|---------------------|------|-------|-------|
| Potomac | 66 / 23 | 81 / 55 | 88 / 126 | **92 / 418** |
| Wolf | 117 / 9 | 123 / 27 | 127 / 76 | **133 / 216** |

Temporary saturates by ~10 years. Persistent keeps growing through 50 years (especially Potomac).

---

## Figures

### Recovery timeseries (by length)

- [drought_recovery_totals_and_anomalies.png](figures/drought_recovery_totals_and_anomalies.png) — storage, ΔS, outlet flow, ΔQ over 5-year recovery (1/3/10/50)
- [drought_recovery_by_length_fractional_storage.png](figures/drought_recovery_by_length_fractional_storage.png) — fraction of initial storage deficit remaining

### Drought course (+ recovery)

- [ten_year_drought_streamflow_storage.png](figures/ten_year_drought_streamflow_storage.png) — last 3 spinup years → 10-year drought → recovery
- [fifty_year_drought_streamflow_storage.png](figures/fifty_year_drought_streamflow_storage.png) — same layout for 50-year (new)

### Spatial WTD / storage deficits

- [drought_recovery_wtd_anomaly_maps.png](figures/drought_recovery_wtd_anomaly_maps.png) — ΔWTD at recovery start, +1 yr, +5 yr (rows = 1/3/10/50)
- [drought_recovery_temp_persistent_storage_deficit_maps.png](figures/drought_recovery_temp_persistent_storage_deficit_maps.png) — temporary vs persistent storage (m water equiv.)
- [drought_recovery_temp_persistent_wtd_deficit_maps.png](figures/drought_recovery_temp_persistent_wtd_deficit_maps.png) — same split for ΔWTD

### Totals by drought length

- [drought_recovery_temp_persistent_deficit_bars.png](figures/drought_recovery_temp_persistent_deficit_bars.png) — map-based domain totals
- [drought_recovery_temp_persistent_deficit_bars_spike.png](figures/drought_recovery_temp_persistent_deficit_bars_spike.png) — fast-spike vs persistent (slow branch projected to \(t=0\))
- [drought_recovery_temp_spike_correction.csv](figures/drought_recovery_temp_spike_correction.csv) — breakpoint fits / spike magnitudes

### Machine-readable totals

- [drought_recovery_50yr_totals.json](figures/drought_recovery_50yr_totals.json)

---

## Takeaways with 50-year included

1. **Two-phase recovery still holds** — fast year-1 recovery vs slow residual; the fast component barely grows from 10 → 50 years.
2. **Persistent deficit is where length matters** — Potomac persistent ≈ 3× the 10-year value at 50 years (126 → 418); Wolf ≈ 3× as well (76 → 216).
3. **Potomac accumulates more persistent deficit than Wolf** at long durations, despite Wolf having a larger temporary (near-stream) pulse.
4. **5 years of average forcing is not enough** to erase the 50-year memory in either domain (ΔS remains large at recovery year 5).
5. **Streamflow does not track that deep persistent growth** — see [`persistent_storage_vs_streamflow_50yr.md`](persistent_storage_vs_streamflow_50yr.md) (peaks rebound in ~1 yr; only mild Potomac residual; no clean baseflow collapse).

---

## How to reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
source ~/pf_env.sh
cd /glade/derecho/scratch/bwest/drought-ensemble
python analysis/redo_recovery_with_50yr.py
```

Covariate / drainage / multivar screens from the earlier 10-year-focused follow-ups were **not** re-run here; say if you want those extended to 50-year as well.
