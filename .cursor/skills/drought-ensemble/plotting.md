# Paper figure conventions (drought-ensemble)

Canonical analysis notebook: `analysis/drought_recovery_comparison.ipynb`  
Figure output dir: `analysis/figures/` with category subfolders (`drought_final/`,
`pumping_final/`, `comparison/`, `psa_final/`, `drought_exploratory/`, `pumping_exploratory/`,
plus `decks/`, `_data/`, `_reports/`, `_cache/`, `_scratch/`).  
**Membership:** `analysis/FIGURE_CATEGORIES.yaml` + `analysis/figure_paths.py`
(`FIG_DIR / "name.png"` to write, `resolve_figure("name.png")` to read).  
`pumping_final/` = catalog-rate pumping story (`make_pumping_final_figures.py`);
`comparison/` = drought vs matched (`make_comparison_figures.py`). See
`analysis/pumping_story_set_summary.md` and
`analysis/comparison_story_set_summary.md`. Prefer **219 h**
condensed products (`interval=219`, `file_locations_219h.json`).

## Domain display names

Keep filesystem / code IDs unchanged. On **all paper figures** (titles, panel titles, legends, axis text), use:

| Domain id   | Plot label |
|-------------|------------|
| `potomac2`  | **Potomac** |
| `wolf2`     | **Wolf**   |

```python
DOMAIN_LABELS = {"potomac2": "Potomac", "wolf2": "Wolf"}
ax.set_title(DOMAIN_LABELS[domain_name])
```

Do not print raw `potomac2` / `wolf2` on figures.

## Layout (multi-domain, multi-metric)

Default grid for comparing domains:

- **Columns** = domains (Potomac | Wolf)
- **Rows** = metrics (stacked)
- `sharex="col"` so recovery/drought time is shared down each column
- `constrained_layout=True` with modest pads, e.g.  
  `fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.04, hspace=0.08, wspace=0.04)`

**Do not duplicate labels across domains:**

- Y-axis labels (with units) **only on the left column**
- One shared x-label via `fig.supxlabel(...)` (not per bottom panel)
- Domain names as **column titles** on the top row only

When anomaly panels should be compared visually, **share y on that row** so zero lines align:

```python
axes[row, 1].sharey(axes[row, 0])
# ensure 0 is inside limits
lo, hi = axes[row, 0].get_ylim()
axes[row, 0].set_ylim(min(lo, 0.0), max(hi, 0.0))
```

Absolute storage/flow panels usually keep **independent** y-scales (domains differ by orders of magnitude).

## Titles and legends (paper figures)

- **No figure-level title** (`fig.suptitle`) for paper plots — the caption lives in the manuscript.
- Put the legend in the freed space:  
  `fig.legend(..., loc="outside upper center", ncol=…, frameon=False)`
- Font sizes: bump **labels and legend**; leave **tick numbers** near default unless asked.
  - Time-series / multi-panel line plots: ~11–13 for labels/legend.
  - **Map grids destined for Word/docs:** go larger (~13–16 for titles/labels, ~12 for colorbar ticks) so text stays readable when the figure is pasted small.

Typical constants used in the recovery / drought-course figures:

```python
LABEL_FS, LEGEND_FS, TITLE_FS = 12, 11, 13
```

## Units and scaling

Always put units on axis labels.

| Quantity            | Preferred axis label              | Notes |
|---------------------|-----------------------------------|--------|
| Total storage       | `Total storage (10⁹ m³)`          | divide series by `1e9` |
| Storage anomaly     | `Δ storage (10⁶ m³)`              | divide by `1e6` |
| Outlet flow         | `Outlet flow (m³/h)`              | 219 h mean overland flow |
| Flow anomaly        | `Δ outlet flow (m³/h)`            | |

Scale large storage values in the plotted arrays so matplotlib does **not** draw a `1e11`-style offset that collides with titles. Also:

```python
ax.ticklabel_format(axis="y", style="plain", useOffset=False)
```

## Colors and drought annotations

Drought-length colors (longest = darkest / driest) — a **sequential** brown
scale for an ordered factor. Use this family for 1 / 3 / 10 / 50 yr; do **not**
swap the longest length to an unrelated categorical color (e.g. pure black or
purple) when comparing drought lengths:

```python
COLORS = {1: "#E8C39E", 3: "#B86B2B", 10: "#4A2410", 50: "#140A05"}
```

**Encoding (see also `paper-figures` skill):** vary **one** channel per factor.
Same marker (and linestyle) across drought lengths; distinguish lengths with
the brown sequence above. Use a categorical hue (e.g. purple
`STORY_PUMP_COLORS` / `#7B3294`) only when the series is a different *type*
(matched pumping vs drought), not as a step on the drought-length scale.

- Baseline on absolute panels: grey (`"0.65"` / `"0.75"`)
- Drought window shading on **course** plots is the three-period fill
  (`shade_sequence_periods`): Okabe–Ito orange spinup `#E69F00`, C3 pink
  drought, sky blue recovery `#9ECAE1`. Do **not** use olive/khaki for spinup
  (unsafe next to red under deuteranopia).
- Fills must run **flush to the axis frame** (no white x-margin).
- Mark drought start/end with vertical lines (`ls="--"`, `ls=":"`)
- Include a legend patch for each shaded period
- Hide **top and right** spines (`despine_axes`); leave colorbars boxed

On streamflow “course” plots it is OK to **omit baseline on flow** while keeping baseline on storage, when the user wants that emphasis.

## Time axes

Pick one clear origin and label it:

| Context | Label | Origin |
|---------|-------|--------|
| Recovery comparison | `Years into recovery` | end of drought / recovery onset |
| Drought course (+ recovery) | `Year (from drought start)` | drought onset (`SPINUP_YEARS`) |

Use **integer year ticks**:

```python
from matplotlib.ticker import MultipleLocator
ax.xaxis.set_major_locator(MultipleLocator(2))  # or 1 if short window
ax.xaxis.set_minor_locator(MultipleLocator(1))
```

## WTD anomaly maps (recovery)

Canonical figure: `analysis/figures/drought_recovery_wtd_anomaly_maps.png`  
Built in `analysis/drought_recovery_comparison.ipynb` (WTD section).

### What to plot

$\Delta$WTD = drought member − `short_baseline` (m). **Positive = deeper / drier.**  
Use **219 h** condensed `wtd` snapshots (not hourly).

Preferred column set (both domains in one figure):

| Column label | Snapshot |
|--------------|----------|
| Recovery start (end of drought) | last condensed step of final drought year |
| 1 year recovery | last condensed step of first recovery year |
| 5 year recovery | last condensed step of 5th recovery year |

Year indices (sequence origin year 0):

```python
start_year = SPINUP_YEARS + drought_length - 1
yr1_year   = SPINUP_YEARS + drought_length          # end of year 1 of recovery
end_year   = SPINUP_YEARS + drought_length + RECOVERY_YEARS - 1
```

`STEPS_PER_YEAR = ONE_YEAR // 219` (= 40). Mid-year (~6 mo) would be `t_idx = STEPS_PER_YEAR // 2` in the first recovery-year file — tried once; user preferred **1 year** over 6 months.

Do **not** add a “recovery amount” (start − end) column unless explicitly requested (tried and reverted).

### Layout

- **Paper / combined:** one Potomac + Wolf figure is fine for docs.
- **16:9 slides:** prefer **per-domain PNGs** (`*_potomac2.png` / `*_wolf2.png`) so maps fill the slide — see “Spatial map grids for 16:9 slides” below.
- Rows = drought length; heatmap slide lengths use **1 / 3 / 10** (`MAP_LENGTHS`; omit 50 unless asked). Within each domain: start | 1 yr | 5 yr (WTD anomaly) or temporary | persistent (deficit maps).
- Domain headers (**Potomac** / **Wolf**) centered above each domain’s maps.
- Tall domains (Potomac): rotate to landscape via `_prepare_map` / `_best_align_angle`, then crop to valid cells.
- Size axes boxes to map aspect; avoid `set_aspect("equal")` letterboxing on slide layouts.
- **One shared** norm + colorbar (`RdBu_r` for ΔWTD; `YlOrBr` for deficits). Do not split colorbars unless asked.
- No `fig.suptitle` (caption in text).

### Stream overlay

- Mask: top **3%** of late-spinup baseline mean overland flow (active cells).
- Color: Okabe–Ito yellow `#F0E442` with dark edge (`edgecolors="0.15"`).
- Legend label: **`Stream`**. Paper map grids: Stream key **above the colorbar**. Slide map grids: Stream at **figure bottom**, colorbar on the right.

### Session notes / preferences

- Most spatial ΔWTD recovery is already visible by **~1 year**; 5-year panels are mainly residual.
- Potomac anomalies are subtler than Wolf on a shared scale — expected; do not split colorbars unless asked.
- Map-grid fonts for Word: domain titles ~16, column/row labels ~13–14, Stream ~15, colorbar label ~14 / ticks ~12.


## Temporary vs persistent storage-deficit maps

Canonical: `drought_recovery_temp_persistent_storage_deficit_maps.png` (+ per-domain `_*_potomac2.png` / `_*_wolf2.png` for slides).  
Built in `redo_recovery_with_50yr.py` (also historically in `drought_recovery_comparison.ipynb`).

### Definitions

Column-integrated `subsurface_storage` − baseline, as **m water equivalent** (`/ 1 km²` cell area).

- `deficit = S_baseline − S_drought` (positive = drier)
- **Temporary** = `max(deficit_start − deficit_1yr, 0)` — recovered in first recovery year
- **Persistent** = `max(deficit_1yr, 0)` — remaining after one year

### Layout

- Rows = drought length (1 / 3 / 10 for slides); columns = temporary | persistent
- Sequential colormap `YlOrBr`, shared `Normalize(0, vmax)` with vmax ≈ 98th percentile
- Same stream / colorbar conventions as WTD maps
- No `fig.suptitle`


## Temporary vs persistent WTD-deficit maps

Canonical: `drought_recovery_temp_persistent_wtd_deficit_maps.png` (+ per-domain variants).

Same timing as storage-deficit maps, for $\Delta$WTD (positive = deeper / drier):

- **Temporary** = `max(ΔWTD_start − ΔWTD_1yr, 0)`
- **Persistent** = `max(ΔWTD_1yr, 0)`

Shared `YlOrBr` scale. Stream overlay same as other map grids.

## Spatial map grids for 16:9 slides (learned Aug 2026)

- Prefer **one domain per slide PNG**; stacked both-domain figures go portrait and shrink on landscape slides.
- Axes box aspect = map `nx/ny`. After setting `xlim`/`ylim`, use **`ax.set_aspect("auto")`** so the cell fills (do not use `equal` + adjustable box — that letterboxes and wastes row height).
- Row labels in a **left gutter** via `fig.text` — never `set_ylabel` on map axes (overlaps pixels).
- Fixed figure canvas for inch-based layouts; avoid `bbox_inches="tight"` (crops gutters / reintroduces collisions).
- Overland-as-predictor figures are **`drought_recovery_drainage_*` + `deficit_covariate_spearman`**, not the `budyko_*` set (Budyko = φ / f_temp framing). Catalog: [FIGURES_INDEX.md](../../../analysis/FIGURES_INDEX.md).

Deck: `make_drought_narrative_slides.py` → `drought_narrative_slides.pptx`  
Order: **1 Results → 2 Overland covariates → 3 Local Budyko → 4 Depth mechanism**.

## Condensed story deck (learned Aug 2026)

Short talk version: **7 figures + title** (drought + pumping parity).
PNGs: `make_story_figures.py` (etc.) → `figures/drought_final/`.
Deck file: `figures/decks/drought_story_slides.pptx` via `make_drought_story_slides.py`.
**Authoritative handoff:** [`drought_story_deck_summary.md`](../../../analysis/drought_story_deck_summary.md)
(slide numbering, colors, layout params, reproduce commands).

### Decks: only on request

**Never rebuild PowerPoint decks automatically** after regenerating PNGs.
Stop at the PNG (and index/YAML updates). Run `make_drought_story_slides.py`,
`make_drought_narrative_slides.py`, `make_pumping_vs_drought_slides.py`, or other
`*.pptx` builders **only when the user explicitly asks** to update / rebuild the
deck. Prefer linking and discussing the PNGs in-editor.

- Half the deck **reuses canonical PNGs unchanged** (slide 2 course; slide 6 partition
  uses `fig_aggregate_partition` with **deck-specific** blue/purple + T/P styling).
- Merged figures get `story_*.png` files. Do not duplicate plotting code — import loaders
  from canonical scripts so numbers cannot drift.
- **Deck-only pumping colors** in `make_story_figures.py` (`STORY_PUMP_COLORS` purple
  sequential). Do **not** reuse `pumping_recovery_timeseries.COLORS` (same browns as drought).
- **Every reply about story slides** must include a numbered 8-slide list with PNG links
  (see the handoff).
- **Draft vs final:** `FIGURE_FIDELITY` defaults to `draft` (stride 4). User “final /
  high-fidelity” → `FIGURE_FIDELITY=final`. Draft misses Q peaks — slide 4 yearly-mean
  Q must be rebuilt at final. Cache: `analysis/.tmp_figure_cache/`. Rebuilding PNGs at
  final fidelity still does **not** imply rebuilding the pptx unless asked.
- **Spines:** `despine_axes` / `_save_fig` hide top and right on plot axes.
- **Legends at the bottom** of story-deck figures (`_legend_bottom` /
  `loc="outside lower center"`). Domain / panel **titles stay on top**.
  Single-length courses (slides 2, 7) omit the drought-length line from the
  legend (period fills + baseline only).

### Slides 2 & 7 — period backgrounds

- Orange spinup (3 yr) / pink drought / blue recovery via `shade_sequence_periods`.
- Slide 7 uses `spinup_years=COURSE_SPINUP_YEARS` so the orange band is visible.
- Flush to xlim; no white buffer at the axis edges.
- Legend under the plots; no “10-year drought” handle (only one line).

### Slide 4 — flow anomaly lines

- `fig_recovery_flow_anomaly_combined` uses **`_plot_recovery_flow_on_axes`** /
  **`_plot_pumping_flow_on_axes`** (yearly-mean % anomaly; markers via
  `_length_marker_style` / `_rate_marker_style`).
- Drought row: years 1–5. Pumping row: years 1–10.
- Explicit `fig.subplots_adjust` + **dual bottom legends**; inter-row x-label in axis gap.
- Catalog `story_recovery_flow_anomaly.png` remains the drought-only line plot.

### Slides 3 & 8 — storage + map composites

```python
STORAGE_MAPS_FIG_H = 7.4
STORAGE_MAPS_BAND_Y = (0.78, 4.05)
STORAGE_MAPS_DS_BOTTOM = (STORAGE_MAPS_BAND_Y[1] + 0.38) / STORAGE_MAPS_FIG_H
STORAGE_MAPS_DS_HEIGHT = 0.32
```

- `_domain_band_map_grid(..., col_titles_at_bottom=True, stream_legend_pos="below")`.
- ΔS temp/persist labels in axis **top corners** (white bbox), not on lines.
- Series legend at figure bottom (`bbox_to_anchor=(0.47, 0.01)`); titles on ΔS axes.
- Slide 8 pumping ΔS: focus rate **1e-5 only** on top panel.

### Slide 6 — partition bars (`fig_aggregate_partition`)

- **Deep bottom, near-surface top.** Blue = temporary (left), purple = persistent (right).
- **T / P** above bars; legend: depth swatches + T/P definitions at figure bottom.
- Colors: temp `#C6DBEF`/`#2171B5`, persist `#DCCCE5`/`#7B3294`.

### Overlap policy

User requires **no overlapping text/figures**. After layout edits, visually check PNGs
or bbox-test legends vs axis titles. Prefer inch-based layout over `constrained_layout`
when placing `fig.text` or stacked outside legends.

### Pitfalls hit here

- **Shared y-axis clipping.** `axes[1,1].sharey(axes[1,0])` silently clipped
  Wolf's −11% flow-anomaly points off the bottom. When sharing an anomaly row
  across domains, set an explicit range from **all** plotted values.
- **`ax.set_title` does not clear a `twiny` label.** Either put the title on the
  twin axes (`ax2.set_title`) or drop the twin axis label and let a coloured tick
  scale plus the legend identify the curve.
- **Overland-vs-persist figures need `flow > 0`.** `drought_recovery_drainage_*`
  have **no surviving source script**; rebuild from
  `wtd_threshold_vs_overland.load_bundle_lean` + `cell_table` and exclude cells
  with zero baseline overland flow, which reproduces the published **54% / 42%**
  lowest-quintile mass shares (keeping them gives 65% for Potomac).
- **Sub-annual ΔQ is storm-peak noise.** For "streamflow recovered but storage
  did not", use **yearly-mean Q as % of baseline** (`_annual_flow_anomaly`).
  (The old "Potomac yr 1 overshoots by ~21–25%" was the near-dry config outlet cell.)
- **Outlet flow: use `analysis/outlet_flow.py`.** `analysis_outlet(d)` (Potomac
  mainstem (63, 129), not config (66, 135)); `window_mean_outlet_flow(path, x, y)`
  (catalog `10_year_pumping_tests` years 43–49 store snapshots despite a "mean"
  tag — rebuilt from `derived_hourly.nc`; audit in
  `figures/_data/overland_flow_aggregation_audit.json`); `block_mean(q, stride)`
  for draft. Never subsample flux series or rebuild Q from pressure snapshots.
- **Flow legend ↔ markers** (line catalog figures): use `_length_marker_style` /
  `_rate_marker_style` for plotted points and legend handles.
- **Map column headers above Potomac** overlapped ΔS panels — use
  `col_titles_at_bottom=True`.
- **Stream legend in Wolf ΔS panel** — use `stream_legend_pos="below"`.
- **Pumping ΔS composite:** plot **focus rate only** on top panel; 1e-4 crushes y.
- **Olive/green spinup next to drought red** fails CVD — use Okabe–Ito orange `#E69F00`.
- **Draft time-stride** block-averages Q (yearly means exact); hydrograph peaks are smoothed — use final for slide 2.
- **`_save_fig` recursion:** the helper must call `fig.savefig`, not `_save_fig`.

## Condensed pumping story set (learned Sep 2026)

Pumping-only figures in `figures/pumping_final/` (**no pptx** until asked).
**Authoritative handoff:**
[`pumping_story_set_summary.md`](../../../analysis/pumping_story_set_summary.md).

Builder: `analysis/make_pumping_final_figures.py`.

### Focus science

- **All panels** use catalog **`1e-7` / `1e-6` / `1e-5`**.
- **Never** plot domain-matched rates here — those belong in `comparison/`.
- Courses / mid-regen / recovery windows use **5 recovery years**.
- WTD map band on the recovery composite stays at **`1e-6`** (ΔS shows all rates).

### Style

| Series | Style |
|--------|--------|
| `1e-6` / catalog rates | Purple `STORY_PUMP_COLORS`, **solid**, `lw=1.5` |

### Naming / membership

- Write via `FIG_DIR` with basenames listed under `pumping_final` in
  `FIGURE_CATEGORIES.yaml`.
- **Never** reassign `story_pumping_*` into `pumping_final`.

### When discussing

Numbered list of all **5** `pumping_final` PNGs with links (see handoff).

### Pitfalls

- Rate labels: explicit map — `f"{r:.0e}"` rounds `8.64e-7` → `9e-7`.
- `make_10yr_pumping_story_figures.py` is stress-only; prefer
  `make_pumping_final_figures.py` for the condensed set.

## Comparison set (drought vs matched pumping)

`figures/comparison/` — condensed **3 figures** (flow anomaly, overland,
temp/persist bars). Matched rates only (Potomac `8.64e-7`, Wolf `2.49e-6`) vs
`droughts/10_year_drought`. **Handoff:**
[`comparison_story_set_summary.md`](../../../analysis/comparison_story_set_summary.md).
Builder: `make_comparison_figures.py`.

### Style

| Figure | Encoding |
|--------|----------|
| Flow + bars | Domain browns drought / purple `#7B3294` matched |
| Overland | **Color = domain** (`#009E73` Potomac / `#56B4E9` Wolf); **dash = stress** (solid drought / dashed matched); no markers on cumulative curves; circles on bin panel |

Do **not** put catalog `1e-6` on comparison panels. Do **not** flip overland to
color=stress unless the user asks (tried and reverted Sep 22).

### When discussing

Numbered list of all **3** `comparison/` PNGs with links (see handoff).

## Figure index (required)

Canonical catalog: **`analysis/FIGURES_INDEX.md`**.

**Whenever you create, rename, replace, or delete a figure under `analysis/figures/`, update `FIGURES_INDEX.md` in the same turn** (filename, one-line description, script if known, deck section if any). If it belongs in a condensed deck, also add the basename under the right key in `FIGURE_CATEGORIES.yaml`. Look up the index before regenerating analyses that may already exist.

## Checklist before saving

1. Display names Potomac / Wolf (not `*2`)
2. Units on every y-label; no duplicate labels under each domain
3. Shared x-label once; integer ticks if year axis
4. No `suptitle` for paper figures; legend outside top (paper maps: Stream above cbar; slide maps: Stream at bottom)
5. Labels/legend larger than tick numbers (larger still for Word/doc map figures)
6. Storage scaled; no colliding offset text
7. Drought / spinup / recovery shade + legend patches when a sequence window is shown  
8. Anomaly-row zeros aligned across domains when comparison matters  
9. Top/right spines off (`despine_axes`); colorbars keep their box  
10. Write via `analysis.figure_paths.FIG_DIR / "name.png"` (lands in the right category) at dpi≈150–160  
11. One visual channel per factor; drought lengths use the sequential brown `COLORS` (not categorical jumps)  
12. **Update `analysis/FIGURES_INDEX.md`** (and `FIGURE_CATEGORIES.yaml` if final)

## Reference figures (short list)

Full catalog: [FIGURES_INDEX.md](../../../analysis/FIGURES_INDEX.md).

| File | Content |
|------|---------|
| `drought_recovery_totals_and_anomalies.png` | Recovery: storage, ΔS, flow, ΔQ; 1/3/10/50-yr |
| `ten_year_drought_streamflow_storage.png` | Drought course: Q, S through recovery |
| `drought_recovery_wtd_anomaly_maps_*.png` | Per-domain ΔWTD: start / 1 yr / 5 yr |
| `drought_recovery_drainage_deficit_concentration.png` | Persist mass vs overland ranking |
| `drought_recovery_drainage_threshold_bins.png` | log overland vs dist. stream vs mean persist |
| `drought_recovery_deficit_covariate_spearman.png` | Temp/persist vs covariates |
| `budyko_hexbin_ftemp_vs_predictors.png` | f_temp vs overland / WTD / distance |
| `shallow_deep_mid_drought_regen.png` | Near-surface regenerates mid-drought |
