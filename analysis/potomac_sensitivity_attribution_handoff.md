# Potomac sensitivity attribution — agent handoff

**Created:** 2026-09-22
**Status:** Analysis complete (plan Steps 0–7). Results and verdicts are in
[`potomac_sensitivity_attribution_summary.md`](potomac_sensitivity_attribution_summary.md). Read that first for *what* was found. This file covers *how to keep working*: the code map, the gotchas, and self-contained workstreams that separate agents can pick up in parallel.

Environment: `conda activate /glade/work/bwest/conda-envs/droughts`, cwd `/glade/derecho/scratch/bwest/drought-ensemble`. Project conventions are in `.cursor/skills/drought-ensemble/SKILL.md`; plotting rules are in `.cursor/skills/drought-ensemble/plotting.md`.

---

## One-paragraph state of knowledge

The apparent excess Potomac *pumping* streamflow sensitivity is an artifact. Older figures sample the near-dry config outlet (66, 135) and rebuild flow from sparse pressure snapshots. At the mainstem (63, 129), with window-mean flow, Potomac ≈ Wolf. The *drought* streamflow residual is about 2× Wolf's as a percentage of flow, but smaller in mm/yr. The real Potomac-only signal is slow **near-surface** (top 2 m) recovery. About 80% of what remains after recovery year 2 sits in about 5% of cells with these properties:
- a **perched** water table about 1.7 m deep, above a regional WTD of about 110 m;
- essentially no overland flow;
- root-zone ET that flips from energy-limited to water-limited during drought.

The regional WTD is the wrong variable for these cells; the "shallowest water table" is the right one. The mechanism is suppressed ET plus slow refill from local infiltration, not refill of the deep deficit (H3 rejected). Composition swaps explain none of the streamflow gap. The persistence gap is a behavior × composition interaction.

---

## Durable learnings since the original handoff (22 Sep evening)

These were confirmed while finishing workstream A (and later B/D). They are easy to re-break.

1. **Never trust `overland_flow.attrs["aggregation"]` alone.** Catalog `10_year_pumping_tests` years **43–49** (`pumping_1e-{7,6,5,4}` only; matched rates are fine) store end-of-window **snapshots** while tagged as window means. Detect by matching stored flow to pressure-rebuilt flow (`figures/_data/overland_flow_aggregation_audit.json`, rebuild with `.tmp_psa/detect_snapshots.py`). Rebuild means from sibling `derived_hourly.nc` (all 56 snap files have it).
2. **Outlet Q must go through `analysis/outlet_flow.py`.** Potomac → mainstem `(63, 129)`, not config `(66, 135)`. Draft fidelity must **block-average** flux series, never subsample (`q[::4]` aliases the repeating storm calendar). Series caches need outlet coords in the key (`_o{x}-{y}_wm1`).
3. **The Potomac recovery-year-1 "overshoot" (~+21–25%) was the config cell.** At the mainstem there is no overshoot (10-yr yr 1 ≈ −4.8%, 50-yr ≈ −5.9%). Any older note quoting that overshoot is wrong for basin Q.
4. **Matched pumping % gaps disappear at the mainstem.** Recovery yrs 1 / 2 / 5 ≈ −1.4 / −1.1 / −0.8% (Potomac) vs −1.3 / −1.0 / −0.7% (Wolf). The old comparison-set "esp. Potomac" (−7.4 / −6.2 / −4.6%) was config + stride-4 snapshots.
5. **Same absolute pumping rate is still a bigger % of Potomac Q** (e.g. catalog `1e-5` recovery ≈ −10.5% Potomac vs −3.7% Wolf). That is H0 normalization (smaller baseline Q), not higher sensitivity. Matched rates already remove most of it.
6. **Perched lens (workstream B):** sits on CONUS2 `FBz = 0.001` barrier faces (7 m or 2 m), not an indicator-K contrast. Memory depends on that barrier parameterization; `potomac_flow_barrier_*` is the natural follow-up.
7. **Paper panels (workstream D draft):** live in `figures/psa_final/` via `make_psa_paper_figures.py`. Map the remaining NS deficit in **mm**, not R₂ (R₂ lights up tiny deficits).

## Code map

| File | Role |
|---|---|
| `analysis/outlet_flow.py` | **Required for any outlet-Q plot.** `analysis_outlet`, `window_mean_outlet_flow`, `block_mean`, `FLOW_TAG`. Audit JSON: `figures/_data/overland_flow_aggregation_audit.json`. |
| `analysis/psa_extract.py` | Per-year slim extraction from raw 219 h + hourly CLM → `figures/_cache/psa/<domain>/<hash>.nc`. `--flowmean` writes `<hash>_qwm.nc` (window-mean `overland_flow` + local gain). `year_jobs()` defines **which years exist in the cache**. |
| `analysis/psa_extract.pbs` | Casper job (16 workers, resume-safe). Submit with `qsub -q casper@casper-pbs analysis/psa_extract.pbs`. |
| `analysis/potomac_sensitivity_attribution.py` | All analysis + figures. `main()` runs Steps 0–7 serially and writes `figures/_data/psa_summary.json`, `figures/_data/cell_traits_{domain}.nc`, and `figures/drought_exploratory/psa_*.png`. There is no per-step CLI: import the module and call `stepN_*` / `fig_*` directly when iterating. |
| `analysis/potomac_perched_lens.py` | Workstream B: barrier / lens structure, drought response, definition sensitivity → `_data/psa_lens.json`, `psa_lens_*.png`. |
| `analysis/make_psa_paper_figures.py` | Workstream D: paper panels → `figures/psa_final/psa_paper_*.png`. |
| `analysis/.tmp_psa/probe*.py` | Throwaway diagnostics. `probe11.py` is the snapshot-vs-window-mean outlet comparison (config vs mainstem, stride 1 vs 4); rerun it to reproduce the artifact numbers. `detect_snapshots.py` rebuilds the aggregation audit. |

Key functions in `potomac_sensitivity_attribution.py`:
- **Cache access.** `year_ds(domain, member, y)` returns one year's slim Dataset. `q`/`gain` are the window-mean versions; the snapshot versions are renamed `q_snap`/`gain_snap`. `base_key` / `member_key` map a year onto a cached baseline or member year (with remaps; see gotchas). `base_prev_end` gives a continuous baseline ΔS.
- **Traits.** `step1_traits()` builds everything in `cell_traits_*.nc`. `shallowest_wt_depth()` reads **raw** pressure from `ds.attrs["source_219h"]`, which is slow and not cached. `breakpoint_fit()` does the EF-vs-saturation fit, pooled over both domains (s_c = 0.66).
- **Classes.** `wtd_class` / `swt_class` are coded 0 (<1 m), 1 (1–5 m), 2 (>5 m). `et_class` is coded 0 (energy-limited), 1 (threshold), 2 (water-limited). `joint_class = 3*wtd_class + et_class`, and `swt_joint_class = 3*swt_class + et_class`. **The key Potomac class is `swt_joint_class == 4`** (shallowest WT 1–5 m · threshold; 177 cells).
- **Analysis steps.** `step2_attribution` (class shares of Δ local export), `step3_ns` / `ns_persistence` (R₁/R₂/R₅, regeneration), `step4_tests` (skill, H3 partial ρ), `step5_decomposition(class_key=...)`, `step6_budgets` / `class_budget` (`BUDGET_CLASSES` picks which classes), `step7_pumping`.

Case/period definitions are `CASES` and `periods()` at the top of the file. Baseline years are 35–39 (`BASE_YEARS`), and the growing season is windows 20–39 (`GS`).

---

## Gotchas (read before changing anything)

1. **Flow must be window means.** Recomputing outlet or cell flow from end-of-window pressure snapshots aliases badly at flashy cells, up to 10×, because the forcing calendar repeats. The psa caches store both; always use `q` / `gain` (window mean), not `q_snap`.
2. **Not every 219 h file stores a window mean, and the tag lies.** Catalog `10_year_pumping_tests` years 43–49 store end-of-window snapshots while tagged "mean". Use `analysis/outlet_flow.window_mean_outlet_flow` (and the audit JSON), not the attribute. The psa caches never read those years.
3. **Outlet choice** (now centralized in `analysis/outlet_flow.analysis_outlet`). `Domain(...).outlet_x/y` for potomac2 is (66, 135), a near-dry cell (0.07 mm/yr domain-equivalent). The mainstem is (63, 129): the max baseline-flow cell, which matches the USGS-validation snap. Wolf's config outlet (18, 21) is fine.
4. **`overland_bc_flux` is all zeros** in the 219 h files, so don't use it. Local export is rebuilt from window-mean outflow via `psa_extract.face_weights` / `gain_from_outflow`, which is exact under OverlandKinematic upwinding.
5. **Baseline remaps.** Potomac `baseline` has no condensed years ≥ 55, so late years map onto `short_baseline` 50–54, and ΔS must use `base_prev_end`. Wolf 50-yr late years map onto `baseline` 90–94. Adding new years means extending `year_jobs()` and re-running the extraction.
6. **The cache covers only specific years.** Coverage is `short_baseline` 35–54; `10_year_drought` 40–54; `50_year_drought` 40, 41, 85–94; the matched pumping member 40–59; and `baseline` 55–59, 90–94. Other drought lengths, catalog pumping rates, and other domains are **not** cached.
7. **ET classes lean on the drought response** (the threshold class is defined by crossing s_c during drought), and the pooled breakpoint R² is only 0.15. When circularity matters, use the baseline-only proxy `sat_rz_gs_base < 0.90` (step R² 0.66 for NS R₂).
8. **Shared outputs.** `psa_summary.json`, `cell_traits_*.nc` and the `psa_*.png` files are overwritten on every `main()` run. If two agents work in parallel, write to new filenames (or a suffix) rather than re-running `main()` concurrently.

---

## Workstreams (independent; pick one per agent)

Each workstream lists what it touches, so parallel agents don't collide. All of them should update `FIGURES_INDEX.md` (and `FIGURE_CATEGORIES.yaml` for finals) when figures change. Only one agent at a time should edit those two files.

### A. Correct the outlet / snapshot bias in existing deck figures

**Status: DONE (22 Sep 2026).**
- **New helper `analysis/outlet_flow.py`.** It provides:
  - `analysis_outlet`: the Potomac override to (63, 129);
  - `window_mean_outlet_flow`: true window means, falling back to `derived_hourly.nc` for snapshot files;
  - `block_mean`: draft downsampling by averaging.
- **Readers switched to the helper:** `make_10yr_pumping_story_figures.read_series` (the pressure-snapshot path is removed), `redo_recovery_with_50yr.read_condensed_series`, `pumping_recovery_timeseries.read_series` and `pumping_annualized_q.read_outlet`. Series caches are now tagged `_o{x}-{y}_wm1`.
- **File audit.** `figures/_data/overland_flow_aggregation_audit.json`, built by `.tmp_psa/detect_snapshots.py` using an exact match to pressure-rebuilt flow. Only catalog `10_year_pumping_tests/pumping_1e-{7,6,5,4}` years 43–49 are snapshots, in both domains. Every other drought, baseline, 3-yr and matched file is a true mean, and `derived_hourly.nc` exists for all 56 snapshot files.
- **Figures regenerated (draft fidelity):** the comparison set, `make_story_figures.py`, `make_pumping_final_figures.py`, and the flow figures from `redo_recovery_with_50yr` (both drought courses and totals/anomalies). **Decks were not rebuilt.**
- **Docs corrected:** `drought_story_deck_summary.md`, `comparison_story_set_summary.md` and `plotting.md`. Caveats were added to `persistent_storage_vs_streamflow_50yr.md` and `budyko_local_framing_handoff.md`, whose Potomac yr-1 "overshoot" was the config cell.
- **Left as-is:** `redo_pumping_recovery_analogues.py` is legacy 3-yr; it bakes the config-cell `outlet_flow` into its own slim caches. `wolf_pumping_recovery.py` is Wolf only and unaffected.
- **Still open:** the `final`-fidelity rebuild, plus rerunning other exploratory scripts that plot Potomac outlet Q (for example `pumping_annualized_q.py`, the `ten_year_pumping_*` suite via `run_10yr_pumping_analyses.py`, and `redo_recovery_with_50yr.main()` in full). They will pick up the fix when rerun.

**Original goal.** The deck figures should show basin streamflow, not the dry config cell or snapshot aliasing. The Potomac "larger pumping impact" claim in the comparison set is not supported.

**Affected figures and writers:**
- `comparison/compare_drought_pump_recovery_flow_anomaly.png` (`make_comparison_figures.py::fig_recovery_flow`)
- `pumping_final/ten_year_pumping_recovery_flow_anomaly.png` (`make_pumping_final_figures.py`)
- `drought_final/story_recovery_flow_anomaly_combined.png` (`make_story_figures.py`)
- All of these share `make_10yr_pumping_story_figures.read_series` (`OUTLETS` from config; `_outlet_q_from_pressure_snapshots`; stride 4 in draft fidelity).
- Also check `redo_recovery_with_50yr.py`, `pumping_recovery_timeseries.py`, `redo_pumping_recovery_analogues.py` and `pumping_annualized_q.py`. They build `OUTLETS` the same way.

**Approach:**
- Add a Potomac mainstem override at (63, 129).
- Use window-mean `overland_flow` wherever `aggregation` says mean, and keep the pressure rebuild only for snapshot-tagged files (gotcha 2).
- Alternatively, plot whole-domain surface export.
- Mind the series caches: `.tmp_figure_cache/10yr_pumping_story/series_*_qsnap2.npz` is keyed on stride and not on outlet, so bump the cache tag.

**Expected result.** Pumping recovery years 1 / 2 / 5 at the mainstem are about −1.4 / −1.1 / −0.8% for Potomac and −1.3 / −1.0 / −0.7% for Wolf (from `probe11.py`).

**Touches.** Deck scripts and their `.tmp_figure_cache`, plus `comparison_story_set_summary.md`, `pumping_story_set_summary.md` and `drought_story_deck_summary.md` text. Don't rebuild `.pptx` decks unless the user asks.

### B. Perched-lens mechanism: is it physical, and how robust is it?

**Status: done (2026-09-22).** Script `potomac_perched_lens.py` → `_data/psa_lens.json`, `psa_lens_{structure,drought,sensitivity}.png`; write-up [`potomac_perched_lens_summary.md`](potomac_perched_lens_summary.md). Findings:
- The lens sits on the CONUS2 `FBz = 0.001` flow barrier (ParFlow applies it to the cell's upper face; every cell has it on the 7 m or the 2 m face). It is not an indicator K contrast (only about 2× across the face). The lens is perched wherever the regional WT is below the barrier (53% of Potomac, 12% of Wolf).
- In drought the lens mostly thins (class-4 lens WT 1.7 → 3.4 m, below the 2 m root zone) rather than vanishing (30% lose it). Lens drawdown and the ET flip are one coupled process (ρ 0.79). Lens loss does not beat the ET flip as an R₂ predictor (step R² 0.12 vs 0.48), and head drop adds nothing given the ET class.
- Class-4 results survive every tested change of SWT edges, perched threshold and head criterion (remainder share 0.78–0.82).
- Wolf lenses thin as much as Potomac's but refill within a year (about 3× the net recharge).
- Open lead: this memory depends on the barrier parameterization. Check what the `potomac_flow_barrier_*` domains vary (same `pf_flowbarrier.pfb`, only 2 spinup years).

Original brief:

**Goal.** Nail down *why* Potomac uplands carry a saturated lens (layers around z5, 2–7 m depth) above an unsaturated interval, and whether the persistence result holds up under reasonable definitional choices.

**Starting points.** `step6_saturation_profiles` in the JSON, `shallowest_wt_depth()`, `cell_traits_potomac2.nc` (`perched`, `swt_mean`, `swt_drought_mean`, `perm_top`, `perm_mid`, `por_top`).

**Questions:**
- Is the lens a permeability contrast in the CONUS2 subsurface indicator? Map `perm_mid` / the indicator by layer under class-4 cells versus others.
- Does the lens survive the drought in some cells and vanish in others? Does its disappearance, rather than the ET flip, predict R₂?
- Sensitivity: the SWT class edges (1 / 5 m), the perched threshold (regional − shallowest > 5 m), and the pressure-head ≥ 0 criterion.
- Does Wolf have lenses that simply stay wet (59% of its 22 class-4 cells are perched)?

**Touches.** New functions or a new script (for example `potomac_perched_lens.py`), new `psa_lens_*.png` figures. Import from `potomac_sensitivity_attribution`; don't edit its `main()`.

### C. Attribution robustness checks

**Goal.** Make the class-share and decomposition numbers defensible for a paper.

**Checks:**
- Rerun `step5_decomposition` with baseline-only classes (`sat_rz_gs_base` split at 0.90 × SWT class) to remove ET-class circularity (gotcha 7).
- Per-domain breakpoints versus the pooled one (both are in `step1_breakpoints`).
- A bootstrap over cells for the class shares in Step 2 and Step 3.
- 50-yr versus 10-yr consistency: the class-4 streamflow share drops from 18% to 8% after 50 years. Why?
- Check the Potomac baseline remap years (gotcha 5) by comparing drift in `short_baseline` 50–54 against 35–39.

**Touches.** Can call module functions with modified trait arrays in memory. Write results to a separate JSON (for example `_data/psa_robustness.json`).

### D. Manuscript figures and narrative

**Goal.** Condense the psa story into 2–3 paper-quality panels, using the `paper-figures` skill (`~/.cursor/skills/paper-figures/SKILL.md`) plus the project `plotting.md`.

**Candidate story:**
- Normalization panel: mainstem versus config outlet, showing the artifact.
- Map of shallowest WT with class-4 cells outlined, beside the NS R₂ map.
- The class-4 column budget in recovery (ET suppression versus ΔS_ns refill) beside Wolf's deep refill.

The current `psa_*` figures are exploratory: they have titles and dense legends, and the budget panels run off-scale in drought years by design.

**Touches.** A new builder script (for example `make_psa_paper_figures.py`) and new figure names. Decide with the user whether they go to a `*_final` category.

**Status (2026-09-22): first draft done.** `make_psa_paper_figures.py` writes `psa_paper_{flow_normalization,perched_maps,recovery_budgets}.png` into the new `psa_final/` category (listed in `FIGURE_CATEGORIES.yaml` and `figure_paths.CATEGORIES`). Draft captions are in the summary under "Manuscript figures". Two departures from the candidate story:
- The map column shows the near-surface deficit left in **mm**, not the R₂ fraction. R₂ lights up cells with tiny deficits, so it hides the class-4 concentration.
- The Wolf comparison budget uses class 3 (WT 1–5 m · energy-limited). Wolf's class 4 has only 22 cells.

### E. (Optional) Extend to more cases or domains

Other drought lengths (1-, 3-yr), catalog pumping rates and `potomac_flow_barrier_*` would all need `psa_extract.year_jobs()` extended plus a Casper extraction run. The CLM reads take about 135 s per year-file for 8 variables, so run it as a batch job, not on a login node. `CASES` / `periods()` would also need new entries. This is the heaviest workstream; coordinate before running, because the extraction writes into the shared `_cache/psa/`.

---

## Key numbers to sanity-check against (from `psa_summary.json`)

- Baseline mainstem Q: Potomac 180 mm/yr, Wolf 574 mm/yr. Domain export: 191 / 699 mm/yr.
- 10-yr drought, recovery years 2–5, mainstem: Potomac −0.61%, Wolf −0.35%. Matched pumping, recovery years 2–5: −0.92% / −0.83%.
- Near-surface fraction remaining after recovery year 2: Potomac 0.15, Wolf 0.011.
- Potomac class 4: 4.7% of area; holds 34.5% of the end-of-drought NS deficit and 80.5% of the year-2 remainder.
- Pumping source over 10 years (storage / export / ET): Potomac 0.73 / 0.25 / 0.02, Wolf 0.63 / 0.33 / 0.04.
