# USGS streamflow validation (agent notes)

Lessons from Aug 2026 average / drought-year outlet validation for **potomac2** and **wolf2**.  
Canonical notebook: `analysis/average_year_usgs_validation.ipynb`  
User-facing summary: `analysis/usgs_streamflow_validation_summary.md`  
Figures: `analysis/figures/average_year_usgs_*.png`, `drought_year_usgs_start_vs_end_*.png`

Use this when validating domains against NWIS, picking gages, mapping gage→local cells, or interpreting spinup/drought antecedent effects on Q skill.

## Domains and years

| Domain | HUC8 | Average WY | Dry WY | Config `CURRENT_REFERENCE_GAGE` |
|--------|------|------------|--------|----------------------------------|
| `potomac2` | `02070001` | **2005** | **1999** | `01607500` (SF Brandywine, ~103 mi²) |
| `wolf2` | `08010210` | **2008** | **2007** | `07030500` (Rossville, ~503 mi²) |

Forcing calendar (from `Domain.get_domain_year`): water year `{Y-1}-10-01` → `{Y}-10-01`.

Sequences reuse the same wetness year repeatedly (average or dry). Antecedent storage — not a different met year — is what changes between spinup y0, end-spinup, drought start, and drought end.

## Which USGS gage to use

**Do not** blindly use `CURRENT_REFERENCE_GAGE` for domain-outlet validation.

| Domain | Validation gage used | Why |
|--------|----------------------|-----|
| Potomac | **`01608500`** South Branch near Springfield, WV (~1461 mi²) | Matches HUC / domain drainage (~3727 km²). Config `01607500` is a small SF headwater. |
| Wolf | **`07030500`** Wolf River at Rossville, TN | Config reference; mid-basin but nearest major gage with WY2007–08 DV. Snap to channel (see below). |

Config outlet `(OUTLET_X, OUTLET_Y)` is **not** always the high-flow cell:

- Potomac config outlet `(66, 135)` ≈ dry; mainstem / Springfield snap ≈ `(63, 129)`.
- Wolf config outlet `(18, 21)` is on the mainstem; Rossville raw map `(26, 22)` is off-channel — snap within ~3 cells to high `overland_flow` (≈ `(23, 21)`).

## Mapping gage → local cell

1. `hf_hydrodata.from_latlon("conus2", lat, lon)` → fractional CONUS2 (i, j).
2. Domain origin from `drv_vegm.dat` (1-based i,j + lat/lon):  
   `i0, j0 = round(ci - i), round(cj - j)` for any vegm point.
3. Local raw: `x0, y0 = round(ci - i0), round(cj - j0)` (0-based NetCDF indices).
4. **Snap** to max `mean(overland_flow)` within radius 3 (1 km grid misalignment is common).

No HF API pin needed for `from_latlon`. NWIS via REST (`waterservices.usgs.gov`) — `dataretrieval` may be absent in `droughts` env; use `requests`.

## Model data to sample

- Prefer **219 h** `processed_output_219h.nc` via `file_locations_219h.json`.
- Variable: `overland_flow` (m³/h) at snapped (x, y) → ÷3600 → m³/s.
- Member for average / spinup contrast: `droughts/short_baseline` (all average years).
- Drought contrast: `droughts/{3,10}_year_drought`; dry years at indices `40` (start) and `40+L-1` (end). Spinup is 40 years (`SPINUP_YEAR_INDEX = 40`).

USGS daily: block-average onto 219 h windows centered on model timestamps for NSE / KGE / PBIAS / r / RSR(log₁₀).

## What the metrics showed (Aug 2026)

Units: m³/s at snapped gage cell; same USGS WY for all phases of a given wetness.

### Average WY — post-spinup (y40 ≈ y39)

| Domain | NSE | KGE | PBIAS | r |
|--------|-----|-----|-------|---|
| Potomac WY2005 | 0.05 | 0.33 | −44% | 0.56 |
| Wolf WY2008 | 0.40 | 0.33 | +40% | 0.94 |

### Average WY — out of steady state (y0) vs end transient spinup (y39)

| Domain | Phase | NSE | KGE | PBIAS |
|--------|-------|-----|-----|-------|
| Potomac | y0 (out of SS) | **0.34** | **0.60** | −16% |
| Potomac | y39 (end spinup) | 0.05 | 0.33 | −44% |
| Wolf | y0 (out of SS) | 0.20 | 0.20 | +59% |
| Wolf | y39 (end spinup) | **0.40** | **0.33** | +40% |

**Lesson:** Antecedent state dominates average-year skill. Potomac looks **better right out of SS** (higher Q, less dry bias); after 40 yr average spinup mean Q drops and skill worsens. Wolf is **too wet out of SS**; spinup reduces high bias and improves NSE/KGE. y39 ≈ y40 (spinup effectively settled for Q).

### Dry WY — drought start (y40) vs drought end (y42 / y49)

Same dry forcing (Potomac WY1999, Wolf WY2007); antecedent = average spinup vs prior dry years.

| Domain | L | start NSE/KGE | end NSE/KGE | Notes |
|--------|---|---------------|-------------|-------|
| Potomac | 3 or 10 | 0.19 / 0.52 | ~0.23 / ~0.50 | Small change; slightly drier |
| Wolf | 3 or 10 | −0.28 / 0.18 | −0.11 / ~0.41 | Large effect; much drier (PBIAS −28%→−53%); KGE up; 3-yr end ≈ 10-yr end |

**Lesson:** Prior drought years matter more for **Wolf** than Potomac. Most Wolf adjustment happens within the first ~3 dry years.

## Operational takeaways for agents

1. Validate at **drainage-matched** gages + **channel-snapped** cells, not raw config outlet / small headwater gages.
2. Always state **which model year index** (y0 / y39 / drought start / end) — skill is not invariant to IC.
3. Do not treat “average year validation” as a single number; report SS-exit vs spun-up if discussing spinup adequacy.
4. For drought forcing skill, compare **start vs end** of multi-year drought (3 and 10); 1-year has start==end.
5. Display names on figures: Potomac / Wolf (not `potomac2` / `wolf2`). Follow [plotting.md](plotting.md).
6. Env: `/glade/work/bwest/conda-envs/droughts` (has xarray, hf_hydrodata, requests; often no `dataretrieval`).

## Do not

- Compare domain outlet Q to `01607500` without noting the ~103 mi² mismatch.
- Sample Potomac at config outlet `(66,135)` for validation (near-zero flow).
- Assume Wolf gage lat/lon cell is on the river without snapping.
- Claim spinup is “validated” from y0 alone, or ignore that Potomac Q skill degrades over transient spinup.
