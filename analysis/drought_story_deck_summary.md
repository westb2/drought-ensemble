# Condensed drought story deck — handoff (Sep 2026)

**Last updated:** 20 September 2026 (pptx rebuilds only on request; category folders)  
**Deck:** [`figures/decks/drought_story_slides.pptx`](figures/decks/drought_story_slides.pptx) — **8 slides** (1 title + 7 figures)  
**Scripts:** [`make_story_figures.py`](make_story_figures.py) → PNGs; [`make_drought_story_slides.py`](make_drought_story_slides.py) → pptx **only when asked**  
**Catalog:** deck table in [`FIGURES_INDEX.md`](FIGURES_INDEX.md)  
**Skill:** [`.cursor/skills/drought-ensemble/plotting.md`](../.cursor/skills/drought-ensemble/plotting.md) § Condensed story deck  
**General figure habits:** `~/.cursor/skills/paper-figures/SKILL.md`

Goal: cut the 35-slide [`drought_narrative_slides.pptx`](figures/decks/drought_narrative_slides.pptx)
down to a short talk deck. The long deck and `make_drought_narrative_slides.py` are
unchanged. Pumping-recovery parity at the end contrasts drought vs pumping storage memory.

**Agent rule:** regenerate / discuss **PNGs** by default. Do **not** run pptx builders
unless the user explicitly asks to update the deck (easier in-editor PNG review).

---

## When discussing story slides (required)

**Every** user-facing reply about this deck must open with a **numbered list of all 8 slides** and markdown links to the current PNGs (title has no PNG). User asked for this on 10 Sep 2026 and said to keep doing it.

Paths under `analysis/figures/`:

1. Title — Drought storage memory *(no PNG)*
2. [`ten_year_drought_streamflow_storage.png`](figures/drought_final/ten_year_drought_streamflow_storage.png)
3. [`story_recovery_storage_and_wtd_maps.png`](figures/drought_final/story_recovery_storage_and_wtd_maps.png)
4. [`story_recovery_flow_anomaly_combined.png`](figures/drought_final/story_recovery_flow_anomaly_combined.png)
5. [`story_overland_controls_persistence.png`](figures/drought_final/story_overland_controls_persistence.png)
6. [`shallow_deep_temp_persist_partition.png`](figures/drought_final/shallow_deep_temp_persist_partition.png)
7. [`story_mid_drought_regen_10yr.png`](figures/drought_final/story_mid_drought_regen_10yr.png)
8. [`story_pumping_recovery_storage_and_wtd_maps.png`](figures/drought_final/story_pumping_recovery_storage_and_wtd_maps.png)

Slide numbers without “original / long deck” mean **this** deck. **Figure # = deck slide − 1.**

---

## Current deck (authoritative — matches `make_drought_story_slides.py`)

| Deck | Fig | Title | PNG | Builder |
|------|-----|-------|-----|---------|
| 1 | — | Drought storage memory | — | `slide_title` |
| 2 | 1 | A 10-year drought draws storage down for the whole drought | `ten_year_drought_streamflow_storage.png` | `redo_recovery_with_50yr.fig_drought_course` |
| 3 | 2 | Recovery is two-phase; near-stream cells recover, uplands stay dry | `story_recovery_storage_and_wtd_maps.png` | `make_story_figures` |
| 4 | 3 | Streamflow returns within a year; pumping stays depressed after shutoff | `story_recovery_flow_anomaly_combined.png` | `make_story_figures` (**lines**, not bars) |
| 5 | 4 | The persistent deficit sits where overland flow is low | `story_overland_controls_persistence.png` | `make_story_figures` |
| 6 | 5 | Temporary saturates, persistent grows — and persistent is deep | `shallow_deep_temp_persist_partition.png` | `shallow_deep_shielding.fig_aggregate_partition` |
| 7 | 6 | Near-surface regenerates through the drought; deep ratchets down and only partly refills | `story_mid_drought_regen_10yr.png` | `make_story_figures` → `fig_mid_drought_regen` |
| 8 | 7 | After pumping: little returns in year 1; near-stream cells recover first | `story_pumping_recovery_storage_and_wtd_maps.png` | `make_story_figures` |

---

## Draft vs final fidelity

Default is **`FIGURE_FIDELITY=draft`** in `redo_recovery_with_50yr.py` (every 4th 219 h step ≈ 36 days). 1D series cache under `analysis/.tmp_figure_cache/` (gitignored via `.tmp*/`). After the first load, course/regen redraws are ~0.6 s.

| Mode | How | Use |
|------|-----|-----|
| **draft** | default, or `FIGURE_FIDELITY=draft` | Layout / colors / spines while iterating |
| **final** | `FIGURE_FIDELITY=final` in the env **before import**, or `R.FIGURE_FIDELITY = "final"` after import; user says “final version” / “high fidelity” | Every condensed step |

**Draft block-averages outlet flow** over each 4-window block (≈36 days), so yearly means (slide 4) are exact in draft; the slide-2 hydrograph is smoothed (peaks lower than in final). Storage / ΔS are subsampled snapshots and usually fine in draft.

When the user asks for the final/high-fidelity version: set `FIGURE_FIDELITY=final`
and rebuild the affected **PNGs** only. **Do not** run `make_drought_story_slides.py`
(or any other pptx builder) unless they also ask to update the deck — prefer viewing
PNGs in the editor.

---

## Reproduce (PNGs; pptx only if asked)

```bash
conda activate /glade/work/bwest/conda-envs/droughts
source ~/pf_env.sh
cd /glade/derecho/scratch/bwest/drought-ensemble

# Default = draft. For the deliverable:
#   FIGURE_FIDELITY=final python analysis/make_story_figures.py

python analysis/make_story_figures.py

python -c "
from analysis import redo_recovery_with_50yr as R
R.fig_drought_course(R.load_all_series(), 10, 'ten_year_drought_streamflow_storage.png')
"

python -c "
from analysis import shallow_deep_shielding as S, redo_recovery_with_50yr as R
zp = {d: {L: S.zone_deficit_pair(d, L) for L in S.available_lengths(d)} for d in R.DOMAINS}
S.fig_aggregate_partition(zp)
"

# ONLY when the user explicitly asks to rebuild the PowerPoint:
# python analysis/make_drought_story_slides.py
```

Shell on Derecho login nodes must run **unsandboxed** (Landlock V3 unsupported).

### Partial rebuild (single slide)

| Slide | Command |
|-------|---------|
| 2 | `R.fig_drought_course(..., 'ten_year_drought_streamflow_storage.png')` |
| 3, 4, 5, 7, 8 | relevant function in `make_story_figures.py` (see `main()`) |
| 6 | `S.fig_aggregate_partition(zone_pairs)` |
| 4 (Q means) | load drought with **final** fidelity, then `M.fig_recovery_flow_anomaly_combined` |
| pptx only | `python analysis/make_drought_story_slides.py` — **user must ask**; needs PNGs present |

---

## Visual design (current — do not regress)

### Legends and titles

- **Titles on top** (domain / panel `set_title`). **Figure legends under the plots**
  (`loc="outside lower center"` or `_legend_bottom`). Do not put the series legend
  above the domain titles.
- Slides 2 and 7 are a single drought length: omit the “10-year drought” line from
  the legend (keep baseline + period patches).

### Color palettes

| Context | Palette | Where |
|---------|---------|-------|
| Drought length / ΔS | Brown sequential `COLORS` in `redo_recovery_with_50yr` | Slides 2–5, 7 |
| **Sequence periods** | Okabe–Ito **orange** spinup `#E69F00`; C3 pink drought; sky blue recovery `#9ECAE1` | Slides 2 and 7 (`shade_sequence_periods`) |
| **Deck pumping only** | Purple sequential `STORY_PUMP_COLORS` in `make_story_figures.py` | Slides 4, 8 |
| Partition bars | Blue = temporary, purple = persistent; saturation = depth | Slide 6 |

**Period fills** (helpers in `redo_recovery_with_50yr.py`):

```python
COURSE_SPINUP_YEARS = 3
PERIOD_SPINUP_FACE = "#E69F00"      # Okabe–Ito orange; NOT olive/khaki
PERIOD_DROUGHT_FACE = "C3"
PERIOD_RECOVERY_FACE = "#9ECAE1"
# shade_sequence_periods(ax, drought_length, t_left, t_right)  # flush to xlim
# despine_axes(fig)  # hide top/right spines; skip colorbars
```

User rejected olive/gold spinup next to drought pink (red–green CVD). Orange / pink / blue is the safe triad. Do **not** reuse green or khaki for spinup.

**Deck pumping colors** (do **not** use canonical `pumping_recovery_timeseries.COLORS` — those match drought browns):

```python
STORY_PUMP_COLORS = {1e-7: "#DCCCE5", 1e-6: "#B084CC", 1e-5: "#7B3294", 1e-4: "#3C096C"}
STORY_PUMP_TEMP = "#C994C7"
STORY_PUMP_PERSIST = "#984EA3"
```

User rejected blue/green for pumping (wetness cue) and brown (confusion with drought).

### Spines

`despine_axes(fig)` before save: **no top or right** spines on plot axes. Maps already have all spines off. Leave colorbar boxes intact. `make_story_figures._save_fig` applies this automatically.

### Slides 2 & 7 — course period backgrounds

- **Orange** = last 3 spinup years (average forcing); **pink** = drought; **blue** = recovery.
- Slide 7 includes `spinup_years=COURSE_SPINUP_YEARS` so the orange band actually appears (axis −3 → 15, same window as slide 2).
- Fills must run **flush to the axis frame** (bleed + `margins(x=0)` + `set_xlim`); no white strip at left/right.
- Legend **under** the plots: period patches (+ baseline on slide 2). **No** “10-year drought” handle — only one line.
- Domain titles stay on the top row. No `fig.suptitle`.

### Slide 3 & 8 — storage + ΔWTD composites

Constants in `make_story_figures.py`:

```python
STORAGE_MAPS_FIG_H = 7.4
STORAGE_MAPS_BAND_Y = (0.78, 4.05)
STORAGE_MAPS_DS_BOTTOM = (STORAGE_MAPS_BAND_Y[1] + 0.38) / STORAGE_MAPS_FIG_H
STORAGE_MAPS_DS_HEIGHT = 0.32
```

- **`col_titles_at_bottom=True`:** recovery-stage labels under Wolf row (not above Potomac).
- **`stream_legend_pos="below"`** on both slides (stream key under colorbar, not in plot area).
- ΔS **temporary/persistent** labels in **top corners** of axes (`transAxes` + white bbox), not on data lines.
- Series legend at figure **bottom** (`bbox_to_anchor=(0.47, 0.01)`); ΔS titles remain on the axes.

### Slide 4 — flow-anomaly lines

- **`_plot_recovery_flow_on_axes` / `_plot_pumping_flow_on_axes`** (reverted from grouped bars 10 Sep 2026).
- Yearly-mean outlet Q as % of baseline; length/rate **markers** via `_length_marker_style` / `_rate_marker_style`.
- Drought row: years 1–5. Pumping row: years 1–10. Shared y from `_flow_anomaly_pct_arrays`.
- Dual **bottom** legends (drought length above pumping rate); row labels “Drought” / “Pumping”; inter-row x-label in the axis gap.
- Outlet Q is **window-mean `overland_flow` at the Potomac mainstem (63, 129)** via `analysis/outlet_flow.py` (block-averaged in draft, never subsampled). The old "Potomac yr-1 overshoot ~+21%" was the near-dry config cell (66, 135); at the mainstem Potomac yr 1 is ≈ −5% (10-yr) / −6% (50-yr), no overshoot.

### Slide 6 — partition bars (`fig_aggregate_partition`)

- **Stack order:** deep (saturated) **bottom**, near-surface (light) **top**.
- **Left bar = temporary (blue), right = persistent (purple):**
  - temp: `#C6DBEF` / `#2171B5`
  - persist: `#DCCCE5` / `#7B3294`
- **T / P** labels above each bar (`fontsize=10`, `ylim` headroom ×1.10).
- Legend at bottom: near-surface / deep swatches + “T = temporary …” / “P = persistent …”.

### Overlap policy

User has repeatedly asked for **no overlapping text/figures**. After layout changes:

1. Re-read the PNG (or run bbox overlap check on figure artists before save).
2. Prefer explicit inch/`subplots_adjust` over `constrained_layout` when adding `fig.text` / dual legends.
3. Map composites: enforce gap between ΔS bottom and map band top via `STORAGE_MAPS_*` constants.
4. Story-deck legends sit **under** the plots (`outside lower center` / `_legend_bottom`). Do not put them above domain titles.

---

## Key implementation notes

### `_domain_band_map_grid` (`make_story_figures.py`)

- One map row per domain; embeddable via `band_y=(y_bottom, y_top)` in inches.
- **`stream_legend_pos`:** `"above"` | `"below"` | `None` (standalone uses figure bottom).
- **`col_titles_at_bottom`:** column headers under map grid.

### Flow anomaly (slide 4)

- **Yearly-mean Q as % of baseline** (`_annual_flow_anomaly`); not sub-annual ΔQ.
- Shared y across all four panels via `_flow_anomaly_pct_arrays`.

### Pumping storage+maps (slide 8)

- Top ΔS: **focus rate 1e-5 only**.
- Maps: **1e-5 only**, recovery start / 1 yr / 5 yr.

### Outputs from `make_story_figures.py`

| File | In deck? |
|------|----------|
| `story_recovery_storage_and_wtd_maps.png` | slide 3 |
| `story_recovery_flow_anomaly_combined.png` | slide 4 |
| `story_overland_controls_persistence.png` | slide 5 |
| `story_mid_drought_regen_10yr.png` | slide 7 |
| `story_pumping_recovery_storage_and_wtd_maps.png` | slide 8 |
| `story_recovery_flow_anomaly.png` | catalog (drought-only lines) |
| `story_pumping_recovery_flow_anomaly.png` | catalog |
| `story_recovery_and_streamflow.png` | legacy catalog |
| `story_wtd_recovery_maps.png` | catalog |

Loaders: `redo_recovery_with_50yr`, `wtd_threshold_vs_overland`, `pumping_recovery_timeseries`,
`shallow_deep_shielding`, `redo_pumping_recovery_analogues.read_wtd` (pumping WTD only).

---

## Verification (numbers must not drift)

| Quantity | Rebuilt | Reference |
|----------|---------|-----------|
| Lowest-flow 20% share of persistent mass | Potomac 54%, Wolf 42% | `drought_recovery_drainage_deficit_concentration.png` |
| Recovery yr-1 mean Q anomaly, 50-yr (mainstem, window mean) | Potomac −5.9%, Wolf −11.0% | `figures/_data/psa_summary.json` step0 (`d50.rec1.main`) — the old "+21%" was the config cell |
| Wolf mean persist in lowest log-flow bin | 0.136 m | `drought_recovery_drainage_threshold_bins.png` |

---

## Gotchas

1. **Slide-15/16 overland figures have no surviving source script.** Rebuild from
   `wtd_threshold_vs_overland.load_bundle_lean` + `cell_table`.
2. **Exclude zero-baseline-overland-flow cells** (`t["flow"] > 0`) for 54% / 42% shares.
3. **Do not share y without checking limits** — Wolf −11% was clipped once.
4. **Outlet flow source (fixed 22 Sep 2026).** All outlet series go through `analysis/outlet_flow.py`: Potomac uses the mainstem (63, 129), not the near-dry config cell (66, 135); flow is the true 219 h window mean (snapshot-tagged backfill years are rebuilt from `derived_hourly.nc`) and draft **block-averages** instead of subsampling. The earlier "Potomac yr-1 overshoot ~21–25%" was a config-cell artifact. Series caches carry `_o{x}-{y}_wm1` in the name.
5. **`FIGURES_INDEX.md` may be edited by other sessions** — re-read before editing.
6. **Shell unsandboxed** on Derecho login nodes.
7. **`shallow_deep_shielding.py main()`** regenerates many non-deck figures; use targeted
   `fig_aggregate_partition` call when only slide 6 changed.
8. **Do not change `pumping_recovery_timeseries.COLORS`** for deck parity — use `STORY_PUMP_*` in `make_story_figures.py` only.
9. **Do not pair olive/green period fill with drought red** (CVD). Spinup is Okabe–Ito orange.
10. **`_save_fig` must call `fig.savefig`**, not recurse into itself.

---

## Not done / possible next steps

- **Final-fidelity rebuild of story PNGs** when the user says the figures are done (default is still draft). Rebuild the **pptx only if they ask**.
- **Per-slide caption text** — deck is title + figure only.
- **Title slide subtitle** still drought-length only; could mention pumping.
- **Opener swap:** `fifty_year_drought_streamflow_storage.png` for more drama.
- **Budyko §3** (long deck slides 21–28) absent.
- **Slide 6 CVD:** user considered blue+orange; settled on blue+purple with T/P labels.
- **50-yr baseflow partition** (`fifty_year_streamflow_baseflow_partition.png`) is analysis, not in this deck.
- **No git commits** unless user requests.

---

## Session history

### 10 September 2026 (later)

1. Story-deck figure legends moved **under** the plots; domain titles stay on top.
2. Slides 2 and 7: dropped the redundant “10-year drought” legend handle.

### 10 September 2026 (earlier)

1. Slides 2 & 7: shared period backgrounds (spinup / drought / recovery), flush to axis edges; slide 7 gained 3 spinup years.
2. Spinup fill: khaki-olive → **Okabe–Ito orange** `#E69F00` (CVD-safe with drought pink).
3. **Draft/final** timestep stride + `.tmp_figure_cache` for faster iteration.
4. Slide 4: grouped bars → **lines** again.
5. All story-deck plot axes: **no top/right spines** (`despine_axes`).
6. User: always list the 8 slides with PNG links when talking about the deck.

### 26 August 2026

1. Map composites (slides 3, 8): column titles **below** maps; stream legend **below colorbar**; ΔS/map gap via `STORAGE_MAPS_*`.
2. **No overlapping text** pass on all slides.
3. **Pumping deck colors:** purple sequential (`STORY_PUMP_COLORS`).
4. Slide 6: deep below near-surface; blue temp / purple persist; **T/P bar labels**.

---

## Files touched (cumulative for this deck)

| File | Role |
|------|------|
| `analysis/make_story_figures.py` | Story figures, `_save_fig` / despine, flow lines, map grid, pumping colors |
| `analysis/make_drought_story_slides.py` | `SLIDES` list → pptx |
| `analysis/shallow_deep_shielding.py` | `fig_aggregate_partition`, `fig_mid_drought_regen` (+ spinup years) |
| `analysis/redo_recovery_with_50yr.py` | Slide 2 course; `shade_sequence_periods`; `FIGURE_FIDELITY`; `despine_axes` |
| `analysis/FIGURES_INDEX.md` | Deck catalog |
| `analysis/figures/drought_story_slides.pptx` | Deliverable |
| `.cursor/skills/drought-ensemble/plotting.md` | Conventions + pitfalls |
| `.cursor/skills/drought-ensemble/SKILL.md` | Pointers |
| `~/.cursor/skills/paper-figures/SKILL.md` | General spines / period-shade / CVD habits |
