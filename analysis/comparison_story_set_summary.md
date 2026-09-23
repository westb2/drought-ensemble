# Drought vs matched-pumping comparison set — handoff (Sep 2026)

**Last updated:** 22 September 2026  
**PNGs:** [`figures/comparison/`](figures/comparison/)  
**Script:** [`make_comparison_figures.py`](make_comparison_figures.py)  
**Membership:** [`FIGURE_CATEGORIES.yaml`](FIGURE_CATEGORIES.yaml) → `comparison:`  
**Catalog:** [`FIGURES_INDEX.md`](FIGURES_INDEX.md) § Comparison set  
**Skill:** [`.cursor/skills/drought-ensemble/plotting.md`](../.cursor/skills/drought-ensemble/plotting.md) § Comparison set  
**Sister stream:** [`pumping_story_set_summary.md`](pumping_story_set_summary.md)  
**General figure habits:** `~/.cursor/skills/paper-figures/SKILL.md`

Condensed **drought vs matched pumping** set (**3 figures**). Only
domain-matched rates vs the 10-yr drought — never catalog `1e-6` / multi-rate
ladders here (those live in `pumping_final`).

| Domain | Matched member | Rate (m/h) |
|--------|----------------|-----------:|
| Potomac (`potomac2`) | `pumping_8.64e-7` | **8.64×10⁻⁷** |
| Wolf (`wolf2`) | `pumping_2.49e-6` | **2.49×10⁻⁶** |

Drought twin: `droughts/10_year_drought`. Baseline: `droughts/short_baseline`.
Stress **10 yr** both sides; recovery windows **5 yr**.

**Agent rule:** regenerate / discuss **PNGs** by default. Do **not** rebuild
any `*.pptx`. Prefer linking PNGs for in-editor review.

---

## When discussing this set (required)

Numbered list of all **3** figures under `analysis/figures/comparison/`:

1. [`compare_drought_pump_recovery_flow_anomaly.png`](figures/comparison/compare_drought_pump_recovery_flow_anomaly.png) — yearly-mean outlet % anomaly
2. [`compare_drought_pump_overland_controls.png`](figures/comparison/compare_drought_pump_overland_controls.png) — persist vs overland rank + bins
3. [`compare_drought_pump_temp_persist_bars.png`](figures/comparison/compare_drought_pump_temp_persist_bars.png) — temp/persist totals

Retired from condensed set (still may exist on disk / exploratory): rate curve,
Q/S course, recovery ΔS+WTD maps, mid-regen.

---

## Style conventions (iterated Sep 21–22)

### Flow anomaly + temp/persist bars

| Series | Color | Markers / style |
|--------|-------|-----------------|
| 10-yr drought | Domain browns `#4A2410` Potomac / `#B86B2B` Wolf | Flow: triangles; bars: solid + hatch for T |
| Matched pumping | Purple `#7B3294` | Flow: circles; bars: purple + hatch for T |
| Recovery yr 1 | Soft grey `axvspan(0,1)` | Flow only; legend outside **upper** center |

Shared y across domains on anomaly and bars. Bar titles include matched rate
(`8.64×10⁻⁷` / `2.49×10⁻⁶` m/h). In-bar **P%/T%** labels when segments are tall
enough; totals above bars.

### Overland (figure 2) — final encoding

Tried and **reverted** (do not revive unless asked):

- Color = stress, dash = domain
- Domain browns + purple (collides with other decks)
- Domain-specific markers (○/□) on cumulative curves

**Current (keep):**

| Encoding | Mapping |
|----------|---------|
| **Color** | Domain: Potomac `#009E73` (Okabe–Ito bluish green), Wolf `#56B4E9` (sky blue) |
| **Line style** | Stress: drought **solid**, matched pumping **dashed** `(0, (4.5, 2.0))` |
| Left (cumulative) | **No** markers on curves; small callout dots only at x=0.2 |
| Right (bins) | **All circles** |
| Annotations | Lowest-fifth shares for drought **and** matched (≈54/42% vs ≈25/31%) |

These two Okabe–Ito colors were chosen because they are **not** used as series
colors elsewhere (browns / purples / period orange-pink-blue fills stay put).

---

## Scientific reads (talk hypotheses)

- Matched totals ≈ 10-yr drought totals (~211–214 Potomac, ~204–206 Wolf).
- Matched deficit is **mostly persistent** (little yr-1 rebound); drought has a
  large temporary fraction (esp. Wolf).
- Overland concentration of persist mass is **weaker** under matched pumping
  (~25% / ~31% in lowest fifth vs ~54% / ~42% drought).
- Recovery outlet flow (mainstem, window mean): drought rebounds near baseline
  after yr 1; matched pumping stays depressed longer by a **similar amount in
  both domains** (yr 1 / 2 / 5 ≈ −1.4 / −1.1 / −0.8% Potomac vs −1.3 / −1.0 /
  −0.7% Wolf). The earlier "esp. Potomac" (−7.4 / −6.2 / −4.6%) came from the
  near-dry config cell (66, 135) sampled from stride-4 pressure snapshots — see
  [`potomac_sensitivity_attribution_summary.md`](potomac_sensitivity_attribution_summary.md).

---

## Reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
cd /glade/derecho/scratch/bwest/drought-ensemble
python analysis/make_comparison_figures.py
```

Derecho login shells must run **unsandboxed** (Landlock V3 unsupported).

After membership changes, keep `FIGURE_CATEGORIES.yaml` and `FIGURES_INDEX.md`
in sync. Writers use `FIG_DIR / "name.png"` so files land in `comparison/`.
Prefixes `compare_*` (and `matched_deficit_*`) route here via `figure_paths.py`.

---

## Pitfalls

1. Rate labels: never `f"{rate:.0e}"` — use `_RATE_LABELS` / `_rate_pretty`.
2. Do **not** add catalog `1e-6` to comparison panels.
3. Do **not** flip overland encoding back to color=stress unless asked.
4. Keep basenames under `compare_*` so they stay in `comparison/`.
5. `matched_deficit_10yr_rate_curve.png` may still sit under `comparison/` via
   prefix inference but is **not** in the condensed 3-figure membership.
6. Outlet Q comes from `analysis/outlet_flow.py` (Potomac mainstem (63, 129),
   true window means, block-averaged in draft). Do not reintroduce the config
   outlet or pressure-snapshot Q in `make_10yr_pumping_story_figures.read_series`.
