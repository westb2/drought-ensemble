# Matched-deficit pumping rate (10-yr stress)

**Script:** [`matched_deficit_10yr.py`](matched_deficit_10yr.py)  
**Figure:** [matched_deficit_10yr_rate_curve.png](figures/matched_deficit_10yr_rate_curve.png)

Deficit = `short_baseline` − member column storage at year index 49 (40 spinup + 10 stress), per-cell clipped at zero, summed over active cells. Drought and pumping now share a 10-year stress length.

The `5e-7`–`5e-6` bracket members end at year 49 and are complete. The `1e-7`–`1e-4` members carry a 10-yr recovery tail that is still running, but their year-49 state is final, so they contribute to the rate curve.

## End-of-stress deficits (10⁶ m³)

| Domain | Case | Total | Net |
|--------|------|------:|----:|
| Potomac | 10-yr drought | 205 | 167 |
| Potomac | pumping 1e-7 | 24 | 24 |
| Potomac | pumping 5e-7 | 118 | 118 |
| Potomac | pumping 8.64e-7 | 205 | 205 |
| Potomac | pumping 1e-6 | 237 | 237 |
| Potomac | pumping 2e-6 | 477 | 477 |
| Potomac | pumping 2.49e-6 | 596 | 596 |
| Potomac | pumping 3e-6 | 720 | 720 |
| Potomac | pumping 5e-6 | 1228 | 1228 |
| Potomac | pumping 1e-5 | 2628 | 2628 |
| Potomac | pumping 1e-4 | 29788 | 29788 |
| Wolf | 10-yr drought | 204 | 204 |
| Wolf | pumping 1e-7 | 8 | 8 |
| Wolf | pumping 5e-7 | 39 | 39 |
| Wolf | pumping 8.64e-7 | 68 | 68 |
| Wolf | pumping 1e-6 | 79 | 79 |
| Wolf | pumping 2e-6 | 161 | 161 |
| Wolf | pumping 2.49e-6 | 203 | 203 |
| Wolf | pumping 3e-6 | 248 | 248 |
| Wolf | pumping 5e-6 | 430 | 430 |
| Wolf | pumping 1e-5 | 935 | 935 |
| Wolf | pumping 1e-4 | 12102 | 12102 |

## Matched rates

| Domain | 10-yr drought target | Matched rate (m/h) | Bracketed by runs |
|--------|---------------------:|-------------------:|-------------------|
| Potomac | 205 | 8.64e-07 | yes |
| Wolf | 204 | 2.49e-06 | yes |

## Reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
cd /glade/derecho/scratch/bwest/drought-ensemble
python analysis/matched_deficit_10yr.py
```

