# Processed outputs — consolidation, reading, plotting

Canonical **new** hourly derived product is a thin sidecar next to untouched
ParFlow raw. Analysis should prefer the **219 h** consolidated product when
available (40 steps/year; `8760 % 219 == 0`).

For **paper figure layout, labels, colors, and drought shading**, see
[plotting.md](plotting.md) (also summarized in `SKILL.md`).

## Layout

```
domains/<domain>/raw_runs/<hash>/
  run.out.00000.nc             # statics
  run.out.00001.nc             # ParFlow transient (never amended)
  derived_hourly.nc            # overland_flow + subsurface_storage only (new)
  processed_output.nc          # legacy full hourly (still readable)
  processed_output_219h.nc     # consolidated (40 steps/year)

domains/<domain>/processed_full_runs/<ensemble>/<member>/
  file_locations.json          # ordered hourly refs (sidecar or legacy paths)
  file_locations_219h.json     # ordered consolidated paths
  sequence.json
  run_log.txt
```

`processed_full_runs/` is metadata only. Shared open/merge helpers live in
`ensemble_running/hourly_year.py` (`open_hourly_year`, `write_sidecar_atomic`).

## Why 219 h (not 168)

| Interval | ≈ period | Steps/year | Divides 8760? |
|----------|----------|------------|---------------|
| **219** | ~9.1 days | **40** | yes (default) |
| 120 | 5 days | 73 | yes |
| 168 | 7 days | 52.14 | **no** — breaks clean year stacking under `open_mfdataset` |

Legacy notebooks often used `isel(time=slice(None, None, 219))` or `168` — those are **snapshots**, not window means/sums. Prefer on-disk consolidation.

## Aggregation rules (in `processed_output_219h.nc`)

| Variables | Op | Notes |
|-----------|-----|-------|
| `pressure`, `saturation`, `subsurface_storage` | **last** of window | State / stock |
| `overland_flow`, `overland_bc_flux`, `evaptrans` | **mean**; `*_sum` = mean × 219 | One pass; do not coarsen twice |
| statics (`mask`, `porosity`, …) | copy | No time agg |
| `total_storage` | sum of snapshotted `subsurface_storage` over x,y,z | Scalar series (m³) |
| `wtd` | from snapshotted pressure/saturation | 2D (y, x); CONUS2 `dz` = layer fractions × 200 m |

Time coords on consolidated files are **end-of-window** hour indices (`219, 438, …, 8760`).

### Plotting choice: mean vs sum vs snapshot

- **Storage / WTD / pressure / saturation curves:** use snapshot fields (or `total_storage` / `wtd`).
- **Characteristic discharge / flux rate (m³/h or similar):** use window **mean** (`overland_flow`, etc.).
- **Volume over the window / cumulative mass:** use `*_sum` (or integrate mean × 219).
- Do **not** sum storage across time. Do **not** treat strided `isel` as a substitute for mean/sum when comparing peaks or volumes.

## Automatic post-processing

`classes/RunOutputReader.read_output_netcdf` (default `consolidation_interval=219`):

1. Skips year if valid sidecar (or legacy `processed_output.nc`) exists; removes invalid sidecar/tmp first
2. Else computes derived fields and atomically writes `derived_hourly.nc` (temp → validate → replace)
3. Calls `ensemble_running.consolidate_to_interval.consolidate_year` on the year ref (skips if `*_219h.nc` exists)
4. Writes both `file_locations.json` (sidecar or legacy paths) and `file_locations_219h.json`

Hourly reads merge `run.out.00001.nc` + `derived_hourly.nc` + statics (or open legacy). Do **not** write a new full `processed_output.nc`.

Disable consolidation with `RunOutputReader(run, consolidation_interval=None)`.

Shared implementation: `ensemble_running/hourly_year.py`, `ensemble_running/consolidate_to_interval.py` (`DEFAULT_INTERVAL = 219`).

## Batch backfill (existing years)

For years that predate auto-consolidation (e.g. `droughts` on wolf2/potomac2):

```bash
module load conda && conda activate droughts && source ~/pf_env.sh
cd /glade/derecho/scratch/bwest/drought-ensemble/ensemble_running

# Interactive node recommended (I/O + CPU)
# qsub -I -A UPRI0032 -q develop -l select=1:ncpus=8:mem=200GB -l walltime=06:00:00

python consolidate_to_interval.py \
  --domains wolf2 potomac2 \
  --ensembles droughts \
  --interval 219 \
  --workers 3
```

Extensible: `--domains`, `--ensembles`, `--members`, `--limit` (smoke), `--indexes-only`, `--overwrite` (default off).

**Disk:** consolidated products are small (wolf ~17 MB/yr, potomac ~50 MB/yr). Full `droughts` wolf2+potomac2 backfill ≈ **7 GB** — negligible vs hourly.

Per finished year (Aug 2026 measured):

| Layout | wolf2 | potomac2 |
|--------|------:|---------:|
| New: raw + `derived_hourly.nc` | **~11 GB** (sidecar ~0.8 GB) | **~34 GB** (sidecar ~2–3 GB est.) |
| Legacy: raw + full `processed_output.nc` | ~20 GB (full hourly ~9 GB) | ~56–60 GB (full hourly ~28 GB) |

New years must **not** write full `processed_output.nc` (would re-duplicate pressure/saturation already in `run.out.*`).

## Migrate legacy hourly → sidecar (disk reclaim)

After postprocess jobs are idle, convert existing `processed_output.nc` to
`derived_hourly.nc`, ensure 219h exists, then delete the full hourlies.

```bash
cd /glade/derecho/scratch/bwest/drought-ensemble

# 1) migrate (dry-run then commit) — start with wolf2
python ensemble_running/migrate_to_sidecar.py --domains wolf2 --ensembles droughts
python ensemble_running/migrate_to_sidecar.py --domains wolf2 --ensembles droughts --commit

# 2) spot-check: open_hourly_year → hourly_layout == "raw+sidecar"

# 3) delete legacy (dry-run then commit)
python ensemble_running/migrate_to_sidecar.py --domains wolf2 --ensembles droughts --delete-legacy
python ensemble_running/migrate_to_sidecar.py --domains wolf2 --ensembles droughts --delete-legacy --commit

# 4) repeat for potomac2 / other domains
```

Default is dry-run; `--commit` writes or deletes. Delete gates: valid raw
(`run.out.00001.nc`, `time==8760`), valid `derived_hourly.nc`, valid
`processed_output_219h.nc`. Optional `--require-indexed`. Never deletes raw,
sidecar, or 219h. Use `--limit N` for smoke tests; `--indexes-only` to rewrite
`file_locations.json` toward sidecar paths without migrating.

## Analysis helpers

```python
# Prefer consolidated when plotting multi-year storage/flow
ds = utils.read_simulation_data(
    ensemble_name, member, domain, interval=219
)

# Hourly (raw+sidecar merge, or legacy)
ds_h = utils.read_simulation_data(ensemble_name, member, domain, interval=None)
```

- `read_simulation_data(..., interval=219)` reads `file_locations_219h.json`.
- `read_simulation_data(..., interval=None)` and `read_storage_outlet_series` use `open_hourly_year` / `open_hourly_paths`.
- For new notebooks: load `interval=219` full fields when you need grids; use `total_storage` / `wtd` / outlet from consolidated when possible.
- Rename: loaders map `subsurface_storage` → `storage` when present.

## Variables in hourly products

**Raw** (`run.out.00001.nc`): `pressure`, `saturation`, `evaptrans`, `overland_bc_flux`.

**Sidecar** (`derived_hourly.nc`): `overland_flow`, `subsurface_storage`.

**Statics** (`run.out.00000.nc`): `mask`, `mannings`, `porosity`, `specific_storage`, `DZ_Multiplier`, `slopex/y`, `perm_*`.

**Legacy** `processed_output.nc`: all of the above in one file (still supported).

WTD is **not** stored hourly; it is computed on consolidated snapshots (and on demand in notebooks via `calculate_water_table_depth`).

## Future post-processing extensions

When adding new derived products:

1. Prefer implementing in `consolidate_to_interval.py` (or a sibling module) and calling from `RunOutputReader._maybe_consolidate_year` so batch + automatic paths stay shared.
2. Keep interval year-divisible (`8760 % interval == 0`).
3. Write a parallel `file_locations_<tag>.json`; extend `utils._file_locations` / `read_simulation_data` with an explicit kwarg (do not break hourly default).
4. Document aggregation (snapshot vs mean vs sum) next to the variable; for fluxes, derive sum from mean × Δt.
5. Never overwrite ParFlow raw; write derived fields only via atomic sidecar (or consolidated) publish.

## Scratch / ops reminders

- Check `gladequota` before large ParFlow resubmits (hourly years are TiB-scale; consolidation is not).
- Old domain `domains/wolf` was removed (Aug 2026); use **`wolf2`**.
- `potomac_save` (~1.8 TB) is a candidate cleanup if space is tight — confirm with user before delete.
