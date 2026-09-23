# Annualized outlet Q through pumping and recovery

**Script:** [`pumping_annualized_q.py`](pumping_annualized_q.py)  
Annualized Q = yearly-mean outlet overland flow × 8760 h, as 10⁶ m³/yr.  
Sequence: 40 yr average spinup + **10 yr pumping** + **5 yr recovery** (average forcing).

## Figures

- [ten_year_pumping_annualized_q_course.png](figures/pumping_exploratory/ten_year_pumping_annualized_q_course.png)
- [ten_year_pumping_annualized_q_ratio_recovery.png](figures/pumping_exploratory/ten_year_pumping_annualized_q_ratio_recovery.png)
- [ten_year_pumping_annualized_q_milestones.png](figures/pumping_exploratory/ten_year_pumping_annualized_q_milestones.png)

## Annualized Q / baseline

| Domain | Rate | Pump yr1 | Pump yr10 | Rec Yr1 | Rec Yr5 |
|--------|------|---------:|---------:|---------:|---------:|
| Potomac | 1e-07 | 1.000 | 0.858 | 0.999 | 1.001 |
| Potomac | 1e-06 | 1.000 | 0.832 | 0.969 | 0.982 |
| Potomac | 1e-05 | 0.989 | 0.193 | 0.703 | 0.809 |
| Potomac | 1e-04 | 0.938 | 0.090 | 0.455 | 0.453 |
| Wolf | 1e-07 | 1.000 | 0.932 | 0.999 | 1.000 |
| Wolf | 1e-06 | 0.999 | 0.927 | 0.995 | 0.997 |
| Wolf | 1e-05 | 0.994 | 0.891 | 0.963 | 0.974 |
| Wolf | 1e-04 | 0.973 | 0.850 | 0.923 | 0.923 |

## Takeaways

- **Potomac** 1e-5: pump yr1=0.99, yr10=0.19, rec yr1=0.70, yr5=0.81.
- **Wolf** 1e-5: pump yr1=0.99, yr10=0.89, rec yr1=0.96, yr5=0.97.
- Low rates (1e-7 / 1e-6) stay near baseline through pumping and recovery.

## Reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
cd /glade/derecho/scratch/bwest/drought-ensemble
PUMPING_STRESS_YEARS=10 python analysis/run_10yr_pumping_analyses.py annualized_q
```

