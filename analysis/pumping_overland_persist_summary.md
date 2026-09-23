# Pumping persistent deficit vs overland flow

**Date:** August 2026  
**Script:** [`pumping_overland_persist.py`](pumping_overland_persist.py)  
Analogues of `drought_recovery_drainage_deficit_concentration.png` and `drought_recovery_drainage_threshold_bins.png`. Non-stream cells with baseline overland > 0. Persistent = remaining after recovery yr 1.

## Figures

- [pumping_drainage_deficit_concentration.png](figures/pumping_exploratory/pumping_drainage_deficit_concentration.png)
- [pumping_drainage_threshold_bins.png](figures/pumping_exploratory/pumping_drainage_threshold_bins.png)
- [pumping_vs_drought_mean_persist_overland.png](figures/pumping_exploratory/pumping_vs_drought_mean_persist_overland.png)

## Lowest-flow 20% of cells: share of persistent mass

| Domain | 3-yr drought | Pump 1e-7 | 1e-6 | 1e-5 | 1e-4 |
|--------|-------------:|----------:|-----:|-----:|-----:|
| Potomac | 0.60 | 0.22 | 0.21 | 0.23 | 0.17 |
| Wolf | 0.40 | 0.27 | 0.27 | 0.29 | 0.23 |

## Spearman ρ(log overland, persist)

| Domain | 3-yr drought | Pump 1e-5 |
|--------|-------------:|----------:|
| Potomac | -0.17 | 0.10 |
| Wolf | -0.27 | -0.29 |

## Takeaways

- Drought persistent mass concentrates in low-overland cells: lowest-flow 20% hold 60% (Potomac) / 40% (Wolf).
- Pumping persist is near-uniform: lowest-flow 20% hold only 23% / 29% at 1e-5 (uniform would be 20%).
- Potomac pumping even slightly prefers *higher*-flow cells (ρ = +0.10 vs drought −0.17).
- Wolf still has a weak low-flow slope under pumping (ρ = −0.29), but far less mass concentration than drought.

## Reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
cd /glade/derecho/scratch/bwest/drought-ensemble
python analysis/pumping_overland_persist.py
```

