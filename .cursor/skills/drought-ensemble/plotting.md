# Paper figure conventions (drought-ensemble)

Canonical analysis notebook: `analysis/drought_recovery_comparison.ipynb`  
Figure output dir: `analysis/figures/`  
Prefer **219 h** condensed products (`interval=219`, `file_locations_219h.json`).

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

Drought-length colors (longest = darkest / driest):

```python
COLORS = {1: "#E8C39E", 3: "#B86B2B", 10: "#4A2410", 50: "#140A05"}
```

- Baseline on absolute panels: grey (`"0.65"` / `"0.75"`)
- Drought window shading (match earlier 4-panel style):  
  `ax.axvspan(t0, t1, color="C3", alpha=0.08)`
- Mark drought start/end with vertical lines (`ls="--"`, `ls=":"`)
- Include a legend patch for the shade:

```python
from matplotlib.patches import Patch
Patch(facecolor="C3", alpha=0.25, edgecolor="none", label="drought period")
```

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

## Figure index (required)

Canonical catalog: **`analysis/FIGURES_INDEX.md`**.

**Whenever you create, rename, replace, or delete a figure under `analysis/figures/`, update `FIGURES_INDEX.md` in the same turn** (filename, one-line description, script if known, deck section if any). Look up the index before regenerating analyses that may already exist.

## Checklist before saving

1. Display names Potomac / Wolf (not `*2`)
2. Units on every y-label; no duplicate labels under each domain
3. Shared x-label once; integer ticks if year axis
4. No `suptitle` for paper figures; legend outside top (paper maps: Stream above cbar; slide maps: Stream at bottom)
5. Labels/legend larger than tick numbers (larger still for Word/doc map figures)
6. Storage scaled; no colliding offset text
7. Drought shade + legend patch when a drought window is shown
8. Anomaly-row zeros aligned across domains when comparison matters
9. Write under `analysis/figures/` at dpi≈150–160
10. **Update `analysis/FIGURES_INDEX.md`**

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
