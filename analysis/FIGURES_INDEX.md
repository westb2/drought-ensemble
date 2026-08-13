# Drought-ensemble figure index

**Directory:** `analysis/figures/`  
**Rule:** when you create, rename, replace, or retire a figure, **update this file in the same change**.  
**Deck:** `drought_narrative_slides.pptx` is built by `make_drought_narrative_slides.py` — keep slide membership in sync when adding narrative figures.

Display names on figures: `potomac2`→**Potomac**, `wolf2`→**Wolf**.

---

## Narrative slide deck

| File | What it is | Script |
|------|------------|--------|
| `drought_narrative_slides.pptx` | Results → overland covariates → Budyko → depth mechanism | `make_drought_narrative_slides.py` |
| `pumping_vs_drought_storage_slides.pptx` | Preliminary: pumping vs drought storage losses (depth + mid-stress regen) | `make_pumping_vs_drought_slides.py` |

---

## 1. Drought recovery (temp / persist, courses, maps)

**Primary script:** `redo_recovery_with_50yr.py` (some older maps/covariates may predate this file).

| File | What it shows | In deck? |
|------|---------------|----------|
| `drought_recovery_temp_persist_definition.png` | ΔS recovery: yr-1 = temporary, remainder = persistent | §1 |
| `ten_year_drought_streamflow_storage.png` | 10-yr drought course: Q + S | §1 |
| `fifty_year_drought_streamflow_storage.png` | 50-yr drought course | §1 |
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
**Tables:** `drought_recovery_deficit_covariate_spearman.csv`, `drought_recovery_temp_spike_correction.csv`, `figures/wtd_threshold_vs_overland_summary.json`.

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
| `shallow_deep_temp_persist_partition.png` | Temp ≈ near-surface; persist ≈ deep (bars) | §4 |
| `shallow_deep_layer_recovery_profile_10yr.png` | Recovery fraction by layer (10-yr) | §4 |
| `shallow_deep_spatial_10yr.png` | Spatial near-surface fraction vs f_temp | §4 |
| `shallow_deep_mid_drought_regen.png` | Mid-drought ΔS near-surface vs deep | §4 |
| `shallow_deep_mid_drought_regen_with_recovery.png` | Same series through 5-yr recovery window | §4 |
| `shallow_deep_mid_drought_year_pulse.png` | One drought year: storage tracks P only near surface | §4 |

---

## 5. Pumping analogue

**Scripts:** `redo_pumping_recovery_analogues.py`, `pumping_shallow_deep_proxies.py`, `pumping_streamflow_impact.py`  
**Summaries:** `pumping_recovery_analogue_summary.md`; `pumping_shallow_deep_proxies_summary.md`; `pumping_streamflow_impact_summary.md` → `figures/pumping_streamflow_impact.json`.  
**Slide deck:** `pumping_vs_drought_storage_slides.pptx` (§6 streamflow).

| File | What it shows |
|------|---------------|
| `pumping_during_totals_and_anomalies.png` | During-pumping totals/anomalies |
| `pumping_by_rate_fractional_storage.png` | Fractional storage by rate |
| `pumping_course_streamflow_storage.png` | Pumping course Q + S |
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
| Cumulative persist mass vs overland ranking | `drought_recovery_drainage_deficit_concentration.png` |
| log overland vs mean persist (+ vs stream distance) | `drought_recovery_drainage_threshold_bins.png` |
| Temp/persist covariate heatmap | `drought_recovery_deficit_covariate_spearman.png` |
| Budyko / φ / f_temp | §3 `budyko_*` |
| Near-surface shielding / mid-drought regen | §4 `shallow_deep_*` |
| Pumping shallow/deep / mid-year regen proxies | §5 `pumping_shallow_deep_*` |
| Pumping streamflow / Q ratios | §5 `pumping_streamflow_*` · `pumping_streamflow_impact_summary.md` |
| Slide deck (drought) | `drought_narrative_slides.pptx` |
| Slide deck (pumping vs drought) | `pumping_vs_drought_storage_slides.pptx` |

---

*Last updated: 2026-08-13 (pumping streamflow impact + slides §6).*
