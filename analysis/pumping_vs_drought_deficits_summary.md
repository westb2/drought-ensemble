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
| Potomac | 3-yr drought | 81.0 | 55.2 | 0.59 |
| Potomac | pumping 1e-07 | 1.9 | 8.1 | 0.19 |
| Potomac | pumping 1e-06 | 12.0 | 78.8 | 0.13 |
| Potomac | pumping 1e-05 | 108.8 | 810.7 | 0.12 |
| Potomac | pumping 1e-04 | 517.2 | 9320.2 | 0.05 |
| Wolf | 3-yr drought | 122.8 | 27.1 | 0.82 |
| Wolf | pumping 1e-07 | 0.9 | 2.7 | 0.25 |
| Wolf | pumping 1e-06 | 4.8 | 27.8 | 0.15 |
| Wolf | pumping 1e-05 | 40.8 | 297.5 | 0.12 |
| Wolf | pumping 1e-04 | 207.9 | 3612.8 | 0.05 |

## Depth split (3-yr drought vs pumping 1e-5)

| Domain | Case | Temp NS | Temp deep | Persist NS | Persist deep |
|--------|------|--------:|----------:|-----------:|-------------:|
| Potomac | 3-yr drought | 17.6 | 16.5 | 25.9 | 29.1 |
| Potomac | pumping 1e-5 | 2.1 | 48.8 | 7.9 | 802.7 |
| Wolf | 3-yr drought | 122.6 | 0.2 | 0.7 | 26.5 |
| Wolf | pumping 1e-5 | 2.2 | 26.7 | 6.1 | 291.4 |

## Takeaways

- **Potomac** 3-yr drought: f_temp=0.59 (81 / 55 ×10⁶ m³ temp/persist).
- **Potomac** pumping 1e-5: f_temp=0.12 (109 / 811) — little drought-style temporary pool.
- **Wolf** 3-yr drought: f_temp=0.82 (123 / 27 ×10⁶ m³ temp/persist).
- **Wolf** pumping 1e-5: f_temp=0.12 (41 / 297) — little drought-style temporary pool.
- Drought deficit falls sharply in recovery year 1 then plateaus; pumping deficit stays.
- Drought temporary mass is near-surface; pumping leftover is deep (layer-2 extraction).

## Reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
cd /glade/derecho/scratch/bwest/drought-ensemble
python analysis/pumping_vs_drought_deficits.py
```

