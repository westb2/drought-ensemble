# Pumping impact on streamflow (preliminary)

**Date:** August 2026  
**Script:** [`pumping_streamflow_impact.py`](pumping_streamflow_impact.py)  
**Question:** How does 3-year pumping change outlet streamflow vs average-year baseline, and does Q track deep storage loss the way drought Q did not?

No recovery years on disk yet — metrics are **during pumping** only.

## Figures

- [pumping_streamflow_q_ratio.png](figures/pumping_exploratory/pumping_streamflow_q_ratio.png)
- [pumping_streamflow_q_ratio_bars.png](figures/pumping_exploratory/pumping_streamflow_q_ratio_bars.png)
- [pumping_streamflow_q_ratio_by_year.png](figures/pumping_exploratory/pumping_streamflow_q_ratio_by_year.png)
- [pumping_streamflow_dq_vs_ds.png](figures/pumping_exploratory/pumping_streamflow_dq_vs_ds.png)
- Existing context: [pumping_during_totals_and_anomalies.png](figures/pumping_exploratory/pumping_during_totals_and_anomalies.png), [pumping_course_streamflow_storage.png](figures/pumping_exploratory/pumping_course_streamflow_storage.png)

## Mean outlet Q / baseline by pump year

| Domain | Rate | Yr1 | Yr2 | Yr3 |
|--------|------|----:|----:|----:|
| Potomac | 1e-07 | 1.001 | 1.001 | 1.003 |
| Potomac | 1e-06 | 1.003 | 0.990 | 0.985 |
| Potomac | 1e-05 | 0.971 | 0.878 | 0.801 |
| Potomac | 1e-04 | 0.847 | 0.395 | 0.226 |
| Wolf | 1e-07 | 1.000 | 1.001 | 0.998 |
| Wolf | 1e-06 | 0.997 | 0.994 | 0.990 |
| Wolf | 1e-05 | 0.977 | 0.938 | 0.913 |
| Wolf | 1e-04 | 0.890 | 0.791 | 0.764 |

## Pump year 3 percentiles (Q / baseline)

| Domain | Rate | Mean | p50 | p90 | End ΔS (10⁶ m³) |
|--------|------|-----:|----:|----:|----------------:|
| Potomac | 1e-07 | 1.003 | 1.000 | 1.004 | -24 |
| Potomac | 1e-06 | 0.985 | 0.994 | 0.999 | -237 |
| Potomac | 1e-05 | 0.801 | 0.877 | 0.969 | -2628 |
| Potomac | 1e-04 | 0.226 | 0.000 | 0.844 | -29788 |
| Wolf | 1e-07 | 0.998 | 1.000 | 1.000 | -8 |
| Wolf | 1e-06 | 0.990 | 0.996 | 0.999 | -79 |
| Wolf | 1e-05 | 0.913 | 0.968 | 0.991 | -935 |
| Wolf | 1e-04 | 0.764 | 0.901 | 0.975 | -12102 |

## Takeaways (early)

- **Potomac** at 1e-5: mean Q/baseline yr1=0.97, yr3=0.80 (1e-7 yr3=1.00).
- **Potomac** (1e-5): mean Q keeps falling from yr1→yr3 (not a pure mid-drought plateau).
- **Wolf** at 1e-5: mean Q/baseline yr1=0.98, yr3=0.91 (1e-7 yr3=1.00).
- **Wolf** (1e-5): mean Q keeps falling from yr1→yr3 (not a pure mid-drought plateau).
- Low rates (1e-7) leave outlet Q near baseline; high rates (1e-4) strongly suppress flow.
- Contrast with 50-yr drought: there, deep storage grew for decades while Q plateaued. Under pumping, check whether ΔQ tracks ΔS in `pumping_streamflow_dq_vs_ds.png` — capture-style coupling can appear even without drying the precip forcing.
- Outlet p10≈0 on baseline still limits classical baseflow ratios (same caveat as drought).
- Recovery years will show whether Q rebounds with the near-surface skin or stays suppressed with deep memory.

## Reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
cd /glade/derecho/scratch/bwest/drought-ensemble
python analysis/pumping_streamflow_impact.py
```

