# Pumping vs drought storage deficits

**Date:** August 2026  
**Script:** [`pumping_vs_drought_deficits.py`](pumping_vs_drought_deficits.py)  
Same 3-year stress length. Temporary = recovered in recovery year 1; persistent = remaining. Near-surface = top 2 m (z≥6).

## Figures

- [pumping_vs_drought_temp_persist_bars.png](figures/pumping_exploratory/pumping_vs_drought_temp_persist_bars.png)
- [pumping_vs_drought_fractional_recovery.png](figures/pumping_exploratory/pumping_vs_drought_fractional_recovery.png)
- [pumping_vs_drought_ds_recovery.png](figures/pumping_exploratory/pumping_vs_drought_ds_recovery.png)
- [pumping_vs_drought_depth_partition.png](figures/pumping_exploratory/pumping_vs_drought_depth_partition.png)

## Domain totals (10⁶ m³)

| Domain | Case | Temporary | Persistent | f_temp |
|--------|------|----------:|-----------:|-------:|
| Potomac | 3-yr drought | 88.0 | 125.6 | 0.41 |
| Potomac | pumping 1e-07 | 2.4 | 22.6 | 0.09 |
| Potomac | pumping 1e-06 | 18.9 | 225.4 | 0.08 |
| Potomac | pumping 1e-05 | 146.9 | 2551.0 | 0.05 |
| Potomac | pumping 1e-04 | 614.0 | 29734.6 | 0.02 |
| Wolf | 3-yr drought | 127.1 | 76.4 | 0.62 |
| Wolf | pumping 1e-07 | 1.1 | 7.0 | 0.14 |
| Wolf | pumping 1e-06 | 7.9 | 72.1 | 0.10 |
| Wolf | pumping 1e-05 | 55.2 | 888.4 | 0.06 |
| Wolf | pumping 1e-04 | 276.2 | 12011.1 | 0.02 |

## Depth split (3-yr drought vs pumping 1e-5)

| Domain | Case | Temp NS | Temp deep | Persist NS | Persist deep |
|--------|------|--------:|----------:|-----------:|-------------:|
| Potomac | 3-yr drought | 23.1 | 18.2 | 32.6 | 92.8 |
| Potomac | pumping 1e-5 | 1.1 | 75.5 | 13.0 | 2538.0 |
| Wolf | 3-yr drought | 124.1 | 3.1 | 1.5 | 74.9 |
| Wolf | pumping 1e-5 | 1.6 | 44.6 | 10.8 | 877.6 |

## Takeaways

- **Potomac** 3-yr drought: f_temp=0.41 (88 / 126 ×10⁶ m³ temp/persist).
- **Potomac** pumping 1e-5: f_temp=0.05 (147 / 2551) — little drought-style temporary pool.
- **Wolf** 3-yr drought: f_temp=0.62 (127 / 76 ×10⁶ m³ temp/persist).
- **Wolf** pumping 1e-5: f_temp=0.06 (55 / 888) — little drought-style temporary pool.
- Drought deficit falls sharply in recovery year 1 then plateaus; pumping deficit stays.
- Drought temporary mass is near-surface; pumping leftover is deep (layer-2 extraction).

## Reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
cd /glade/derecho/scratch/bwest/drought-ensemble
python analysis/pumping_vs_drought_deficits.py
```

