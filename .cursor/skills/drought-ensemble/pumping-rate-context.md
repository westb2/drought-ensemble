# Catchment & pumping context (reference only)

**User controls `pumping_rate_fraction`.** Do not pick, change, or “recommend” a pumping rate unless the user explicitly asks you to choose one. When comparing model rates to observations, report the math and leave the decision to the user.

Use this doc when:
- Comparing a user-specified rate to USGS consumptive use / withdrawals
- Exploring **new catchments/HUCs** for subset domains (especially if looking for places that both see real pumping stress and are plausible in ParFlow CONUS)
- Explaining geology / drawdown context for Potomac vs Coastal Plain
- Revisiting the **Jul 2026 HUC validation rankings** or the **geologic-diversity ensemble shortlist** (`02070001` / `02070008` / Coastal Plain)

## Units and conversion

- Sequence field `pumping_rate_fraction` = **domain-average** extraction depth rate in **m/h** (after the cropland-fraction fix in `Run.py`).
- potomac2: **3727** active 1 km cells → **3727 km²** for volume math (WBD HUC8 area for `02070001` ≈ 3833 km²).
- potomac2 cropland fraction ≈ **0.133** (496/3727); pumping layer `dz` = **50** m.
- Volume: `V_year = R × area_m² × 8760`.
- MGD ↔ domain-average m/h:

```text
m_per_h = (MGD × 3785.411784 / 24) / area_m²
MGD     = (m_per_h × area_m² × 24) / 3785.411784
```

### potomac2 rate ladder (for comparison only)

| User-set `pumping_rate_fraction` | mm/yr | ≈ MGD on potomac2 |
|----------------------------------|-------|-------------------|
| `1e-7` | 0.88 | 2.36 |
| `1e-6` | 8.8 | 23.6 |
| `1e-5` | 88 | 236 |
| `1e-4` | 876 | 2360 |

## Fetching USGS water-use context for a HUC

Config HUC lives in `domains/<domain>/config.ini` as `HUC_ID` (e.g. potomac2 → **`02070001`** South Branch Potomac; gage `01607500`).

NWDC API (public-supply + irrigation; annual calendar year). **PS+IRR only** — no thermoelectric/industrial/mining in these endpoints:

```text
https://api.water.usgs.gov/nwaa-data/data?model=wu-public-supply-cu&variable=pscutot
  &timeRes=annualcy&startDate=2010&endDate=2020&location=huc8:HHHHHHHH
  &intersection=overlap&limit=600&format=json&skip=0
# also: model=wu-irrigation-cu&variable=irrcutot
# withdrawals: wu-public-supply-wd / pswdtot , wu-irrigation-wd / irrwdtot
```

- Paginate: `skip += recordsReturned` until `skip >= totalRecords` (max `limit=600`).
- Keep only returned HUC12 IDs that **startswith** the requested HUC8.
- Convert basin total MGD → domain-average m/h with WBD `areasqkm` (or mask cell count for in-model volume).

### Snapshot used in Jul 2026 analysis (means 2010–2020)

| HUC8 | Name | PS+IRR CU (MGD) | ≈ CU depth (m/h) | Notes |
|------|------|-----------------|------------------|-------|
| `02070001` | South Branch (potomac2) | ~0.12 | ~5×10⁻⁹ | PS withdrawals ~2.1 MGD |
| `02070002` | North Branch | ~1.3 | ~6×10⁻⁸ | adjacent |
| `02070003` | Cacapon | ~0.02 | ~1×10⁻⁹ | adjacent |
| `02070004`–`07`, `09`, `11` | Shenandoah / Monocacy / Lower Potomac | — | ~0.7–2.5×10⁻⁷ | upper/mid Potomac |
| `02070008` | Middle Potomac–Catoctin | ~26 | ~1.3×10⁻⁶ | metro / Fall Line |
| `02070010` | Anacostia–Occoquan | ~93 | ~4.4×10⁻⁶ | metro / Fall Line |

Compare **depth rates** (m/h or mm/yr), not raw MGD alone.

## Geology / drawdown context (Potomac region)

- **South Branch / potomac2:** Valley & Ridge fractured / carbonate rock; local flow; drought-sensitive. Not the classic multi-decade confined-aquifer drawdown setting.
- **Documented long-term pumping drawdowns** in the broader Potomac/Chesapeake region are mainly **Atlantic Coastal Plain** confined aquifers (Potomac–Patapsco / Patuxent group): tens to 100–200+ ft declines; some land subsidence (esp. VA Coastal Plain / Hampton Roads).
- Name collision: sedimentary **“Potomac aquifer”** ≠ South Branch Potomac watershed geology.
- High-CU Potomac HUCs (`02070008`, `02070010`) are **Piedmont / Coastal Plain / Fall Line**, not Valley & Ridge analogues.
- Coastal Plain has both **native headwaters** (originate east of Fall Line) and **Fall Line–crossing** basins (Piedmont headwaters → Coastal Plain lower reaches). `02070011` Lower Potomac is Coastal Plain but low CU depth in the NWDC PS+IRR snapshot.

## HUC8s with higher CU intensity (candidates to explore — not rate prescriptions)

Useful when the user wants catchments where real-world PS+IRR consumptive use is closer to higher domain-average depths. **Still ask / wait for the user to set the pumping rate.**

Higher CU depth (NWDC PS+IRR / WBD area), Mid-Atlantic:

| HUC8 | Name | ≈ CU depth | Setting |
|------|------|------------|---------|
| `02070010` | Middle Potomac–Anacostia–Occoquan | ~4×10⁻⁶ | metro Potomac |
| `02080109` | Nanticoke | ~3×10⁻⁶ | Delmarva Coastal Plain |
| `02080108` | Lynnhaven–Poquoson | ~2×10⁻⁶ | Hampton Roads CP |
| `02080208` | Hampton Roads | ~1.7×10⁻⁶ | confined Potomac-aquifer stress |
| `02060002` | Chester–Sassafras | ~1.7×10⁻⁶ | MD Coastal Plain |
| `02070008` | Middle Potomac–Catoctin | ~1.3×10⁻⁶ | metro Potomac |
| `02060006` | Patuxent | ~1.0×10⁻⁶ | MD Coastal Plain |
| `02060003` | Gunpowder–Patapsco | ~9×10⁻⁷ | Baltimore-area CP |

Also noted (~0.5–0.6×10⁻⁶): `02080206` Lower James, `02060004` Severn, `02080110` Tangier, `02080111` Pocomoke–Western Lower Delmarva.

Current ensemble Potomac domains all use **`02070001`** (low CU depth in this snapshot).

## ParFlow CONUS validation — guidance for testing catchments

Domains in this project are CONUS2 subsets (`subsettools` / HydroData). National-model evaluation (Yang et al. 2024 CONUS 2.0; O'Neill et al. 2021 CONUS 1.0) is the backdrop when another agent screens catchments.

### How to access validation inputs (Jul 2026 note)
- **`subsettools` does not ship HUC validation scores** — it subsets domains and inputs.
- Use **`hf_hydrodata`** (same HydroFrame stack): CONUS2 gridded fields + USGS point obs, then compute metrics.
- Practical recipe used below: sample `conus2_baseline` monthly `streamflow` (WY2003 mean, m³/h → m³/s) at USGS gage `conus2_i/j`, compare to gage mean Q (1990–2019), **RSR on log₁₀ Q**. Steady-state `ss_water_table_depth` is available for WTD checks; Mid-Atlantic NWIS well density on candidates was sparse.
- Yang framing: RSR &lt; 0.5 ≈ excellent; ~1 ≈ good. Mid-Atlantic HUC2–02 is in the eastern US group with strong CONUS2 streamflow skill.

### What “validated well” means here
- Metrics are typically **RSR** on log streamflow and log WTD.
- CONUS2 improved streamflow and WTD vs CONUS1 across HUC basins; **~half of HUC subbasins** had excellent streamflow RSR.
- **Eastern US** generally shows strong stream network / shallow WTD structure.
- **WTD** is harder: **D1** (along 1:1, better) vs **D2** (river cells / unresolved microtopography at 1 km). Flat Coastal Plain + heterogeneity is more challenging.
- Mid-Atlantic coastline BC sensitivity in CONUS2 spinup was small for streamflow/WTD (HUC2–02 tests).

### Jul 2026 streamflow RSR for Mid-Atlantic high-CU candidates

Computed for the CU shortlist above (CONUS2 baseline WY2003 monthly mean at gages vs 1990–2019 observed mean Q). Lower RSR = better. `n_lt` = gages used in the long-term metric.

| Rank | HUC8 | Name | RSR (long-term) | n_lt | Geology (brief) |
|------|------|------|-----------------|------|-----------------|
| 1 | `02070008` | Middle Potomac–Catoctin | **0.22** | 27 | Blue Ridge / Piedmont, metro fringe |
| 2 | `02070010` | Anacostia–Occoquan | 0.51 | 19 | Fall Line / metro Potomac |
| ~3 | `02080111` | Pocomoke–W. Lower Delmarva | 0.52 | 5 | Delmarva Coastal Plain |
| ~3 | `02060006` | Patuxent | 0.52 | 15 | MD Coastal Plain |
| ~3 | `02070001` | South Branch (current) | 0.52 | 7 | Valley & Ridge headwaters |
| ~3 | `02080109` | Nanticoke | 0.52 | 4 | Delmarva Coastal Plain (high CU) |
| — | `02060003` | Gunpowder–Patapsco | 0.68 | 64 | Baltimore-area CP / mixed |
| — | `02080206` | Lower James | 0.99 | 6 | VA Coastal Plain |
| poor | `02080110` | Tangier | 1.30 | 3 | Delmarva / tidal |
| poor | `02060002` | Chester–Sassafras | 1.60 | 8 | MD Coastal Plain |
| avoid | `02080108` | Lynnhaven–Poquoson | ~5.0 | 4 | Hampton Roads CP |
| avoid | `02080208` | Hampton Roads | ~5.6 | 3 | Confined Potomac-aquifer stress, weak CONUS skill |

CSV snapshot from that run (if present): `drought-ensemble/.tmp_hydrodata/huc8_streamflow_rsr.csv`.

### `02070008` vs current `02070001` (context)

| | `02070001` (potomac2) | `02070008` |
|--|------------------------|------------|
| Role | True **headwater** HUC | Mid-basin Potomac **corridor** + local tributaries |
| Physiography | Valley & Ridge | Blue Ridge / Piedmont → metro fringe |
| Elev (CONUS2 bbox) | median ~566 m (to &gt;1300 m) | median ~128 m (to ~550 m) |
| CU depth | ~5×10⁻⁹ m/h | ~1.3×10⁻⁶ m/h (~200×) |
| Streamflow RSR | ~0.52 | **~0.22** |
| Modeling caveat | Clean closed headwaters | HUC mask does **not** bring upstream Potomac inflow; mainstem cells can be awkward |

Do **not** require new domains to be South Branch analogues. Geologic diversity is desirable for the ensemble.

### Preferred geologic-diversity shortlist (Jul 2026)

User preference: **validation + CU + geologic spread**, not Valley & Ridge similarity. Suggested triad:

| Slot | HUC8 | Geology | CU depth | RSR | Role |
|------|------|---------|----------|-----|------|
| Keep | `02070001` | Valley & Ridge | ~5×10⁻⁹ | ~0.52 | Existing headwater / drought work |
| Add | **`02070008`** | Blue Ridge / Piedmont | ~1.3×10⁻⁶ | **~0.22** | Best skill + high CU |
| Add | **`02080109`** or **`02060006`** | Atlantic Coastal Plain | ~3×10⁻⁶ / ~1×10⁻⁶ | ~0.52 | CP diversity; Nanticoke = higher CU, Patuxent = more gages |

Also strong if metro/Fall Line CU is the priority: **`02070010`** (highest CU, RSR ~0.51; more urban / mainstem complexity than `02070008`).

**Hampton Roads (`02080208` / `02080108`):** best real-world confined-aquifer drawdown narrative, but streamflow RSR is poor — defer unless the user accepts weak CONUS skill for that process story.

### Existing project domains (starting points)
| Domain | HUC8 | Reference gage | Notes |
|--------|------|----------------|-------|
| `potomac2` (+ flow barriers) | `02070001` | `01607500` | Valley & Ridge headwaters; active pumping/drought work |
| `wolf2` | `08010210` | `07030500` | Separate workstream |
| `republican` / `ponca` | `10250003` | (see config) | Plains; large disk / spinup constraints |

### Practical screening workflow for a new catchment
1. User names goal (e.g. Coastal Plain + higher CU, geologic diversity, metro pumping, or stay on current domain).
2. Shortlist from CU table + **Jul 2026 RSR table** above (and/or Yang et al. / O'Neill et al.). Prefer good streamflow RSR; treat flat tidal Coastal Plain and Hampton Roads as high-risk for skill.
3. Prefer geologic diversity across the ensemble (V&R / Piedmont / Coastal Plain) unless the user asks for analogues.
4. Confirm gage / drainage area consistency for subsetting; for corridor HUCs (`02070008`, `02070010`), flag mainstem / upstream-inflow issues.
5. **Ask the user what `pumping_rate_fraction` to use** (or a set of rates). Optionally show USGS CU depth as context — do not auto-select.
6. Create domain via existing `get_domain` / Domain workflow; do not invent rates in sequence JSON without user confirmation.

### Citations
- Yang et al. (2024), *J. Hydrol.* — ParFlow CONUS 2.0 evaluation (WTD + streamflow, HUC performance, D1/D2).
- O'Neill et al. (2021), *GMD* — ParFlow–CLM CONUS 1.0 water-balance assessment.
- USGS NWDC — PS/irrigation consumptive use & withdrawals by HUC12.
