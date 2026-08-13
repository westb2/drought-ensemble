# USGS streamflow validation summary

**Date:** August 2026  
**Notebook:** [`average_year_usgs_validation.ipynb`](average_year_usgs_validation.ipynb)  
**Figures:** [`figures/`](figures/) (`average_year_usgs_*.png`, `drought_year_usgs_start_vs_end_*.png`)

ParFlow `overland_flow` at drainage-matched USGS gages vs NWIS daily discharge. Model values are 219 h means; USGS is block-averaged onto the same windows. Metrics: NSE, KGE, PBIAS, correlation (r).

---

## Setup

| Domain | HUC | Average WY | Dry WY | Validation gage | Why this gage |
|--------|-----|------------|--------|-----------------|---------------|
| Potomac (`potomac2`) | `02070001` | 2005 | 1999 | **`01608500`** Springfield, WV (~1461 mi²) | Matches basin / outlet scale. Config gage `01607500` Brandywine is only ~103 mi². |
| Wolf (`wolf2`) | `08010210` | 2008 | 2007 | **`07030500`** Rossville, TN (~503 mi²) | Config reference gage. |

Gage locations are mapped to the 1 km grid and **snapped to the nearest channel cell** (high mean overland flow). Config outlets are not always on the mainstem (notably Potomac `(66, 135)`).

Forcing years repeat (same average or dry CW3E water year). Differences between “start” and “end” therefore reflect **antecedent storage**, not different meteorology.

---

## 1. Average year after transient spinup

Post-spinup average year (`short_baseline` year index 40 ≈ 39) vs USGS for the average water year.

| Domain | WY | NSE | KGE | PBIAS | r | Sim / obs mean (m³/s) |
|--------|-----|-----|-----|-------|---|------------------------|
| Potomac | 2005 | 0.05 | 0.33 | −44% | 0.56 | 21.3 / 38.2 |
| Wolf | 2008 | 0.40 | 0.33 | +40% | 0.94 | 25.7 / 18.3 |

Wolf timing tracks well (high r) but runs high. Potomac is biased low with weaker skill.

---

## 2. Average year: out of steady state vs end of spinup

Same average WY and gage; year **0** (first year after steady-state IC) vs year **39** (end of 40-year average spinup).

| Domain | Phase | NSE | KGE | PBIAS | Sim mean (m³/s) |
|--------|-------|-----|-----|-------|-----------------|
| Potomac | Out of SS (y0) | **0.34** | **0.60** | −16% | 32.2 |
| Potomac | End spinup (y39) | 0.05 | 0.33 | −44% | 21.3 |
| Wolf | Out of SS (y0) | 0.20 | 0.20 | +59% | 29.1 |
| Wolf | End spinup (y39) | **0.40** | **0.33** | +40% | 25.7 |

**Δ (end − SS):** Potomac ΔNSE −0.29, ΔKGE −0.27 — skill **worse** after spinup (mean flow drops). Wolf ΔNSE +0.20, ΔKGE +0.13 — skill **better** (wet SS bias relaxes). Year 39 ≈ year 40 for both.

---

## 3. Drought (dry) year: start vs end of drought

Same dry WY repeated every drought year. **Start** = first dry year after average spinup (index 40). **End** = last dry year (index `40 + L − 1`). Members: `3_year_drought`, `10_year_drought`.

| Domain | Drought length | Start NSE / KGE | End NSE / KGE | Start→end PBIAS |
|--------|----------------|-----------------|---------------|-----------------|
| Potomac | 3 yr | 0.19 / 0.52 | 0.23 / 0.51 | −29% → −32% |
| Potomac | 10 yr | 0.19 / 0.52 | 0.23 / 0.50 | −29% → −33% |
| Wolf | 3 yr | −0.28 / 0.17 | −0.11 / 0.42 | −28% → −52% |
| Wolf | 10 yr | −0.28 / 0.17 | −0.11 / 0.41 | −28% → −53% |

Potomac barely changes after prior dry years. Wolf dries further (more negative PBIAS) while KGE rises; **3-year end ≈ 10-year end**, so most of the memory effect appears within the first few dry years.

---

## Takeaways

1. **Gage choice matters** — use Springfield (`01608500`) for Potomac outlet-scale checks, not Brandywine.
2. **Antecedent conditions matter as much as the forcing year** — average-year skill differs strongly y0 vs y39; dry-year skill (especially Wolf) differs drought start vs end.
3. **Domains behave differently** — Potomac validates better out of SS and degrades over average spinup; Wolf validates better after spinup and is sensitive to multi-year drought memory.
4. **Spun-up average-year Q** is biased low (Potomac) / high (Wolf) by tens of percent vs USGS; treat ensemble streamflow anomalies relative to the model baseline rather than as absolute USGS matches unless bias-corrected.

---

## How to reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
cd /glade/derecho/scratch/bwest/drought-ensemble
jupyter notebook analysis/average_year_usgs_validation.ipynb
```
