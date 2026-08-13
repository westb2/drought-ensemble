# WTD thresholding vs overland (10-yr)

**Script:** `analysis/wtd_threshold_vs_overland.py`  
**Figures:** `wtd_threshold_vs_overland_{binned_means,skill,2d_bins}.png`

## Verdict

1. **Thresholding does not make WTD beat overland on Potomac** for persistent magnitude. Linear WTD skill is ~0; a best single step only reaches R²≈0.08 (bin R²≈0.09). Overland stays dominant (step R²≈0.32; lowest-20% overland cells hold **65%** of persistent mass).
2. **On Wolf, WTD already wins — and a ~4.5 m step makes it clearer.** Persistent step R²≈0.41 (vs participation 0.17 / log-overland 0.12); deepest-20% WTD holds **61%** of persistent mass. For \(f_\mathrm{temp}\), WTD step R²≈0.57 vs overland ~0.11–0.12.
3. **Combinations help modestly, domain-dependently:**
   - Potomac: WTD×log-overland bin R²≈0.39 vs log-overland alone 0.34 — small gain. 2-D bins show **low overland is the gate**; WTD only modulates inside that gate.
   - Wolf: WTD×participation dual-threshold R²≈0.51 > WTD alone 0.41 for persistent. For \(f_\mathrm{temp}\), WTD alone is enough (combo does not beat it).
4. **Distance-to-stream** remains weak alone and in combo with overland.

## Skill metrics (non-stream cells with deficit)

| Metric | Meaning |
|--------|---------|
| \|Spearman ρ\| | Monotonic / rank-linear |
| Step / dual-thr R² | Best single threshold (or 4-regime dual thresholds for combos) |
| Quantile-bin R² | Equal-count bin means (flexible nonlinear, in-sample) |

## Potomac (n=3579)

| Response | Predictor | \|ρ\| | step/dual R² | bin R² | top-20% persist mass |
|----------|-----------|----:|-------------:|-------:|---------------------:|
| persistent | log_overland | 0.429 | 0.321 | 0.343 | 0.65 |
| persistent | participation | 0.474 | 0.291 | 0.338 | 0.62 |
| persistent | wtd | 0.032 | 0.076 | 0.090 | 0.20 |
| persistent | dist_km | 0.210 | 0.020 | 0.047 | 0.10 |
| persistent | wtd+log_overland | — | 0.303 | 0.387 | — |
| persistent | wtd+participation | — | 0.304 | 0.375 | — |
| persistent | log_overland+dist | — | 0.311 | 0.385 | — |
| f_temp | log_overland | 0.060 | 0.005 | 0.019 | — |
| f_temp | participation | 0.132 | 0.019 | 0.024 | — |
| f_temp | wtd | 0.059 | 0.032 | 0.116 | — |
| f_temp | wtd+log_overland | — | 0.048 | 0.124 | — |
| f_temp | wtd+participation | — | 0.063 | 0.142 | — |

Best WTD step for persistent ≈ **2.4 m** (weak Δ).

## Wolf (n=1426)

| Response | Predictor | \|ρ\| | step/dual R² | bin R² | top-20% persist mass |
|----------|-----------|----:|-------------:|-------:|---------------------:|
| persistent | log_overland | 0.340 | 0.120 | 0.145 | 0.42 |
| persistent | participation | 0.539 | 0.168 | 0.211 | 0.44 |
| persistent | wtd | 0.504 | 0.408 | 0.401 | 0.61 |
| persistent | dist_km | 0.296 | 0.017 | 0.031 | 0.14 |
| persistent | wtd+log_overland | — | 0.375 | 0.287 | — |
| persistent | wtd+participation | — | 0.512 | 0.384 | — |
| persistent | log_overland+dist | — | 0.139 | 0.175 | — |
| f_temp | log_overland | 0.262 | 0.116 | 0.148 | — |
| f_temp | participation | 0.290 | 0.113 | 0.195 | — |
| f_temp | wtd | 0.537 | 0.565 | 0.559 | — |
| f_temp | wtd+log_overland | — | 0.522 | 0.463 | — |
| f_temp | wtd+participation | — | 0.541 | 0.491 | — |

Best WTD step for persistent ≈ **4.5 m** (clear regime break in binned means).
