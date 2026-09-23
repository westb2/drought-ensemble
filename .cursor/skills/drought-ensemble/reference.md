# drought-ensemble reference

## Sequence hashing

```python
# classes/Run.py — year N folder depends on ALL years 0..N
"_".join(f"{y['wetness']}_{y['pumping_rate_fraction']}_{y['irrigation']}" for y in years)
sha256(sequence_string)
```

Implications:
- Year 5 of a 5+3 pumping test has a different hash than year 5 of 40-year spinup (different prefix).
- potomac2 y0–y4 of `5_year_pumping_tests` reuse hashes from `40_year_spinup` y0–y4.
- Flow-barrier domains only executed y0–y1 of that shared prefix; y2+ must run on each barrier domain.

## Pumping verification (mass balance)

For wolf2 `pumping_1e-7` year 3: expected volume from `fluxes_on.pfb` over 8760 h ≈ 306,146 m³; extra subsurface storage loss vs baseline ≈ 305,875 m³ (ratio 0.999). ParFlow applies EvapTrans correctly when formula is right.

## PBS log ↔ timestamp workflow

1. Find `Running year N of the run in …/raw_runs/<hash>` in `ensemble_running/<job>.o*`.
2. For each hash, read `run.out.00000.nc` → `run.out.00001.nc` mtime delta = ParFlow sim hours.
3. Consecutive `run.out.00001.nc` end times in the same job = wall hours/year (includes restart + light postprocess).

Example potomac2 job (Jul 2025): 5 new years in 4.4 h → ~13 yr/12 h extrapolated.

## Ensemble naming traps

| Name | Means |
|------|-------|
| `3_year_pumping_tests` | 3 **pumping** years (after 40 yr spinup) |
| `5_year_pumping_tests` | 5 **spinup** years + 3 pumping |
| `pumping_test/3_year_drought` | misnamed — all years `average`, includes pump + recovery |

## Flow-barrier `pumping_test/3_year_drought` (8 yr)

```
y0-1: average, no pump   (spinup)
y2-4: average, pump 0.01
y5-7: average, no pump   (recovery)
```

Completed on 0011/002/005 (~8 h total). Useful for barrier sensitivity at 0.01; not drought weather.

## Disk per finished year (approx, full `raw_runs` dir)

Measured Aug 2026. **Budget new submits with the “new year” column** — postprocess no longer duplicates storage into full `processed_output.nc`.

| Domain | New year (raw + `derived_hourly`) | Legacy (raw + full hourly) |
|--------|----------------------------------:|---------------------------:|
| wolf2 | **~11 GB** (measured; sidecar ~0.8 GB) | ~20 GB |
| potomac2 | **~34 GB** (raw+CLM ~31 GB; sidecar ~2–3 GB est.) | ~56–60 GB |
| republican / ponca | **~56 GB** (raw+CLM ~54 GB + thin sidecar) | ~100–103 GB |

Check `gladequota` before large resubmits. Unique new hashes across concurrent jobs on one domain share spinup; divergent drought/pumping tails do not.

Do **not** budget +28 GB/year for missing full hourlies anymore — new postprocess writes the thin sidecar. Migrating legacy → sidecar reclaim ≈ half the year folder (see [processed-outputs.md](processed-outputs.md)).

219 h consolidation: wolf2 ≈ 17 MB/year, potomac2 ≈ 50 MB/year.

## Queued job patterns (Jul 2025 session)

- `3_year_pumping_tests` on potomac2: jobs 6828496–6828499 (rates 1e-4…1e-7); only 3 pump years to run (spinup exists).
- Flow-barrier `3_year_pumping_tests` canceled — would have rerun 40 yr spinup from scratch.
- `5_year_pumping_tests` @ 1e-6: potomac2 + 4 flow-barrier domains (6828738–6828742).

## Matched-deficit intermediate pumping (Aug 2026)

Four new rates (`2e-6`, `3e-6`, `5e-6`, `6e-6`) on potomac2 + wolf2 to interpolate pumping totals to **10-yr drought** storage deficit (~214 / ~203 ×10⁶ m³). Jobs **7254997–7255004**. Full agent handoff: **[matched-deficit-pumping-runs.md](matched-deficit-pumping-runs.md)**; results table: `analysis/matched_deficit_pumping_runs_summary.md`.

## Static vs transient spinup

| Type | Location | Forcing |
|------|----------|---------|
| Static PME | `domains/*/spinup/run/` | equilibrium pme.pfb |
| Transient average | `raw_runs/<hash>/` | `inputs/*_average/forcing` |

New sequences restart from static PME only for year 0; subsequent years chain from prior year's pressure.

## Domain inventory notes (Aug 2026)

- **`wolf` removed** from `domains/` — use **`wolf2`** only.
- `potomac_save` (~1.8 TB) is an older tree; candidate for deletion if scratch is tight (ask user first).
- Analysis loaders and consolidation details: [processed-outputs.md](processed-outputs.md).
