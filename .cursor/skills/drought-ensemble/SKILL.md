---
name: drought-ensemble
description: >-
  Operate the drought-ensemble ParFlow project on Derecho: pumping rate formula,
  catchment/USGS/CONUS validation reference (user chooses pumping rates),
  run sequence layout, job submission, per-domain spinup inventory, runtime
  estimates from PBS logs, scratch-quota checks, flow-barrier domain scope,
  hourly vs 219h processed outputs, consolidation backfill, and analysis
  loaders/plotting (storage snapshot vs flow mean/sum). Use when submitting
  ensemble jobs, creating run sequences, estimating 12h walltime capacity,
  checking spinup reuse / hash collisions, debugging pumping, comparing
  user-specified rates to USGS water use, screening HUCs for new domains
  (Casper job `screen_huc_budyko_selection.pbs`; status/results under
  `analysis/huc_selection_job_status.md` and `huc_selection_screen_summary.json`),
  consolidating timesteps, reading processed NetCDF, plotting storage/WTD/
  streamflow, paper figures (domain display names, shared axes, units, drought
  shading, legend placement, slide heatmap layouts), figure catalog
  (`analysis/FIGURES_INDEX.md` — update when adding figures), condensed drought
  story deck (`drought_story_deck_summary.md`), condensed pumping story set
  (`pumping_story_set_summary.md` / `make_pumping_final_figures.py`; catalog
  1e-7/1e-6/1e-5), and drought-vs-matched comparison set
  (`comparison_story_set_summary.md` / `make_comparison_figures.py`; matched
  rates 8.64e-7 Potomac / 2.49e-6 Wolf; overland color=domain dash=stress), USGS NWIS
  streamflow validation for potomac2/wolf2
  (gage choice, cell snap, spinup/drought antecedent effects), interpreting
  matched-deficit intermediate pumping runs (2e-6…6e-6 vs 10-yr drought totals;
  see matched-deficit-pumping-runs.md), or working with
  potomac2 / potomac_flow_barrier_* / wolf2 / republican / ponca domains.
---

# drought-ensemble

Project root: `/glade/derecho/scratch/bwest/drought-ensemble`

## Active domains

| Domain | In running ensemble |
|--------|---------------------|
| `potomac2` | yes |
| `potomac_flow_barrier_0011` | yes |
| `potomac_flow_barrier_0015` | yes |
| `potomac_flow_barrier_002` | yes |
| `potomac_flow_barrier_005` | yes |
| `potomac_without_flow_barrier` | **no** (legacy metadata only) |
| `wolf2`, `republican`, `ponca` | drought/spinup workstreams |
| `wolf` | **removed** (Aug 2026); use `wolf2` |

## Paper figures (plotting)

Full conventions: **[plotting.md](plotting.md)**. Apply whenever making or revising analysis/paper plots.

**Figure catalog:** [`analysis/FIGURES_INDEX.md`](../../../analysis/FIGURES_INDEX.md) — **update it whenever you add, rename, replace, or delete a figure.**

**Must follow:**

| Rule | Detail |
|------|--------|
| Display names | `potomac2`→**Potomac**, `wolf2`→**Wolf** (code IDs unchanged) |
| Grid | Columns = domains; rows = metrics; `sharex="col"` |
| Labels | Y-labels + units **left column only**; one `fig.supxlabel`; no duplicate domain labels |
| Paper title | **No** `fig.suptitle` — legend `loc="outside upper center"` |
| Fonts | Labels/legend ~11–13 (line plots); map grids for Word ~13–16 |
| Storage scale | Plot as 10⁹ / 10⁶ m³; `useOffset=False` to avoid colliding `1e11` text |
| Drought shade | Three-period fill on courses: orange spinup / C3 drought / blue recovery, flush to axes; `despine_axes` (no top/right spines) |
| Anomaly rows | `sharey` across domains so **zero aligns** |
| Year axis | Integer ticks (`MultipleLocator`); label origin clearly (drought start vs recovery onset) |
| WTD / deficit maps | Shared colorbar; Stream `#F0E442`; slide maps = per-domain PNG + aspect-filled cells — see [plotting.md](plotting.md) |
| Index | Update **FIGURES_INDEX.md** when figures change |

Drought-length colors: `{1: "#E8C39E", 3: "#B86B2B", 10: "#4A2410", 50: "#140A05"}` (sequential browns). One visual channel per factor — see [plotting.md](plotting.md) and the `paper-figures` skill. Figures → `analysis/figures/`.

**Condensed talk deck** (`figures/decks/drought_story_slides.pptx`, 7 figures + title): authoritative handoff
[`analysis/drought_story_deck_summary.md`](../../../analysis/drought_story_deck_summary.md);
PNGs via `make_story_figures.py` (and related). Deck pumping uses
**purple** `STORY_PUMP_COLORS` in `make_story_figures.py` (not canonical brown pumping colors).
Default figure rebuilds are **draft** (`FIGURE_FIDELITY`); ask for **final** before shipping.
**Do not rebuild any `*.pptx` unless the user explicitly asks** — regenerate PNGs only so
figures stay easy to open in the editor; run `make_drought_story_slides.py` /
`make_drought_narrative_slides.py` / other slide builders only on request.
When discussing story slides, always list all 8 with PNG links (see that handoff).

**Condensed pumping story set** (`figures/pumping_final/`, catalog
`1e-7`/`1e-6`/`1e-5` only):
[`analysis/pumping_story_set_summary.md`](../../../analysis/pumping_story_set_summary.md);
builder `make_pumping_final_figures.py`. **Comparison set** (`figures/comparison/`,
3 PNGs; matched vs 10-yr drought):
[`analysis/comparison_story_set_summary.md`](../../../analysis/comparison_story_set_summary.md);
builder `make_comparison_figures.py`. When discussing either set, list all PNGs
with links. Do not mix matched into `pumping_final` or catalog rates into
`comparison`. Do not move `story_pumping_*` out of `drought_final`.

Overland-as-predictor ≠ Budyko: use `drought_recovery_drainage_*` / covariate figures first ([FIGURES_INDEX.md](../../../analysis/FIGURES_INDEX.md) §2); `budyko_*` is the φ / f_temp framing (§3).

## Pumping (critical)

In `classes/Run.py` and `add_pumping.py`:

```python
actual_pumping_rate = pumping_rate_fraction / pumped_area_fraction
fluxes[pumping_layer, :, :] = (-1.0 / dz[pumping_layer]) * actual_pumping_rate  # on pumped cells
```

- **`pumping_rate_fraction`** = desired **domain-average** extraction (m/h).
- **Divide** by cropland fraction `f`, do **not** multiply.
- ParFlow EvapTrans expects T⁻¹ = (depth flux) / `dz` — the `/dz` factor is correct.
- Old runs with the multiply bug need re-run; sequence values tuned for the old formula must be recalculated.
- **Hash does not include computed flux** — after fixing the formula, delete the pumping-year `raw_runs` hashes (keep shared spinup) or the job will skip and keep bad rates.
- **`pumping_layer` must be copied onto every sub-year sequence** in `run_full_sequence` / `get_output_folders` / IC lookup. If omitted, sub-runs default to layer 2, collide with L2 hashes, and skip (or overwrite) instead of writing `_pumping_layer_4` years.

**Recalibrating sequence values:** target flux in `fluxes_on.pfb` = `(pumping_rate_fraction / f) / dz`.

Example (Potomac flow barrier, f≈0.133, dz=50): old `0.01` with wrong formula gave ~`2.66e-5` in pfb; corrected sequence for same pfb ≈ `1.771e-4`.

**Rates are user-chosen.** Do not set or change `pumping_rate_fraction` without explicit user direction. For USGS CU comparisons, geology/drawdown context, Mid-Atlantic HUC8 shortlists, Jul 2026 CONUS2 streamflow RSR rankings, and the geologic-diversity triad (`02070001` / `02070008` / `02080109` or `02060006`): [pumping-rate-context.md](pumping-rate-context.md).

## Run sequences

Sequences live in `run_sequences/<ensemble_name>/*.json`. Each year:

```json
{"wetness": "average|dry|wet", "pumping_rate_fraction": 0.0, "irrigation": "False"}
```

Year folders hash from the **full prefix** of wetness/rate/irrigation strings (`Run.hash_sequence`). Same hash string across domains, but outputs are per-domain under `domains/<domain>/raw_runs/<hash>/`.

| Ensemble folder | Structure |
|-----------------|-----------|
| `3_year_pumping_tests` | **40** yr average spinup + **3** yr pumping + **10** yr recovery; rates `1e-7…1e-4` plus intermediate **`2e-6, 3e-6, 5e-6, 6e-6`** (matched-deficit campaign, Aug 2026 — see **[matched-deficit-pumping-runs.md](matched-deficit-pumping-runs.md)**) |
| `5_year_pumping_tests` | **5** yr spinup + **3** yr pumping |
| `40_year_spinup` | 40 yr average, no pump |
| `25_year_spinup` | **20** yr average (folder name is misleading) |
| `droughts` | **40** yr average spinup + drought/recovery (+ baseline is 95× average) |

Submit all JSONs in a folder:

```bash
cd ensemble_running
python run_ensemble.py <ensemble_name> <domain> [<domain> ...]
# --walltime 12:00:00  --dry-run
```

Default PBS: 4 nodes × 64 MPI ranks, 12 h walltime, queue `main`, project `UPRI0032`. Prefer one-off `tmp_job.pbs` when only a subset of sequences should run.

## Processed outputs (hourly + 219 h)

- Hourly: prefer ``raw_runs/<hash>/derived_hourly.nc`` (thin sidecar) merged with
  ``run.out.00001.nc`` via ``ensemble_running/hourly_year.open_hourly_year``.
  Legacy ``processed_output.nc`` (full hourly) is still readable.
- Consolidated default: **`processed_output_219h.nc`** (40 steps/year; year-divisible). Written automatically by `RunOutputReader` and by `ensemble_running/consolidate_to_interval.py` for backfills.
- Indexes: `file_locations.json` and `file_locations_219h.json` under `processed_full_runs/<ensemble>/<member>/`.

**Analysis default:** prefer `utils.read_simulation_data(..., interval=219)`.

| Plot quantity | Use |
|---------------|-----|
| Storage / WTD / pressure | Snapshot fields (`total_storage`, `wtd`, …) |
| Streamflow / flux **rate** | Window **mean** via `analysis/outlet_flow.py` |
| Streamflow / flux **volume** | `*_sum` (= mean × 219) |

**Outlet Q (required):** `analysis/outlet_flow.py` — Potomac mainstem `(63, 129)`
not config `(66, 135)`; true window means (catalog 10-yr pumping years 43–49
are snapshots despite a "mean" tag — rebuilt from `derived_hourly.nc`); draft
**block-averages**, never `q[::stride]`. Details: [plotting.md](plotting.md),
[`analysis/potomac_sensitivity_attribution_handoff.md`](../../../analysis/potomac_sensitivity_attribution_handoff.md).

Do not use calendar weeks (168 h) for on-disk products — they do not divide 8760. Full rules, backfill commands, and loader notes: [processed-outputs.md](processed-outputs.md).

## Parallel job safety

- **Safe:** same sequence on **different domains** (separate `raw_runs/` trees).
- **Unsafe:** two jobs on the **same domain** that would write the same year hash concurrently (e.g. `droughts/baseline` and another all-average prefix on the same domain).
- Existing year folders are **skipped** with no completeness check — delete tip incompletes before restart (see `restart-ensemble-jobs` + `incomplete-year-cleanup` rule).
- Before deletes: `qstat` — never remove hashes an **`R`** job is writing; list paths and confirm with the user.

## Scratch space

Run `gladequota` before large submits. Count **unique new hashes** per domain. If free ≪ need, free space or hold large domains before `qsub`.

**New years (no storage duplicate):** ParFlow raw + thin `derived_hourly.nc` only — do **not** write full `processed_output.nc`.

| Domain | New year (raw + sidecar) | Legacy year (raw + full hourly) |
|--------|-------------------------:|--------------------------------:|
| wolf2 | **~11 GB** | ~20 GB |
| potomac2 | **~34 GB** (raw+CLM ~31 GB + ~2–3 GB sidecar) | ~56–60 GB |
| republican / ponca | **~56 GB** (raw+CLM ~54 GB + thin sidecar) | ~100–103 GB |

Legacy full `processed_output.nc` ≈ half of old per-year disk (duplicates pressure/saturation already in `run.out.*`). Consolidation to 219 h is cheap (~MB/year). Leave ≥~0.5–1 TiB headroom when submitting multi-domain packages; reclaim via `migrate_to_sidecar.py` if needed (see [processed-outputs.md](processed-outputs.md)).

## Runtime estimates (4 nodes × 64 ranks, 12 h)

Use **same-job** timing, not global file timestamps across months.

**Method:** match PBS `Running year N …/raw_runs/<hash>` to `run.out.00001.nc` mtime; consecutive year-end gaps ≈ wall time per year.

| Domain | ~h/year | ~years/12 h (restart jobs) |
|--------|---------|----------------------------|
| potomac2 | 1.0–1.1 | **10–13** |
| flow_barrier_* | 1.0–1.2 | **8–10** |
| wolf2 | 0.7–0.9 | **12–14** |

Add ~0.75 h once if year 0 starts from scratch (domain setup). Pumping at 1e-7–1e-6 adds ~10–15% on potomac2; flow barrier at 0.01 showed no slowdown in sim time.

Quick check before submit:

```bash
python .cursor/skills/drought-ensemble/scripts/years_to_run.py \
  run_sequences/5_year_pumping_tests/pumping_1e-6.json potomac2 potomac_flow_barrier_0011
```

## Spinup inventory (transient average)

**Transient average met** (what sequences use), consecutive from y0:

| Domain | Available y0+ |
|--------|---------------|
| potomac2, wolf2 | **40+** (current droughts / `3_year_pumping_tests`) |
| republican | **40+** shared with completed `10_year_drought` prefixes |
| ponca | **20** (`25_year_spinup`); not enough for 40-yr droughts without more spinup |
| flow_barrier 0011, 002, 005 | **2 years** (shared hashes with potomac2 y0–y1) |
| flow_barrier 0015 | **0** (needs wet/average forcing setup; HF pin for `get_domain`) |

`domains/*/spinup/run/` = **static PME** equilibrium (press.pfb), not transient average forcing. Do not count as ensemble spinup years.

## Key paths

```
classes/Run.py                         # sequence hashing, run_full_sequence, pumping
classes/RunOutputReader.py             # derived_hourly sidecar + auto 219h
ensemble_running/hourly_year.py        # open/merge/atomic sidecar helpers
ensemble_running/consolidate_to_interval.py
ensemble_running/run_ensemble.py
ensemble_running/run_sequence_on_domain.py
ensemble_running/*.o*                  # PBS stdout (job outcomes)
analysis/paper_figures/utils.py        # read_simulation_data(..., interval=219)
domains/<d>/raw_runs/<hash>/derived_hourly.nc
domains/<d>/raw_runs/<hash>/processed_output.nc   # legacy
domains/<d>/raw_runs/<hash>/processed_output_219h.nc
domains/<d>/processed_full_runs/<ensemble>/<member>/file_locations.json
domains/<d>/processed_full_runs/<ensemble>/<member>/file_locations_219h.json
```

## Related skills / rules

- **Restart after failure:** `.cursor/skills/restart-ensemble-jobs/SKILL.md`
- **Auto restart watchdog (cron → Casper):** `ensemble_running/watchdog/README.md`
- **Delete partial years:** `.cursor/rules/incomplete-year-cleanup.mdc`
- **Deep reference:** [reference.md](reference.md)
- **Processed outputs / analysis:** [processed-outputs.md](processed-outputs.md)
- **Paper figure / plotting conventions:** [plotting.md](plotting.md)
- **Condensed drought story deck (8 slides):** [`analysis/drought_story_deck_summary.md`](../../../analysis/drought_story_deck_summary.md)
- **Catchment / USGS / CONUS context (rates stay user-controlled):** [pumping-rate-context.md](pumping-rate-context.md)
- **USGS streamflow validation (gages, cell snap, spinup/drought IC lessons):** [usgs-streamflow-validation.md](usgs-streamflow-validation.md)
  - User summary: `analysis/usgs_streamflow_validation_summary.md`
  - Notebook: `analysis/average_year_usgs_validation.ipynb`
- **Persistent storage vs streamflow at 50 yr (no clean baseflow collapse):**  
  `analysis/persistent_storage_vs_streamflow_50yr.md`
- **Local Budyko / temp–persist framing → new catchment selection:**  
  `analysis/budyko_local_framing_handoff.md` (handoff for planning agents);  
  `analysis/budyko_drought_literature.md`; `analysis/budyko_temp_persistent_summary.md`
- **HUC Track A/B screen (Casper, disk-safe):** see [HUC selection screen](#huc-selection-screen-casper) below; plan `analysis/budyko_huc_selection_plan.md`

## HUC selection screen (Casper)

Broader eastern + selected Interior HUC8 RSR + WTD/φ screen for Budyko Track A (intermediate WTD) / Track B (arid ribbons). **No `get_domain`.** Run on **Casper**, not Derecho login or `main`.

| Item | Path |
|------|------|
| Script | `analysis/screen_huc_budyko_selection.py` |
| PBS | `analysis/screen_huc_budyko_selection.pbs` (1 CPU, 16 GB, 8 h, account `UPRI0032`) |
| Submit | `qsub -q casper@casper-pbs analysis/screen_huc_budyko_selection.pbs` |
| Job status | `analysis/huc_selection_job_status.md` (**read this first** when user asks for results) |
| Cache / resume | `analysis/.tmp_huc_screen/` (`sites_*`, `obs_lt_*`, `sim_da*`, `wtd_phi_*`) |
| Live log | `analysis/.tmp_huc_screen/screen.log` (symlink to stamped log) |
| PBS oe | `analysis/.tmp_huc_screen/pbs_huc_screen.out` |

**Results deliverables:**

| File | Contents |
|------|----------|
| `analysis/huc_selection_screen_summary.json` | Ranked Top A / Top B |
| `analysis/huc_selection_annotated_tracks.csv` | Labels + φ + WTD metrics |
| `analysis/huc8_headwater_streamflow_rsr.csv` | RSR (incremental during run) |
| `analysis/huc8_headwater_streamflow_sites.csv` | Per-gage sim/obs |
| `analysis/budyko_huc_selection_recommendation.md` | Human gate writeup (update after screen if picks change) |

Do **not** run the screen overnight on Derecho/Casper login nodes. Kill any login copy before `qsub`. Caches make restart safe. Scratch was ~89% when screening started — keep outputs to tiny CSVs/JSON only.

## Do not

- Choose or change `pumping_rate_fraction` without explicit user direction (compare to USGS/CONUS context only when asked)
- Submit `potomac_without_flow_barrier` unless user explicitly asks
- Use `3_year_pumping_tests` on flow-barrier domains expecting 40 yr spinup reuse (only 2 yr exist there)
- Trust `processed_output.nc` mtimes for within-job pacing (batch postprocess skews them)
- Assume folder existence means year finished
- Delete `raw_runs` hashes while an **`R`** job on that domain is writing them
- Submit without checking `gladequota` when adding multi-TiB work (e.g. full republican droughts)
- Use 168 h (calendar week) for on-disk consolidation — it does not divide the year
- Sum storage over time or treat strided `isel` as window mean/sum when volumes matter
- Overwrite ParFlow raw or publish derived products without atomic temp→replace
- Reference domain `wolf` (removed; use `wolf2`)
- Put `potomac2` / `wolf2` as visible labels on paper figures (use Potomac / Wolf)
- Duplicate y/x labels under every domain panel, or leave axes without units
- Rely on matplotlib offset text (`1e11`) next to storage titles — scale the data instead
