# Pumping response figures (analogues of drought recovery)

**Date:** August 2026  
**Script:** [`redo_pumping_recovery_analogues.py`](redo_pumping_recovery_analogues.py)  
**Deck:** [`recovery_and_pumping_figures.pptx`](recovery_and_pumping_figures.pptx) (drought + pumping; open in Google Slides via File → Import)

## Ensemble design adjustments

`3_year_pumping_tests` differs from `droughts`:

| | Droughts | Pumping |
|--|----------|---------|
| Stress axis | Duration (1 / 3 / 10 / 50 yr) | Rate (`1e-7` … `1e-4` m/h domain-avg) |
| Sequence | 40 spinup → drought → **5 yr recovery** | 40 spinup → **3 yr pumping** (ends while still pumping) |
| Temp / persist | Recovered in recovery yr 1 vs remaining | **Early** (end pump yr 1) vs **buildup** (extra by end yr 3) |
| Baseline | `short_baseline` / `baseline` | `droughts/short_baseline` (shared spinup hashes) |

## Figures

- [pumping_during_totals_and_anomalies.png](figures/pumping_during_totals_and_anomalies.png)
- [pumping_by_rate_fractional_storage.png](figures/pumping_by_rate_fractional_storage.png)
- [pumping_course_streamflow_storage.png](figures/pumping_course_streamflow_storage.png)
- [pumping_wtd_anomaly_maps.png](figures/pumping_wtd_anomaly_maps.png)
- [pumping_early_buildup_storage_deficit_maps.png](figures/pumping_early_buildup_storage_deficit_maps.png)
- [pumping_early_buildup_deficit_bars.png](figures/pumping_early_buildup_deficit_bars.png)

### Domain totals (10⁶ m³) — early / buildup

| Rate | Potomac | Wolf |
|------|---------|------|
| 1e-7 | 3.5 / 5.9 | 1.3 / 2.1 |
| 1e-6 | 31 / 54 | 12 / 20 |
| 1e-5 | 308 / 554 | 120 / 206 |
| 1e-4 | 3188 / 6235 | 1254 / 2437 |

Deficits scale roughly linearly with rate; buildup over years 2–3 exceeds the year-1 early deficit at all rates.

## Reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
source ~/pf_env.sh
cd /glade/derecho/scratch/bwest/drought-ensemble
python analysis/redo_pumping_recovery_analogues.py
python analysis/build_recovery_pumping_pptx.py
```
