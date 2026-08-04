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
- Font sizes: bump **labels and legend** (~11–13); leave **tick numbers** at the default (do not set `tick_params(labelsize=…)` unless asked).

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
COLORS = {1: "#E8C39E", 3: "#B86B2B", 10: "#4A2410"}
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

## Checklist before saving

1. Display names Potomac / Wolf (not `*2`)
2. Units on every y-label; no duplicate labels under each domain
3. Shared x-label once; integer ticks if year axis
4. No `suptitle` for paper figures; legend outside top
5. Labels/legend larger than tick numbers
6. Storage scaled; no colliding offset text
7. Drought shade + legend patch when a drought window is shown
8. Anomaly-row zeros aligned across domains when comparison matters
9. Write under `analysis/figures/` at dpi≈150 with `bbox_inches="tight"`

## Reference figures

| File | Content |
|------|---------|
| `drought_recovery_totals_and_anomalies.png` | Recovery: storage, ΔS, flow, ΔQ; 1/3/10-yr |
| `ten_year_drought_streamflow_storage.png` | Drought course: Q, S through recovery |
