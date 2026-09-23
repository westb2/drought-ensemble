# Annualized outlet Q through pumping and recovery

**Date:** August 2026  
**Script:** [`pumping_annualized_q.py`](pumping_annualized_q.py)  
Annualized Q = yearly-mean outlet overland flow × 8760 h, as 10⁶ m³/yr.  
Sequence: 40 yr average spinup + **3 yr pumping** + **10 yr recovery** (average forcing).

## Figures

- [pumping_annualized_q_course.png](figures/pumping_exploratory/pumping_annualized_q_course.png)
- [pumping_annualized_q_ratio_recovery.png](figures/pumping_exploratory/pumping_annualized_q_ratio_recovery.png)
- [pumping_annualized_q_milestones.png](figures/pumping_exploratory/pumping_annualized_q_milestones.png)

## Annualized Q / baseline

| Domain | Rate | Pump yr1 | Pump yr3 | Rec yr1 | Rec yr5 | Rec yr10 |
|--------|------|---------:|---------:|--------:|--------:|---------:|
| Potomac | 1e-07 | 1.000 | 1.001 | 0.999 | 1.000 | 0.999 |
| Potomac | 1e-06 | 1.000 | 0.991 | 0.988 | 0.991 | 0.994 |
| Potomac | 1e-05 | 0.989 | 0.893 | 0.865 | 0.924 | 0.954 |
| Potomac | 1e-04 | 0.938 | 0.542 | 0.491 | 0.479 | 0.486 |
| Wolf | 1e-07 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Wolf | 1e-06 | 0.999 | 0.997 | 0.997 | 0.999 | 0.999 |
| Wolf | 1e-05 | 0.994 | 0.977 | 0.977 | 0.988 | 0.993 |
| Wolf | 1e-04 | 0.973 | 0.939 | 0.935 | 0.936 | 0.943 |

## Takeaways

- **Potomac** 1e-5: pump yr1=0.99, yr3=0.89; rec yr1=0.86, yr5=0.92, yr10=0.95.
- **Potomac** 1e-4: pump yr3=0.54; rec yr1=0.49, yr10=0.49.
- **Wolf** 1e-5: pump yr1=0.99, yr3=0.98; rec yr1=0.98, yr5=0.99, yr10=0.99.
- **Wolf** 1e-4: pump yr3=0.94; rec yr1=0.93, yr10=0.94.
- Low rates (1e-7 / 1e-6) stay near baseline through pumping and recovery.
- Recovery is the test of capture vs drought-style shielding: if Q rebounds in yr1, the Q hit was mostly temporary; leftover at yr10 is persistent coupling.

## Reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
cd /glade/derecho/scratch/bwest/drought-ensemble
python analysis/pumping_annualized_q.py
```

