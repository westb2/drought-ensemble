# Matched-deficit intermediate pumping runs (agent handoff)

**Created:** 2026-08-26  
**Status:** 3-yr intermediate-rate campaign completed earlier. **10-yr production
matched rates** (same stress length as the drought) are now the analysis focus —
see [`analysis/pumping_story_set_summary.md`](../../../analysis/pumping_story_set_summary.md)
and `matched_deficit_10yr.py` (Potomac `8.64e-7`, Wolf `2.49e-6`).

Use this doc when interpreting results from the **intermediate pumping-rate** members of `3_year_pumping_tests`, or when extending drought-vs-pumping analysis to **10-year drought** totals at comparable storage-deficit magnitude.

---

## Scientific goal

Show that **drought and pumping produce different groundwater memory even when total storage deficit is similar**.

The comparison is **not** “find a pumping rate that replicates drought.” It is:

1. Pick a pumping rate where **end-of-stress total storage deficit** ≈ **10-yr drought total deficit** (domain-specific rate).
2. Hold total deficit fixed (approximately) and contrast **deficit character**:
   - temporary vs persistent fraction (`f_temp`)
   - near-surface vs deep partition (CONUS2 z≥6 = top 2 m)
   - spatial concentration vs overland flow (low-overland cells hold most drought persist)
   - recovery trajectory (ΔS, outlet Q) through 10-yr pumping recovery

Prior work at rates `1e-7…1e-4` only bracketed the matched range coarsely. These four intermediate rates fill the gap between `1e-6` and `1e-5` for log-interpolation.

---

## Ensemble design (unchanged)

| Phase | Years (0-indexed) | Forcing |
|-------|-------------------|---------|
| Spinup | 0–39 | `average` wetness, no pumping |
| Pumping | 40–42 | `average` wetness, constant `pumping_rate_fraction` |
| Recovery | 43–52 | `average` wetness, no pumping |

- **Ensemble:** `3_year_pumping_tests`
- **Domains:** `potomac2` (Potomac), `wolf2` (Wolf)
- **Pumping layer:** 2 (default; same as original four rates)
- **Baseline for deficits:** `droughts/short_baseline` (shared spinup hashes with drought ensemble)
- **Total sequence length:** 53 years

Sequence generator: `run_sequences/3_year_pumping_tests/generate_sequences.py`

---

## All pumping rates (after 2026-08-26)

```python
PUMPING_RATES = [1e-7, 1e-6, 2e-6, 3e-6, 5e-6, 6e-6, 1e-5, 1e-4]
```

Member names on disk: `pumping_1e-7`, `pumping_1e-6`, `pumping_2e-6`, `pumping_3e-6`, `pumping_5e-6`, `pumping_6e-6`, `pumping_1e-5`, `pumping_1e-4`.

**New in this campaign:** `2e-6`, `3e-6`, `5e-6`, `6e-6` only.

---

## Comparison targets: 10-yr drought totals

From `analysis/figures/drought_recovery_50yr_totals.json` (end of 10-yr drought, temp+persist):

| Domain | Temporary (10⁶ m³) | Persistent (10⁶ m³) | **Total** |
|--------|-------------------:|--------------------:|----------:|
| Potomac | 88 | 126 | **214** |
| Wolf | 127 | 76 | **203** |

Drought member: `droughts/10_year_drought` (40 spinup + 10 drought + 5 recovery indexed; deficit computed vs `short_baseline`).

For reference, 3-yr drought totals: Potomac **136**, Wolf **150**.

---

## Predicted end-of-pumping deficits (log-interpolation)

Interpolated from existing 3-yr pumping totals at `1e-6` and `1e-5` (Aug 2026 analysis). **Verify against actual runs** once complete.

| Rate (m/h) | Potomac predicted total | Wolf predicted total |
|------------|------------------------:|---------------------:|
| 1×10⁻⁶ | 91 | 33 |
| **2×10⁻⁶** | **182** | **66** |
| **3×10⁻⁶** | **274** | **100** |
| **5×10⁻⁶** | **458** | **167** |
| **6×10⁻⁶** | **550** | **201** |
| 1×10⁻⁵ | 920 | 338 |

### Domain-specific rates matching 10-yr drought **total** deficit

Log-interpolate between bracketing rates (do not use a single rate for both domains):

| Domain | Matched rate | Predicted total | 10-yr drought target |
|--------|-------------:|----------------:|---------------------:|
| Potomac | **~2.4×10⁻⁶** | ~214 | 214 |
| Wolf | **~6.0×10⁻⁶** | ~203 | 203 |

**Best single grid points after this campaign:**

- Potomac: interpolate between **2×10⁻⁶** (182, −15%) and **3×10⁻⁶** (274, +28%)
- Wolf: **6×10⁻⁶** (201, −1%) is essentially on target

**Important:** No single pumping rate matches both domains at once. At 3×10⁻⁶, Potomac is ~274 vs Wolf ~100 — same rate, very different deficit.

---

## Deficit metrics (canonical definitions)

Same as `pumping_vs_drought_deficits.py` and `.cursor/skills/drought-ensemble/plotting.md`:

- **Storage deficit (per cell):** `S_baseline − S_stressed` (m water equivalent; positive = drier)
- **Domain total:** sum over cells → report in **10⁶ m³**
- **End of pumping stress:** year index **42** (last pumping year)
- **Temporary:** `max(deficit_end_stress − deficit_recovery_yr1, 0)` where recovery yr1 = index **43**
- **Persistent:** `max(deficit_recovery_yr1, 0)`
- **f_temp:** temporary / (temporary + persistent)
- **Near-surface / deep:** integrate storage over CONUS2 layers with **z≥6** (top 2 m) vs z<6

Pumping-specific early/buildup split (optional): see `redo_pumping_recovery_analogues.py`.

---

## Expected qualitative contrast at matched total deficit

From prior 3-yr drought vs pumping at `1e-5` (`analysis/pumping_vs_drought_deficits_summary.md`):

| Property | ~10-yr drought (expect similar) | Pumping at matched rate (expect) |
|----------|--------------------------------|----------------------------------|
| f_temp | Potomac ~0.5–0.6, Wolf ~0.6–0.8 | **~0.12** (low temporary pool) |
| Depth | Temp mass near-surface; persist split NS/deep | **Persist dominated by deep** (layer-2 extraction) |
| Spatial pattern | Low-overland 20% holds ~40–54% of persist | **Near-uniform** over domain |
| Recovery yr 1 | Large ΔS drop | Deficit **stays near end-stress level** |

The matched-deficit exercise should **amplify** this message: similar total volume, different mechanism.

---

## Jobs submitted (2026-08-26)

Submitted from `ensemble_running/` — **only the four new rates**, not the original eight.

| Job ID | Domain | Member |
|--------|--------|--------|
| 7254997 | potomac2 | pumping_2e-6 |
| 7254998 | potomac2 | pumping_3e-6 |
| 7254999 | potomac2 | pumping_5e-6 |
| 7255000 | potomac2 | pumping_6e-6 |
| 7255001 | wolf2 | pumping_2e-6 |
| 7255002 | wolf2 | pumping_3e-6 |
| 7255003 | wolf2 | pumping_5e-6 |
| 7255004 | wolf2 | pumping_6e-6 |

PBS: queue `main`, 4 nodes × 64 MPI, walltime 12 h, account UPRI0032.

Spinup years 0–39 should **reuse** existing hashes; only pump+recovery years (40–52) are new work (~13 years × ~11–34 GB/yr per domain).

---

## How to check completion

```bash
cd /glade/derecho/scratch/bwest/drought-ensemble

# Per member: list missing/incomplete years
python .cursor/skills/drought-ensemble/scripts/years_to_run.py \
  run_sequences/3_year_pumping_tests/pumping_2e-6.json potomac2 wolf2

# Processed 219h index (53 entries when fully post-processed)
ls domains/potomac2/processed_full_runs/3_year_pumping_tests/pumping_2e-6/file_locations_219h.json
```

Complete year criterion (same as watchdog): `raw_runs/<hash>/run.out.00001.nc` exists.

Outputs:

```
domains/<domain>/raw_runs/<hash>/
domains/<domain>/processed_full_runs/3_year_pumping_tests/pumping_<rate>/
```

---

## How to analyze (agent workflow)

### 1. Verify actual end-of-stress totals

Read column-integrated storage at year 42 vs `short_baseline` year 42. Compare to interpolation table above; update matched rates if needed.

Quick script pattern: reuse `_col_storage_m` / `_end_storage` from `analysis/pumping_vs_drought_deficits.py`.

### 2. Extend existing analysis scripts

These hardcode `RATES = [1e-7, 1e-6, 1e-5, 1e-4]` and `_resolve_pump()` name maps — **must update** for new rates:

| Script | Purpose |
|--------|---------|
| `analysis/pumping_vs_drought_deficits.py` | Temp/persist bars, depth partition, fractional recovery |
| `analysis/redo_pumping_recovery_analogues.py` | Early/buildup maps, rate scaling figures |
| `analysis/pumping_recovery_timeseries.py` | Q + S through 10-yr recovery |
| `analysis/make_story_figures.py` | Story deck pumping panels (imports `PT.RATES`) |

**Key change for matched-deficit story:** set `DROUGHT_MEMBER = "10_year_drought"` (currently `"3_year_drought"`) when comparing to 10-yr drought totals.

Suggested new outputs:

- `analysis/figures/matched_deficit_pumping_vs_drought_*.png`
- `analysis/matched_deficit_pumping_runs_summary.md` (results table after runs finish)
- Update `analysis/FIGURES_INDEX.md`

### 3. Pick matched rate per domain from data

```python
# Log-log interpolate rate for target deficit D between (r1,d1) and (r2,d2)
import numpy as np
rate = 10 ** np.interp(np.log10(D), np.log10([d1, d2]), np.log10([r1, r2]))
```

Then plot 10-yr drought vs pumping at matched rate side-by-side:

- temp/persist bars (`shallow_deep_temp_persist_partition.png` style)
- depth partition (NS/deep × temp/persist)
- overland concentration (`pumping_drainage_deficit_concentration.png` style)
- fractional storage recovery through yr 10

### 4. Do not over-interpret

- Matched **total** deficit does not imply matched streamflow anomaly, WTD pattern, or recovery time.
- Pumping stress is **3 yr**; drought comparison target is **10 yr** — the match is on **magnitude at end of pumping**, not duration equivalence.
- Wolf needs ~2.5× higher rate than Potomac for the same total — domain geology/size matters.

---

## Related docs and data

| Resource | Path |
|----------|------|
| This handoff | `.cursor/skills/drought-ensemble/matched-deficit-pumping-runs.md` |
| Results summary (fill in after runs) | `analysis/matched_deficit_pumping_runs_summary.md` |
| 10-yr drought totals | `analysis/figures/drought_recovery_50yr_totals.json` |
| Prior 3-yr drought vs pumping | `analysis/pumping_vs_drought_deficits_summary.md` |
| Deficit map conventions | `.cursor/skills/drought-ensemble/plotting.md` |
| Pumping rate / USGS context | `.cursor/skills/drought-ensemble/pumping-rate-context.md` |
| Sequence JSONs | `run_sequences/3_year_pumping_tests/pumping_*.json` |

---

## Regenerate sequences / resubmit

```bash
cd run_sequences/3_year_pumping_tests
python generate_sequences.py

cd ../../ensemble_running
# All rates (includes complete members — they skip existing years):
python run_ensemble.py 3_year_pumping_tests potomac2 wolf2

# Or submit one member manually — see SKILL.md / restart-ensemble-jobs skill
```

---

## Conversation context (why these rates)

User question: can pumping rates be chosen to match 10-yr drought total deficit, or is the response too nonlinear?

Answer agreed in session:

- **Magnitude:** roughly log-linear in rate between `1e-6` and `1e-5` → interpolation feasible.
- **Mechanism:** strongly nonlinear (f_temp, depth, overland, recovery) → matched total is the **controlled variable** to isolate those differences.
- **Rates chosen:** Option B grid `2, 3, 5, 6 ×10⁻⁶` (8 jobs) rather than only domain-specific `2.5e-6` and `6e-6`, to enable smooth interpolation without extrapolation.
