# Drought-ensemble figure index

**Directory:** `analysis/figures/` with category subfolders:

| Folder | Meaning |
|--------|---------|
| `drought_final/` | Selected for the condensed drought story deck (`drought_story_slides.pptx`) |
| `pumping_final/` | Condensed pumping story (`make_pumping_final_figures.py`; catalog / `1e-6` only) |
| `comparison/` | Drought vs matched-pumping contrasts (`make_comparison_figures.py`) |
| `drought_exploratory/` | Drought analyses not in the condensed deck (incl. long narrative) |
| `pumping_exploratory/` | Pumping analyses not in the condensed set |
| `decks/` | `*.pptx` |
| `_data/` | `*.json` / `*.csv` sidecars |
| `_reports/` | `*.html` / `*.pdf` summary renders |
| `_cache/` | Slim 219h / zone caches |
| `_scratch/` | `_tmp_*` diagnostics |

**Membership:** `analysis/FIGURE_CATEGORIES.yaml` (finals). Unlisted PNGs are classified by `analysis/figure_paths.py`. Writers use `FIG_DIR / "name.png"` from `figure_paths` (or `fig_path`); readers/slides use `resolve_figure("name.png")`. Re-run `python analysis/migrate_figure_categories.py` after adding legacy flat files.

**Rule:** when you create, rename, replace, or retire a figure, **update this file and (if final) `FIGURE_CATEGORIES.yaml` in the same change**.  
**Decks:** do **not** rebuild `decks/*.pptx` unless the user explicitly asks — regenerate PNGs and link those for in-editor review.  
**Deck builders:** `decks/drought_narrative_slides.pptx` ← `make_drought_narrative_slides.py` (narrative members stay **exploratory**).

Display names on figures: `potomac2`→**Potomac**, `wolf2`→**Wolf**.

**Outlet flow (since 22 Sep 2026):** every outlet-Q series uses `analysis/outlet_flow.py`. It takes the Potomac **mainstem (63, 129)**, not the near-dry config cell (66, 135), and **true 219 h window means**: catalog 10-yr pumping years 43–49 are rebuilt from `derived_hourly.nc` because their stored values are snapshots. Draft fidelity **block-averages** flow. Figures built before that date with Potomac outlet Q are superseded; see `potomac_sensitivity_attribution_summary.md`.

---

## Narrative slide deck

| File | What it is | Script |
|------|------------|--------|
| `decks/drought_story_slides.pptx` | **Condensed 7-figure story** (+ title; drought + pumping parity) | `make_story_figures.py` → `make_drought_story_slides.py` |
| `decks/drought_narrative_slides.pptx` | Long version, 35 slides: results → overland covariates → Budyko → depth mechanism | `make_drought_narrative_slides.py` |
| `decks/pumping_vs_drought_storage_slides.pptx` | Preliminary: pumping vs drought storage losses (depth + mid-stress regen) | `make_pumping_vs_drought_slides.py` |

### Condensed story deck contents (`drought_final/`)

Slide order in `make_drought_story_slides.py`. Mixed / pumping-parity slides that live in this deck are filed under **drought_final** (deck ownership).  
Built by `make_story_figures.py` using loaders from
`redo_recovery_with_50yr.py`, `wtd_threshold_vs_overland.py`,
`pumping_recovery_timeseries.py`, and `shallow_deep_shielding.py`.

**Rationale, merge provenance, verification, and gotchas:**
[`drought_story_deck_summary.md`](drought_story_deck_summary.md).

| # | Figure | Provenance |
|---|--------|------------|
| 1 | `drought_final/ten_year_drought_streamflow_storage.png` | unchanged |
| 2 | `drought_final/story_recovery_storage_and_wtd_maps.png` | **merged:** old slide 3 ΔS row + old slide 4 ΔWTD maps |
| 3 | `drought_final/story_recovery_flow_anomaly_combined.png` | **merged:** drought + pumping yearly-mean outlet flow anomaly — **lines**, shared y, brown drought + purple pumping (deck palette) |
| 4 | `drought_final/story_overland_controls_persistence.png` | **merged:** drought concentration + log-overland bins (10-yr); **+ pumping 1e-5** dashed purple overlay (near-uniform rank); stream-distance / P(top 20%) dropped; zero-flow cells excluded → 54% / 42% drought shares |
| 5 | `drought_final/shallow_deep_temp_persist_partition.png` | **deck styling:** blue temp / purple persist stacked bars (deep bottom, near-surface top), T/P labels; supersedes `drought_recovery_temp_persistent_deficit_bars.png` |
| 6 | `drought_final/story_mid_drought_regen_10yr.png` | **trimmed:** `shallow_deep_mid_drought_regen_with_recovery.png` — 10-yr drought only (1- and 3-yr courses sat under the 10-yr line), carried through the 5-yr recovery window, widened to the slide aspect so the seasonal pulses stay legible over 15 years |
| 7 | `drought_final/story_pumping_recovery_storage_and_wtd_maps.png` | **pumping parity:** `pumping_temp_persist_definition`-style ΔS (focus rate 1e-5) over ΔWTD recovery maps at 1e-5 |

### Condensed pumping story set (`pumping_final/`)

Pumping-only set (iterate in-editor). Built by `make_pumping_final_figures.py`.
**All panels** use catalog **`1e-7` / `1e-6` / `1e-5`** — **never** domain-matched
rates. Courses include 5-yr recovery. Distinct basenames so drought_final’s
`story_pumping_*` stay put.

**Handoff:** [`pumping_story_set_summary.md`](pumping_story_set_summary.md).

| # | Figure | Notes |
|---|--------|-------|
| 1 | `pumping_final/ten_year_pumping_streamflow_storage.png` | Catalog rates Q/S through recovery |
| 2 | `pumping_final/ten_year_pumping_streamflow_storage_by_rate.png` | Same catalog ladder (rate-sensitivity twin) |
| 3 | `pumping_final/ten_year_pumping_recovery_storage_and_wtd_maps.png` | ΔS all rates; WTD maps @ `1e-6` |
| 4 | `pumping_final/ten_year_pumping_recovery_flow_anomaly.png` | Catalog rates yearly-mean outlet anomaly |
| 5 | `pumping_final/story_mid_pump_regen_10yr.png` | Catalog rates near-surface / deep ΔS |

Reproduce: `python analysis/make_pumping_final_figures.py` (optional `FIGURE_FIDELITY=final`).

### Comparison set (`comparison/`)

Drought vs **domain-matched** pumping only (Potomac `8.64e-7`, Wolf `2.49e-6`).
Built by `make_comparison_figures.py`. Flow/bars: domain-brown drought vs purple
matched. Overland: domain colors `#009E73`/`#56B4E9`, solid drought / dashed
matched; no cumulative markers; circles on bins.

**Handoff:** [`comparison_story_set_summary.md`](comparison_story_set_summary.md).

| # | Figure | Notes |
|---|--------|-------|
| 1 | `comparison/compare_drought_pump_recovery_flow_anomaly.png` | Yearly-mean outlet % anomaly |
| 2 | `comparison/compare_drought_pump_overland_controls.png` | Persist vs overland (+ lowest-fifth shares) |
| 3 | `comparison/compare_drought_pump_temp_persist_bars.png` | Temp/persist totals (same magnitude, different rebound) |

Reproduce: `python analysis/make_comparison_figures.py`.

---

## 1. Drought recovery (temp / persist, courses, maps)

**Primary script:** `redo_recovery_with_50yr.py` (some older maps/covariates may predate this file).  
Paths below are basenames; on disk they live under `drought_final/` or `drought_exploratory/` per the table at top.

| File | What it shows | In deck? |
|------|---------------|----------|
| `drought_recovery_temp_persist_definition.png` | ΔS recovery: yr-1 = temporary, remainder = persistent | §1 |
| `ten_year_drought_streamflow_storage.png` | 10-yr drought course: Q + S | §1 |
| `fifty_year_drought_streamflow_storage.png` | 50-yr drought course | §1 |
| `fifty_year_streamflow_baseflow_partition.png` | 10 vs 50-yr recovery Q ratios + residual −ΔQ by flow tercile | no |
| `baseflow_streamflow_partition_50yr.json` | Machine-readable ratios + partition for above | no |
| `potomac_ns_storage_vs_streamflow_recovery.png` | Potomac 10/50-yr recovery: NS ΔS, deep ΔS, Q/baseline | no |
| `potomac_ns_vs_q_recovery_contrast.png` | Potomac: NS ΔS vs Q/baseline by recovery year (10 vs 50) | no |
| `potomac_ns_storage_vs_streamflow_recovery.json` | Yearly NS/deep/Q + correlations for above | no |
| `three_year_drought_streamflow_4panel.png` | 3-yr course (4-panel) | no |
| `drought_recovery_totals_and_anomalies.png` | Recovery: S, ΔS, Q, ΔQ by length | §1 |
| `drought_recovery_by_length_fractional_storage.png` | Fraction of storage deficit remaining | §1 |
| `drought_recovery_by_length_anomaly.png` | Recovery anomalies by length | no |
| `drought_recovery_temp_persistent_deficit_bars.png` | Domain-total temp vs persist by length | §1 |
| `drought_recovery_temp_persistent_deficit_bars_corrected.png` | Spike-corrected bars | no |
| `drought_recovery_temp_persistent_deficit_bars_spike.png` | Spike bars | no |
| `drought_recovery_temp_spike_decomposition.png` | Temp spike decomposition | no |
| `drought_recovery_temp_persistent_storage_deficit_maps.png` | Temp/persist storage maps (both domains) | archive |
| `drought_recovery_temp_persistent_storage_deficit_maps_potomac2.png` | Same, Potomac only (slide-sized) | §1 |
| `drought_recovery_temp_persistent_storage_deficit_maps_wolf2.png` | Same, Wolf only | §1 |
| `drought_recovery_temp_persistent_wtd_deficit_maps.png` | Temp/persist WTD maps (both) | no |
| `drought_recovery_temp_persistent_wtd_deficit_maps_potomac2.png` | Temp/persist WTD, Potomac | no |
| `drought_recovery_temp_persistent_wtd_deficit_maps_wolf2.png` | Temp/persist WTD, Wolf | no |
| `drought_recovery_wtd_anomaly_maps.png` | ΔWTD start / 1 yr / 5 yr (both) | archive |
| `drought_recovery_wtd_anomaly_maps_potomac2.png` | ΔWTD recovery, Potomac | §1 |
| `drought_recovery_wtd_anomaly_maps_wolf2.png` | ΔWTD recovery, Wolf | §1 |
| `potomac2_drought_recovery_wtd_anomaly_maps.png` | Legacy Potomac WTD maps | legacy |
| `wolf2_drought_recovery_wtd_anomaly_maps.png` | Legacy Wolf WTD maps | legacy |

**Summaries:** `drought_recovery_50yr_summary.md` → `figures/drought_recovery_50yr_summary.{pdf,html}`; `drought_recovery_50yr_totals.json`.

---

## 2. Overland / drainage covariates (predictor of deficit type)

These are the **overland-flow analysis** figures (not the Budyko-named set). Prefer this group when the user asks for overland as a predictor of temp/persist.

| File | What it shows | In deck? |
|------|---------------|----------|
| `drought_recovery_deficit_covariate_spearman.png` | Temp/persist S & WTD vs landscape/K/recharge covariates (Spearman heatmap) | §2 |
| `drought_recovery_drainage_deficit_concentration.png` | Cells ranked low→high overland vs cumulative persistent mass | §2 |
| `drought_recovery_drainage_threshold_bins.png` | Mean persist (& P top-20%) vs log₁₀ overland **and** vs dist. to stream | §2 |
| `drought_recovery_drainage_threshold_enrichment.png` | Enrichment of top-20% persist below log-flow thresholds | §2 |
| `drought_recovery_drainage_position_heuristics.png` | Spearman ρ: drainage heuristics (incl. log overland, dist stream) vs temp/persist | §2 |
| `drought_recovery_best_factors_maps.png` | Best single factors mapped beside deficits (10-yr) | §2 |
| `drought_recovery_best_factors_hexbin.png` | Hexbins for those factor–deficit pairs | §2 |
| `drought_recovery_recharge_vs_persistent_maps.png` | Local recharge vs persistent S / ΔWTD maps | no |
| `drought_recovery_recharge_vs_persistent_hexbin.png` | Recharge vs persistent hexbins | no |
| `drought_recovery_wtd_persistence_vs_covariates.png` | End-of-recovery ΔWTD vs dist/HAND/slope | no |
| `drought_recovery_multivar_r2.png` | Multivariate model R² | no |
| `drought_recovery_multivar_delta_r2.png` | ΔR² | no |
| `drought_recovery_multivar_coefficients.png` | Coefficients | no |
| `drought_recovery_multivar_pred_obs.png` | Pred vs obs | no |
| `wtd_threshold_vs_overland_skill.png` | Spearman vs step vs quantile-bin skill: WTD / overland / dist / combos | no |
| `wtd_threshold_vs_overland_binned_means.png` | Mean persist & f_temp vs WTD / log-overland / dist (equal-count bins) | no |
| `wtd_threshold_vs_overland_2d_bins.png` | Mean persist in WTD × log-overland quantile bins | no |

**Script (WTD threshold test):** `wtd_threshold_vs_overland.py` → `wtd_threshold_vs_overland_summary.md`  
**Tables:** `drought_recovery_deficit_covariate_spearman.csv`, `drought_recovery_temp_spike_correction.csv`, `figures/_data/wtd_threshold_vs_overland_summary.json`.

---

## 3. Local Budyko framing

**Script:** `budyko_temp_persistent.py`  
**Summary:** `budyko_temp_persistent_summary.md` → `figures/budyko_temp_persistent_summary.{pdf,html,json}`.

| File | What it shows | In deck? |
|------|---------------|----------|
| `budyko_phi_vs_overland_hist.png` | φ nearly flat (esp. Wolf); overland participation varies | §3 |
| `budyko_maps_phi_overland_ftemp.png` | Maps: φ, overland participation, f_temp | §3 |
| `budyko_hexbin_ftemp_vs_predictors.png` | f_temp vs φ, participation, WTD, stream distance | §3 |
| `budyko_space_ftemp.png` | (φ, Q_ol/P) colored by f_temp | §3 |
| `budyko_ftemp_by_stratum.png` | Mean f_temp by stream/near/mid/upland × length | §3 |
| `budyko_stratified_temp_persist_bars.png` | Temp/persist volume by stratum × length | §3 |
| `budyko_spearman_ftemp.png` | Within-domain Spearman heatmap | §3 |

**Table:** `budyko_temp_persistent_spearman.csv`.

---

## 4. Near-surface vs deep (shielding mechanism)

**Script:** `shallow_deep_shielding.py`  
**Summary:** `shallow_deep_shielding_summary.md` (curated — do not overwrite from script) → `figures/shallow_deep_shielding_summary.{pdf,html,json}`.

Near-surface = CONUS2 layers **z≥6** (top **2 m**); deep = **z&lt;6**.

| File | What it shows | In deck? |
|------|---------------|----------|
| `shallow_deep_temp_persist_partition.png` | Temp (blue) vs persist (purple); deep bottom / near-surface top; T/P labels on deck | §4 + story deck slide 6 |
| `shallow_deep_layer_recovery_profile_10yr.png` | Recovery fraction by layer (10-yr) | §4 |
| `shallow_deep_spatial_10yr.png` | Spatial near-surface fraction vs f_temp | §4 |
| `shallow_deep_mid_drought_regen.png` | Mid-drought ΔS near-surface vs deep | §4 |
| `shallow_deep_mid_drought_regen_with_recovery.png` | Same series through 5-yr recovery window | §4 |
| `story_mid_drought_regen_10yr.png` | Same, 10-yr only + recovery, slide-width (built by `make_story_figures.py`) | story 6 |
| `shallow_deep_mid_drought_year_pulse.png` | One drought year: storage tracks P only near surface | §4 |

### 4b. Potomac sensitivity attribution (why Potomac Q / near-surface look more sensitive)

**Script:** `potomac_sensitivity_attribution.py` (slim caches from `psa_extract.py` / `psa_extract.pbs` → `figures/_cache/psa/`)  
**Summary:** [`potomac_sensitivity_attribution_summary.md`](potomac_sensitivity_attribution_summary.md) · **handoff:** [`potomac_sensitivity_attribution_handoff.md`](potomac_sensitivity_attribution_handoff.md) · numbers `_data/psa_summary.json` · per-cell traits `_data/cell_traits_{potomac2,wolf2}.nc`.

Flow uses **219 h window-mean** `overland_flow` at the **mainstem** outlet (Potomac (63, 129)), not the near-dry config cell (66, 135) or pressure snapshots. The comparison-deck Potomac pumping excess is a sampling artifact (see the summary). Classes: shallowest water table incl. perched (<1 / 1–5 / >5 m) × ET regime (energy-limited / threshold / water-limited, pooled s_c = 0.66).

| File | What it shows | In deck? |
|------|---------------|----------|
| `psa_flow_normalization.png` | Yearly % flow anomaly at config outlet vs mainstem vs domain export (10-yr drought, matched pumping); the other normalizations (mm/yr, % P, fraction of deficit/pumped) are in the summary table | no |
| `psa_trait_distributions.png` | Regional vs shallowest WTD histograms, EF vs root-zone saturation breakpoint, class area fractions | no |
| `psa_export_attribution.png` | Maps of Δ local export (rec yrs 2–5) + class shares of loss vs area / baseline export | no |
| `psa_ns_persistence_maps.png` | Maps: log shallowest WT, end-of-drought NS deficit, NS fraction left after recovery yr 2 (both domains) | no |
| `psa_hypothesis_bins.png` | Equal-count bins of export loss (drought + pumping) and NS R₂ vs regional WTD, shallowest WT, root-zone saturation, log overland (H1/H2) | no |
| `psa_composition_vs_behavior.png` | Class-fraction swap counterfactuals (drought / pumping ΔQ %, NS R₂) | no |
| `psa_class_column_budgets.png` | Column budget anomalies (P, ET, recharge, ΔS NS/deep, export, residual NS drainage), last drought yr → recovery yr 5; domain + main classes | no |
| `psa_pumping_capture.png` | Annual source of pumped water: storage depletion / reduced export / reduced ET / residual, through pumping + recovery | no |

**Perched-lens follow-up (workstream B):** `potomac_perched_lens.py` · [`potomac_perched_lens_summary.md`](potomac_perched_lens_summary.md) · numbers `_data/psa_lens.json`. The lens sits on the CONUS2 `FBz = 0.001` flow barrier (7 m or 2 m face), not an indicator K contrast.

| File | What it shows | In deck? |
|------|---------------|----------|
| `psa_lens_structure.png` | Maps of flow-barrier depth, baseline perched-lens frequency (class-4 outlined), flux through the barrier; median pressure-head profiles by group | no |
| `psa_lens_drought.png` | Head drop on barrier and NS deficit through 10-yr drought + recovery (class 4, lens lost, lens kept); lens-lost × ET-flip shares and R₂ | no |
| `psa_lens_sensitivity.png` | Class-4 share of the year-2 NS remainder vs SWT class edges, perched threshold, pressure-head criterion | no |

**Manuscript figures → `figures/psa_final/`** (`make_psa_paper_figures.py`; reads the caches + `psa_summary.json`; paper style, no titles, panel letters). Draft captions are in the summary under "Manuscript figures".

| File | What it shows | In deck? |
|------|---------------|----------|
| `psa_paper_flow_normalization.png` | Domains as columns: (a,b) mainstem recovery % anomaly (10-/50-yr drought + pumping matched to 10-yr); (c,d) recovery-yr-2–5 residual (% + mm annotation); (e,f) temp/persist storage totals. Shared stress colors (sequential browns + purple) | no |
| `psa_paper_flow_per_deficit.png` | Same residual bar layout as flow-normalization (c,d): recovery-yr-2–5 cumulative mainstem ΔQ ÷ recovery-start storage deficit; Potomac / Wolf | no |
| `psa_paper_flow_high_low.png` | Recovery mainstem % anomaly (10-yr drought + matched pumping): all windows (a,b), high baseline-flow tercile (c,d), low tercile (e,f); Potomac / Wolf columns; y = −15…5 | no |
| `psa_paper_flow_high_low_abs.png` | Same layout as `psa_paper_flow_high_low` but absolute ΔQ (domain-mm/yr equivalent of mean outlet m³/h difference); y auto per domain column | no |
| `psa_paper_perched_maps.png` | Regional WT, shallowest WT (incl. perched) with perched-threshold cells (`swt_joint_class == 4`) outlined, and NS deficit (mm) left after recovery yr 2 (10-yr drought); Potomac / Wolf rows | no |
| `psa_paper_recovery_budgets.png` | (a) Potomac perched-threshold vs (b) Wolf intermediate-WT (class 3) annual budget anomalies, recovery yrs 1–5 (shared y); (c) whole-domain mean anomalies, recovery yrs 2–5 (NS refill vs deep refill) | no |
| `psa_paper_volume_normalized.png` | Long-term drought residual and matched pumping: streamflow loss as % of baseline Q (top) vs as a fraction of water lost (bottom: storage deficit / volume pumped). Pumping matches; drought residual is closer but not identical. Rec yr 1 noted in (c). | no |
| `psa_paper_pumping_loss_frac.png` | Cumulative streamflow loss (reduced export) and subsurface loss (storage depletion) as a fraction of total pumped volume through pumping + recovery; Potomac / Wolf | no |
| `psa_paper_drought_loss_frac.png` | Same layout for the 10-yr drought: cumulative streamflow and subsurface losses as a fraction of the total precipitation deficit vs baseline; Potomac / Wolf | no |
| `psa_paper_drought_sf_per_storage.png` | 10-yr drought: cumulative streamflow loss divided by end-of-drought storage loss (Potomac / Wolf; shared y) | no |
| `psa_paper_recovery_mass_balance.png` | Recovery only: streamflow, ET, and recharge anomalies / storage deficit at recovery start (recharge ≈ −ET); rows = 10-yr drought & matched pumping, columns = Potomac / Wolf; shared y | no |
| `psa_paper_pumping_rates_recovery_flux.png` | Pumping recovery only: streamflow / ET / recharge anomalies ÷ start-of-recovery storage deficit for catalog rates 1e-7…1e-4 (hue = flux, saturation = rate); Potomac / Wolf | no |
| `psa_paper_storage_recovered.png` | % of end-of-stress storage deficit recovered vs years into recovery; row 1 = drought lengths 1/3/10/50 (sequential browns), row 2 = all `10_year_pumping_tests` rates (sequential purples); domains as columns | no |

---

## 5. Pumping analogue

**Scripts:** `redo_pumping_recovery_analogues.py`, `pumping_recovery_timeseries.py`, `pumping_shallow_deep_proxies.py`, `pumping_streamflow_impact.py`, `pumping_annualized_q.py`, `pumping_vs_drought_deficits.py`, `pumping_overland_persist.py`, `wolf_pumping_recovery.py`, `wolf_pumping_depth.py`, **`make_10yr_pumping_story_figures.py`**, **`backfill_10yr_pumping_219h.py`**, **`run_10yr_pumping_analyses.py`** (`PUMPING_STRESS_YEARS=10`)  
**Summaries:** `pumping_recovery_analogue_summary.md`; `pumping_recovery_timeseries_summary.md`; `pumping_shallow_deep_proxies_summary.md`; `pumping_streamflow_impact_summary.md`; `pumping_annualized_q_summary.md`; `pumping_vs_drought_deficits_summary.md`; `pumping_overland_persist_summary.md`; `wolf_pumping_recovery_summary.md`; `wolf_pumping_depth_summary.md`; **`matched_deficit_pumping_runs_summary.md`** (intermediate rates 2e-6…6e-6 vs 10-yr drought — handoff in `.cursor/skills/drought-ensemble/matched-deficit-pumping-runs.md`); **`ten_year_pumping_*_summary.md`** (same suite retargeted to `10_year_pumping_tests`, 5-yr recovery vs `short_baseline`, drought=`10_year_drought`).  
**Slide deck:** `pumping_vs_drought_storage_slides.pptx` (§6 streamflow; §7 deficit-type contrast).

| File | What it shows |
|------|---------------|
| `ten_year_pumping_streamflow_storage.png` | **10-yr pumping story course** (focus 1e-5): Q + S through last 3 spinup yr → 10-yr pump (drought slide-2 twin; purple deck palette) |
| `ten_year_pumping_streamflow_storage_1e-6.png` | Same single-rate course at `1e-6` |
| `ten_year_pumping_streamflow_storage_by_rate.png` | Same course, all four classic rates `1e-7…1e-4` |
| `story_mid_pump_regen_10yr.png` | **10-yr pumping story:** near-surface vs deep ΔS at 1e-5 (drought slide-7 twin; stress only) |
| `ten_year_pumping_course_streamflow_storage.png` | 10-yr pump + 5-yr recovery Q+S course (all rates) |
| `ten_year_pumping_recovery_totals_and_anomalies.png` | Recovery: S, ΔS, Q, ΔQ by rate (5 yr after 10-yr pump) |
| `ten_year_pumping_recovery_fractional_storage.png` | Fraction of end-pump storage deficit remaining |
| `ten_year_pumping_temp_persist_definition.png` | ΔS recovery schematic (focus 1e-5) |
| `ten_year_pumping_during_totals_and_anomalies.png` | During 10-yr pumping totals/anomalies |
| `ten_year_pumping_by_rate_fractional_storage.png` | Fractional storage by rate (during 10-yr pump) |
| `ten_year_pumping_wtd_anomaly_maps.png` | End-of-10-yr-pump ΔWTD maps × rate |
| `ten_year_pumping_early_buildup_storage_deficit_maps.png` | Early vs end-of-10-yr buildup storage deficit maps |
| `ten_year_pumping_early_buildup_deficit_bars.png` | Early vs end-of-10-yr buildup deficit bars |
| `ten_year_pumping_shallow_deep_mid_pump_regen.png` | Mid-pump (yr 5) near-surface vs deep ΔS by rate |
| `ten_year_pumping_shallow_deep_mid_pump_year_pulse.png` | Mid pump year: NS tracks P; deep ratchets |
| `ten_year_pumping_shallow_deep_end_deficit_partition.png` | End yr1 / end yr10 deficit: near-surface vs deep |
| `ten_year_pumping_fast_regen_vs_deep_drawdown.png` | Mid-year NS rebound vs deep net loss / yr |
| `ten_year_pumping_shallow_deep_spatial_end_yr3.png` | End-of-stress shallow/deep/f_shallow maps (1e-5; filename legacy) |
| `ten_year_pumping_streamflow_q_ratio.png` | Outlet Q/baseline + ΔQ during 10-yr pumping by rate |
| `ten_year_pumping_streamflow_q_ratio_bars.png` | Mean/p50/p90 Q ratios across pump years |
| `ten_year_pumping_streamflow_q_ratio_by_year.png` | Mean Q ratio across pump years 1→10 |
| `ten_year_pumping_streamflow_dq_vs_ds.png` | ΔQ vs ΔS trajectories during 10-yr pumping |
| `ten_year_pumping_annualized_q_course.png` | Yearly outlet Q + Q/baseline through 10-yr pump + 5-yr recovery |
| `ten_year_pumping_annualized_q_ratio_recovery.png` | Annualized Q/baseline; origin at recovery start |
| `ten_year_pumping_annualized_q_milestones.png` | Annualized Q/baseline at pump yr1/yr10 and rec yr1/yr5 |
| `ten_year_pumping_vs_drought_temp_persist_bars.png` | 10-yr drought vs 10-yr pumping: temp/persist volume + f_temp |
| `ten_year_pumping_vs_drought_fractional_recovery.png` | Fraction of end-stress deficit remaining (10-yr drought vs rates) |
| `ten_year_pumping_vs_drought_ds_recovery.png` | ΔS through recovery: 10-yr drought vs pumping 1e-5 |
| `ten_year_pumping_vs_drought_depth_partition.png` | Temp/persist × near-surface/deep, 10-yr drought vs 1e-5 |
| `ten_year_pumping_drainage_deficit_concentration.png` | Persist mass vs cells ranked low→high overland (10-yr drought overlay) |
| `ten_year_pumping_drainage_threshold_bins.png` | Pumping 1e-5: mean persist & P(top 20%) vs log overland / stream dist. |
| `ten_year_pumping_vs_drought_mean_persist_overland.png` | Mean persist / domain-mean vs log overland; 10-yr drought vs 1e-5 |
| `wolf_pumping_course_streamflow_storage.png` | Wolf: Q + S through pump + 10-yr recovery (4 rates) |
| `wolf_pumping_during_totals_and_anomalies.png` | Wolf: during-pumping totals/anomalies by rate |
| `wolf_pumping_recovery_totals_and_anomalies.png` | Wolf: recovery-window S, ΔS, Q, ΔQ by rate |
| `wolf_pumping_recovery_fractional_storage.png` | Wolf: fraction of initial deficit through 10-yr recovery |
| `wolf_pumping_wtd_anomaly_maps.png` | Wolf: ΔWTD recovery start / +1 / +5 yr × rate |
| `wolf_pumping_temp_persist_definition.png` | Wolf: temp/persist schematic on ΔS (focus 1e-5) |
| `wolf_pumping_temp_persistent_storage_deficit_maps.png` | Wolf: temp vs persist storage maps × rate |
| `wolf_pumping_temp_persistent_deficit_bars.png` | Wolf: domain-total temp/persist by rate |
| `wolf_pumping_depth_layer_profile.png` | Wolf: end-stress deficit by layer + yr-1 recovery fraction (L2 pump vs 3-yr drought) |
| `wolf_pumping_depth_shallow_deep_partition.png` | Wolf: NS/deep × temp/persist bars, drought vs L2 pumping |
| `wolf_pumping_depth_zone_course.png` | Wolf: near-surface vs deep ΔS through stress + recovery |
| `pumping_during_totals_and_anomalies.png` | During-pumping totals/anomalies |
| `pumping_by_rate_fractional_storage.png` | Fractional storage by rate (during pumping) |
| `pumping_course_streamflow_storage.png` | Pumping course Q + S through pump + 10-yr recovery |
| `pumping_recovery_totals_and_anomalies.png` | Recovery: S, ΔS, Q, ΔQ by rate (10 yr) |
| `pumping_recovery_fractional_storage.png` | Fraction of end-pump storage deficit remaining |
| `pumping_temp_persist_definition.png` | ΔS recovery schematic: yr-1 = temporary (focus 1e-5) |
| `pumping_wtd_anomaly_maps.png` | Pumping ΔWTD maps |
| `pumping_early_buildup_storage_deficit_maps.png` | Early-buildup storage deficit maps |
| `pumping_early_buildup_deficit_bars.png` | Early-buildup deficit bars |
| `pumping_shallow_deep_mid_pump_regen.png` | Mid-pump near-surface vs deep ΔS by rate |
| `pumping_shallow_deep_mid_pump_year_pulse.png` | One pump year: NS tracks P; deep ratchets |
| `pumping_shallow_deep_end_deficit_partition.png` | End yr1/yr3 deficit: near-surface vs deep |
| `pumping_fast_regen_vs_deep_drawdown.png` | Mid-year NS rebound vs deep net loss / yr |
| `pumping_shallow_deep_spatial_end_yr3.png` | End-yr3 shallow/deep/f_shallow maps (1e-5) |
| `pumping_streamflow_q_ratio.png` | Outlet Q/baseline + ΔQ during pumping by rate |
| `pumping_streamflow_q_ratio_bars.png` | Mean/p50/p90 Q ratios, pump yr1 vs yr3 |
| `pumping_streamflow_q_ratio_by_year.png` | Mean Q ratio across pump years 1→3 |
| `pumping_streamflow_dq_vs_ds.png` | ΔQ vs ΔS trajectories during pumping |
| `pumping_annualized_q_course.png` | Yearly outlet Q (10⁶ m³/yr) + Q/baseline through pump + 10-yr recovery |
| `pumping_annualized_q_ratio_recovery.png` | Annualized Q/baseline; origin at recovery start |
| `pumping_annualized_q_milestones.png` | Annualized Q/baseline at pump yr1/yr3 and rec yr1/yr5/yr10 |
| `pumping_vs_drought_temp_persist_bars.png` | 3-yr drought vs pumping: temp/persist volume + f_temp |
| `pumping_vs_drought_fractional_recovery.png` | Fraction of end-stress deficit remaining (drought vs rates) |
| `pumping_vs_drought_ds_recovery.png` | ΔS through recovery: 3-yr drought vs pumping 1e-5 |
| `pumping_vs_drought_depth_partition.png` | Temp/persist × near-surface/deep, drought vs 1e-5 |
| `pumping_drainage_deficit_concentration.png` | Persist mass vs cells ranked low→high overland (drought overlay) |
| `pumping_drainage_threshold_bins.png` | Pumping 1e-5: mean persist & P(top 20%) vs log overland and vs dist. stream |
| `pumping_vs_drought_mean_persist_overland.png` | Mean persist / domain-mean vs log overland; drought vs 1e-5 |
| `matched_deficit_10yr_rate_curve.png` | End-of-stress deficit vs pumping rate (10-yr stress) with 10-yr drought target and matched rate |
| `flow_barrier_pumping_*.png` | Flow-barrier pumping sensitivity set |

---

## 6. USGS streamflow validation

**Summary:** `usgs_streamflow_validation_summary.md` → `figures/usgs_streamflow_validation_summary.{pdf,html}`.

| File | What it shows |
|------|---------------|
| `average_year_usgs_hydrographs.png` | Average-year model vs USGS hydrographs |
| `average_year_usgs_scatter.png` | Scatter |
| `average_year_usgs_gage_cells.png` | Gage cell map |
| `average_year_usgs_ss_vs_end_spinup.png` | SS vs end-spinup |
| `drought_year_usgs_start_vs_end_hydrographs.png` | Drought-year start vs end hydrographs |
| `drought_year_usgs_start_vs_end_scatter.png` | Scatter |

---

## 7. Legacy / domain-specific / scratch

| Pattern | Notes |
|---------|--------|
| `potomac2_droughts_*.png`, `wolf2_droughts_*.png`, `*_short_droughts_*.png` | Older absolute/anomaly drought plots |
| `wolf2_50_year_drought_*.png` | Early 50-yr Wolf exploratories |
| `_tmp_*.png` | Scratch diagnostics — do not put in decks |

---

## Quick lookup (user phrasing → file)

| User asks for… | Start here |
|----------------|------------|
| Overland as predictor of persist / temp | §2 drainage_* + deficit_covariate_spearman |
| Cumulative persist mass vs overland ranking | `drought_recovery_drainage_deficit_concentration.png` (drought); `pumping_drainage_deficit_concentration.png` (pumping) |
| log overland vs mean persist (+ vs stream distance) | `drought_recovery_drainage_threshold_bins.png` (drought); `pumping_drainage_threshold_bins.png` (pumping) |
| Temp/persist covariate heatmap | `drought_recovery_deficit_covariate_spearman.png` |
| Budyko / φ / f_temp | §3 `budyko_*` |
| Near-surface shielding / mid-drought regen | §4 `shallow_deep_*` |
| Why Potomac Q / near-surface are more sensitive; perched WT; ET threshold cells; composition vs behavior | §4b `psa_*` · `potomac_sensitivity_attribution_summary.md` |
| Pumping shallow/deep / mid-year regen proxies | §5 `pumping_shallow_deep_*` |
| Pumping streamflow / Q ratios | §5 `pumping_streamflow_*` · `pumping_streamflow_impact_summary.md` |
| Pumping Q+S / recovery timeseries | §5 `pumping_course_*` · `pumping_recovery_*` · `pumping_recovery_timeseries_summary.md` |
| Annualized Q through pump + recovery | §5 `pumping_annualized_q_*` · `pumping_annualized_q_summary.md` |
| Pumping vs drought temp/persist | §5 `pumping_vs_drought_*` · `pumping_vs_drought_deficits_summary.md` |
| Pumping rate matching 10-yr drought deficit | `comparison/matched_deficit_10yr_rate_curve.png` · `matched_deficit_10yr_summary.md` |
| Pumping persist vs overland | §5 `pumping_drainage_*` · `pumping_overland_persist_summary.md` · `pumping_final/` + `comparison/` overland figures |
| 10-yr pumping condensed story set | `pumping_final/` · `make_pumping_final_figures.py` (catalog / 1e-6) |
| Drought vs matched pumping | `comparison/` · `make_comparison_figures.py` |
| 10-yr pumping full analysis suite (same as 3-yr, retargeted) | §5 `ten_year_pumping_*` · `ten_year_pumping_*_summary.md` · `run_10yr_pumping_analyses.py` |
| Slide deck (drought, short — 7 figures + title) | `drought_story_slides.pptx` · `story_*.png` |
| Slide deck (drought, full — 35 slides) | `drought_narrative_slides.pptx` |
| Slide deck (pumping vs drought) | `pumping_vs_drought_storage_slides.pptx` |

---

*Last updated: 2026-09-22 (§4b Potomac sensitivity attribution `psa_*` + perched-lens `psa_lens_*`; comparison overland encoding + handoffs refreshed).*
