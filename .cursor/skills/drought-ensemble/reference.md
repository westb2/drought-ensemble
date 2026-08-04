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

| Domain | ~GB/year |
|--------|----------|
| wolf2 | ~20 |
| potomac2 | ~56 |
| republican | ~96 |

Check `gladequota` before large resubmits. Unique new hashes across concurrent jobs on one domain share spinup; divergent drought/pumping tails do not.

Missing `processed_output.nc` only (raw already present): potomac2 ≈ **+28 GB/year**. Writing many of these at once (e.g. finishing `droughts/baseline` + `50_year_drought`) can need **~1.5–2 TiB** — confirm free space first.

219 h consolidation: wolf2 ≈ 17 MB/year, potomac2 ≈ 50 MB/year (see [processed-outputs.md](processed-outputs.md)).

## Queued job patterns (Jul 2025 session)

- `3_year_pumping_tests` on potomac2: jobs 6828496–6828499 (rates 1e-4…1e-7); only 3 pump years to run (spinup exists).
- Flow-barrier `3_year_pumping_tests` canceled — would have rerun 40 yr spinup from scratch.
- `5_year_pumping_tests` @ 1e-6: potomac2 + 4 flow-barrier domains (6828738–6828742).

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
