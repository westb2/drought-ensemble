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
  user-specified rates to USGS water use, screening HUCs for new domains,
  consolidating timesteps, reading processed NetCDF, plotting storage/WTD/
  streamflow, paper figures (domain display names, shared axes, units, drought
  shading, legend placement), or working with potomac2 / potomac_flow_barrier_* /
  wolf2 / republican / ponca domains.
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

**Must follow:**

| Rule | Detail |
|------|--------|
| Display names | `potomac2`→**Potomac**, `wolf2`→**Wolf** (code IDs unchanged) |
| Grid | Columns = domains; rows = metrics; `sharex="col"` |
| Labels | Y-labels + units **left column only**; one `fig.supxlabel`; no duplicate domain labels |
| Paper title | **No** `fig.suptitle` — legend `loc="outside upper center"` |
| Fonts | Larger labels/legend (~11–13); leave tick number size alone |
| Storage scale | Plot as 10⁹ / 10⁶ m³; `useOffset=False` to avoid colliding `1e11` text |
| Drought shade | `axvspan(..., color="C3", alpha=0.08)` + legend `Patch` labeled “drought period” |
| Anomaly rows | `sharey` across domains so **zero aligns** |
| Year axis | Integer ticks (`MultipleLocator`); label origin clearly (drought start vs recovery onset) |

Drought-length colors: `{1: "#E8C39E", 3: "#B86B2B", 10: "#4A2410"}`. Figures → `analysis/figures/`.

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
| `3_year_pumping_tests` | **40** yr average spinup + **3** yr pumping (name = pumping block) |
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
| Streamflow / flux **rate** | Window **mean** |
| Streamflow / flux **volume** | `*_sum` (= mean × 219) |

Do not use calendar weeks (168 h) for on-disk products — they do not divide 8760. Full rules, backfill commands, and loader notes: [processed-outputs.md](processed-outputs.md).

## Parallel job safety

- **Safe:** same sequence on **different domains** (separate `raw_runs/` trees).
- **Unsafe:** two jobs on the **same domain** that would write the same year hash concurrently (e.g. `droughts/baseline` and another all-average prefix on the same domain).
- Existing year folders are **skipped** with no completeness check — delete tip incompletes before restart (see `restart-ensemble-jobs` + `incomplete-year-cleanup` rule).
- Before deletes: `qstat` — never remove hashes an **`R`** job is writing; list paths and confirm with the user.

## Scratch space

Run `gladequota` before large submits. Approx full-year `raw_runs` size: wolf2 ~20 GB, potomac2 ~56 GB, republican ~96 GB. Count **unique new hashes** per domain. If free ≪ need, free space or hold large domains before `qsub`.

Consolidation to 219 h is cheap (~MB/year); ParFlow raw + legacy full `processed_output.nc` dominate quota. New years write thin `derived_hourly.nc` instead of full hourly. Leave ≥~1 TiB headroom when writing many missing Potomac derived products.

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
- **Delete partial years:** `.cursor/rules/incomplete-year-cleanup.mdc`
- **Deep reference:** [reference.md](reference.md)
- **Processed outputs / analysis:** [processed-outputs.md](processed-outputs.md)
- **Paper figure / plotting conventions:** [plotting.md](plotting.md)
- **Catchment / USGS / CONUS context (rates stay user-controlled):** [pumping-rate-context.md](pumping-rate-context.md)

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
