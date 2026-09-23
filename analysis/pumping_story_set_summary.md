# Condensed pumping story set — handoff (Sep 2026)

**Last updated:** 22 September 2026  
**PNGs:** [`figures/pumping_final/`](figures/pumping_final/)  
**Script:** [`make_pumping_final_figures.py`](make_pumping_final_figures.py)  
**Membership:** [`FIGURE_CATEGORIES.yaml`](FIGURE_CATEGORIES.yaml) → `pumping_final:`  
**Catalog:** [`FIGURES_INDEX.md`](FIGURES_INDEX.md) § Condensed pumping story set  
**Skill:** [`.cursor/skills/drought-ensemble/plotting.md`](../.cursor/skills/drought-ensemble/plotting.md) § Condensed pumping story set  
**Sister stream:** [`comparison_story_set_summary.md`](comparison_story_set_summary.md)  
**General figure habits:** `~/.cursor/skills/paper-figures/SKILL.md`

Pumping-only talk figures. **Every panel** uses the catalog ladder
**`1e-7` / `1e-6` / `1e-5`** (purple `STORY_PUMP_COLORS`, solid, equal `lw`).
Never domain-matched rates or drought overlays here — those belong in
`comparison/`.

Ensemble: `10_year_pumping_tests`. Baseline: `droughts/short_baseline`.
Courses / mid-regen / recovery windows use **5 recovery years**.

**Agent rule:** regenerate / discuss **PNGs** by default. Do **not** rebuild
any `*.pptx`. Prefer linking PNGs for in-editor review.

---

## When discussing this set (required)

Numbered list of all **5** figures under `analysis/figures/pumping_final/`:

1. [`ten_year_pumping_streamflow_storage.png`](figures/pumping_final/ten_year_pumping_streamflow_storage.png) — catalog rates (drought-twin basename)
2. [`ten_year_pumping_streamflow_storage_by_rate.png`](figures/pumping_final/ten_year_pumping_streamflow_storage_by_rate.png) — same catalog ladder
3. [`ten_year_pumping_recovery_storage_and_wtd_maps.png`](figures/pumping_final/ten_year_pumping_recovery_storage_and_wtd_maps.png) — ΔS all rates; WTD maps @ `1e-6`
4. [`ten_year_pumping_recovery_flow_anomaly.png`](figures/pumping_final/ten_year_pumping_recovery_flow_anomaly.png)
5. [`story_mid_pump_regen_10yr.png`](figures/pumping_final/story_mid_pump_regen_10yr.png)

Removed from condensed set (Sep 21): overland controls; temp/persist bars
(comparison owns drought↔pump contrasts). Note figures 1 and 2 are currently
the **same plot** under two basenames — drop one if asked.

---

## Stream split (important)

| Stream | Folder | Rates | Drought? |
|--------|--------|-------|----------|
| `pumping_final` | `figures/pumping_final/` | Catalog `1e-7`/`1e-6`/`1e-5` only | No |
| `comparison` | `figures/comparison/` | Domain-matched only | Yes (vs 10-yr drought) |

Do **not** mix matched rates into `pumping_final` or catalog rates into
`comparison`. Do not move `story_pumping_*` out of `drought_final`.

---

## Line / color conventions

| Series | Color | Style |
|--------|-------|-------|
| Catalog rates | Purple `STORY_PUMP_COLORS` | solid, `lw=1.5` |
| Baseline (storage) | `"0.65"` | solid, `lw=1.0` |

Period fills: orange spinup / C3 pink **pumping** / sky blue recovery. Flush
to axes; legends **outside lower center** (courses / mid-regen).

WTD map band on the recovery composite stays at **`1e-6`** even though ΔS shows
all three catalog rates.

---

## Reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
cd /glade/derecho/scratch/bwest/drought-ensemble
python analysis/make_pumping_final_figures.py
# optional: FIGURE_FIDELITY=final
```

Derecho login shells must run **unsandboxed**.
Caches: `analysis/.tmp_figure_cache/10yr_pumping_story/`.

---

## Pitfalls

1. **No matched rates** in this folder.
2. Rate labels: never `f"{rate:.0e}"` — use `_RATE_LABELS`.
3. Recovery length: plot **5** years to fit `short_baseline`.
4. Do not reassign `story_pumping_*` into `pumping_final`.
5. Older stress-only script `make_10yr_pumping_story_figures.py` — prefer
   `make_pumping_final_figures.py` for this set.
