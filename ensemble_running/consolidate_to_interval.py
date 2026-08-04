#!/usr/bin/env python3
"""Consolidate hourly year products to a year-divisible interval.

Default interval is 219 h (40 steps/year; 8760 % 219 == 0), so multi-year
open_mfdataset concat stays aligned on year boundaries.

Hourly input may be:
- ``derived_hourly.nc`` + ``run.out.00001.nc`` (merged via ``hourly_year``), or
- legacy ``processed_output.nc``

Aggregation
-----------
- State fields (pressure, saturation, subsurface_storage): end-of-window snapshot
- Flux / rate fields (overland_flow, overland_bc_flux, evaptrans): window mean,
  with ``*_sum`` derived as ``mean * interval`` (one pass, no second reduction)
- Static fields: copied through
- Derived: ``total_storage`` (domain sum of snapshotted subsurface storage) and
  ``wtd`` (water-table depth from snapshotted pressure/saturation)

Outputs (never overwrites unless ``--overwrite``)
-------------------------------------------------
- ``<raw_run>/processed_output_{interval}h.nc``
- ``processed_full_runs/<ensemble>/<member>/file_locations_{interval}h.json``

Example (interactive node)::

    module load conda && conda activate droughts
    source ~/pf_env.sh
    cd /glade/derecho/scratch/bwest/drought-ensemble/ensemble_running
    python consolidate_to_interval.py --domains wolf2 potomac2 --ensembles droughts \\
        --interval 219 --workers 2
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

import numpy as np
import xarray as xr

# Project imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from parflow.tools.hydrology import calculate_water_table_depth

from ensemble_running.hourly_year import (
    ONE_YEAR_HOURS,
    STATIC_VARS,
    close_hourly_year,
    open_hourly_year,
    resolve_year_dir,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("consolidate")

# Default year-divisible interval used by post-processing and batch consolidation
DEFAULT_INTERVAL = 219
DX_M = 1000.0
DY_M = 1000.0
# CONUS2 vertical discretization used by RunOutputReader (layer fractions × 200 m)
DZ_M = np.array(
    [1.0, 0.5, 0.25, 0.125, 0.05, 0.025, 0.005, 0.003, 0.0015, 0.0005],
    dtype=np.float64,
) * 200.0

SNAPSHOT_VARS = ("pressure", "saturation", "subsurface_storage")
MEAN_VARS = ("overland_flow", "overland_bc_flux", "evaptrans")


def output_name(interval: int) -> str:
    return f"processed_output_{interval}h.nc"


def locations_name(interval: int) -> str:
    return f"file_locations_{interval}h.json"


def consolidated_path(hourly_path: str | Path, interval: int) -> Path:
    """Consolidated file sits in the year directory next to raw/sidecar/legacy."""
    return resolve_year_dir(hourly_path) / output_name(interval)


def _snapshot_last(da: xr.DataArray, interval: int) -> xr.DataArray:
    """End-of-window samples: hours ``interval, 2*interval, ...`` (1-based values)."""
    return da.isel(time=slice(interval - 1, None, interval))


def _wtd_from_snapshots(
    pressure: xr.DataArray, saturation: xr.DataArray, mask: xr.DataArray
) -> xr.DataArray:
    """Water-table depth (y, x) per consolidated time from snapshotted 3D fields."""

    def _one(p, s):
        wtd = calculate_water_table_depth(np.asarray(p), np.asarray(s), DZ_M)
        m = np.asarray(mask)
        if m.ndim == 3:
            m2 = m[0]
        else:
            m2 = m
        m2 = np.where(m2 > 0, 1.0, np.nan)
        # normalize if mask uses domain-id integers
        finite = m2[np.isfinite(m2) & (m2 > 0)]
        if finite.size and finite.max() > 1:
            m2 = m2 / finite.max()
        return wtd * m2

    return xr.apply_ufunc(
        _one,
        pressure,
        saturation,
        input_core_dims=[["z", "y", "x"], ["z", "y", "x"]],
        output_core_dims=[["y", "x"]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[np.float64],
    )


def consolidate_year(
    hourly_path: str | Path,
    interval: int,
    overwrite: bool = False,
    dry_run: bool = False,
) -> Path | None:
    """Write one consolidated NetCDF next to the year dir. Return output path.

    ``hourly_path`` may be legacy ``processed_output.nc``, ``derived_hourly.nc``,
    or the year directory itself.
    """
    hourly_path = Path(hourly_path)
    year_dir = resolve_year_dir(hourly_path)
    out_path = consolidated_path(hourly_path, interval)

    if out_path.exists() and not overwrite:
        log.info("skip existing %s", out_path)
        return out_path

    if dry_run:
        log.info("dry-run would write %s", out_path)
        return out_path

    if ONE_YEAR_HOURS % interval != 0:
        raise ValueError(
            f"interval {interval} does not divide {ONE_YEAR_HOURS}; "
            "years would not align under open_mfdataset"
        )

    # Chunk on full windows so coarsen stays lazy and memory-bounded.
    # open_hourly_year merges raw+sidecar (or opens legacy).
    ds_root = open_hourly_year(hourly_path, chunks={"time": interval})
    try:
        ds = ds_root
        n_time = int(ds.sizes["time"])
        if n_time < interval:
            log.warning("too few timesteps (%d) in %s; skipping", n_time, year_dir)
            return None

        n_keep = (n_time // interval) * interval
        if n_keep != n_time:
            log.warning(
                "truncating %s from %d to %d hours for clean windows",
                year_dir,
                n_time,
                n_keep,
            )
            ds = ds_root.isel(time=slice(0, n_keep))
            n_time = n_keep

        missing_snap = [v for v in SNAPSHOT_VARS if v not in ds]
        missing_mean = [v for v in MEAN_VARS if v not in ds]
        if missing_snap or missing_mean:
            raise KeyError(
                f"{year_dir} missing vars snap={missing_snap} mean={missing_mean}"
            )

        out_vars: dict[str, xr.DataArray] = {}

        for name in STATIC_VARS:
            if name in ds:
                da = ds[name]
                # Drop a singleton time if present on static-like fields
                if "time" in da.dims and da.sizes.get("time", 0) == 1:
                    da = da.isel(time=0)
                out_vars[name] = da

        for name in SNAPSHOT_VARS:
            out_vars[name] = _snapshot_last(ds[name], interval)
            out_vars[name].attrs.update(ds[name].attrs)
            out_vars[name].attrs["aggregation"] = (
                f"last of each {interval}-hour window"
            )

        for name in MEAN_VARS:
            mean = ds[name].coarsen(time=interval, boundary="exact").mean()
            mean.attrs.update(ds[name].attrs)
            mean.attrs["aggregation"] = f"mean over each {interval}-hour window"
            out_vars[name] = mean

            summed = mean * float(interval)
            summed.attrs.update(ds[name].attrs)
            summed.attrs["aggregation"] = (
                f"sum over each {interval}-hour window (= mean * {interval})"
            )
            summed.attrs["note"] = (
                "Derived from window mean to avoid a second pass over hourly data"
            )
            if "units" in summed.attrs:
                summed.attrs["units"] = (
                    f"({summed.attrs['units']}) * {interval} h"
                )
            else:
                summed.attrs["units"] = f"hourly_units * {interval} h"
            out_vars[f"{name}_sum"] = summed

        # End-of-window time coordinates (matches snapshot semantics)
        time_out = ds["time"].values[interval - 1 :: interval]
        for name, da in list(out_vars.items()):
            if "time" in da.dims:
                out_vars[name] = da.assign_coords(time=time_out)

        stor = out_vars["subsurface_storage"]
        total_storage = stor.sum(dim=("x", "y", "z"), skipna=True)
        total_storage.attrs["units"] = "m3"
        total_storage.attrs["long_name"] = "domain-integrated subsurface storage"
        total_storage.attrs["aggregation"] = (
            f"sum of snapshotted subsurface_storage (end of each {interval}h window)"
        )
        out_vars["total_storage"] = total_storage

        mask = out_vars.get("mask", ds["mask"])
        if "time" in mask.dims:
            mask = mask.isel(time=0)
        wtd = _wtd_from_snapshots(out_vars["pressure"], out_vars["saturation"], mask)
        wtd = wtd.assign_coords(time=time_out)
        wtd.attrs["units"] = "m"
        wtd.attrs["long_name"] = "water table depth"
        wtd.attrs["aggregation"] = (
            f"from snapshotted pressure/saturation at end of each {interval}h window"
        )
        out_vars["wtd"] = wtd

        src_attrs = dict(ds_root.attrs)
        out_ds = xr.Dataset(out_vars, attrs=src_attrs)
        out_ds.attrs["source_year_dir"] = str(year_dir)
        out_ds.attrs["source_hourly_ref"] = str(hourly_path)
        out_ds.attrs["consolidation_interval_hours"] = interval
        out_ds.attrs["steps_per_year"] = ONE_YEAR_HOURS // interval
        out_ds.attrs["consolidation"] = (
            "snapshot=last; flux mean + sum(=mean*interval); "
            "derived total_storage and wtd"
        )

        encoding = {}
        for name, da in out_ds.data_vars.items():
            enc = {"zlib": True, "complevel": 4}
            # Reasonable chunk sizes for later lazy reads
            chunks = []
            for dim in da.dims:
                if dim == "time":
                    chunks.append(min(40, da.sizes[dim]))
                elif dim == "z":
                    chunks.append(da.sizes[dim])
                else:
                    chunks.append(min(64, da.sizes[dim]))
            enc["chunksizes"] = tuple(chunks)
            encoding[name] = enc

        # Atomic write: temp in same directory then rename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=out_path.stem + ".",
            suffix=".nc.tmp",
            dir=out_path.parent,
        )
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            out_ds.to_netcdf(tmp_path, encoding=encoding)
            tmp_path.replace(out_path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise
    finally:
        close_hourly_year(ds_root)

    log.info("wrote %s (%.2f GB)", out_path, out_path.stat().st_size / 1e9)
    return out_path


def _worker(args: tuple) -> tuple[str, str | None, str | None]:
    hourly, interval, overwrite, dry_run = args
    try:
        path = consolidate_year(hourly, interval, overwrite=overwrite, dry_run=dry_run)
        return (hourly, str(path) if path else None, None)
    except Exception as exc:  # noqa: BLE001 - surface per-file failures
        return (hourly, None, f"{type(exc).__name__}: {exc}")


def collect_hourly_files(
    root: Path,
    domains: Iterable[str],
    ensembles: Iterable[str],
    members: Iterable[str] | None = None,
) -> tuple[list[str], dict[tuple[str, str, str], list[str]]]:
    """Return unique hourly paths and per-member ordered lists.

    Returns
    -------
    unique_files :
        Deduplicated hourly refs (``derived_hourly.nc`` or legacy
        ``processed_output.nc``; shared hashes once).
    member_files :
        ``(domain, ensemble, member) -> [hourly refs in year order]``
    """
    unique: list[str] = []
    seen: set[str] = set()
    member_files: dict[tuple[str, str, str], list[str]] = {}

    for domain in domains:
        for ensemble in ensembles:
            ens_dir = root / "domains" / domain / "processed_full_runs" / ensemble
            if not ens_dir.is_dir():
                log.warning("missing ensemble dir %s", ens_dir)
                continue
            for member_dir in sorted(ens_dir.iterdir()):
                if not member_dir.is_dir():
                    continue
                member = member_dir.name
                if members is not None and member not in members:
                    continue
                loc = member_dir / "file_locations.json"
                if not loc.is_file():
                    log.warning("missing %s", loc)
                    continue
                files = json.loads(loc.read_text())
                member_files[(domain, ensemble, member)] = files
                for f in files:
                    if f not in seen:
                        seen.add(f)
                        unique.append(f)

    return unique, member_files


def write_interval_indexes(
    root: Path,
    member_files: dict[tuple[str, str, str], list[str]],
    interval: int,
    dry_run: bool = False,
) -> None:
    """Write ``file_locations_{interval}h.json`` for each member."""
    name = locations_name(interval)
    for (domain, ensemble, member), hourly_list in member_files.items():
        out_list = [str(consolidated_path(p, interval)) for p in hourly_list]
        dest = (
            root
            / "domains"
            / domain
            / "processed_full_runs"
            / ensemble
            / member
            / name
        )
        if dry_run:
            log.info("dry-run would write index %s (%d files)", dest, len(out_list))
            continue
        dest.write_text(json.dumps(out_list, indent=2) + "\n")
        log.info("wrote index %s (%d files)", dest, len(out_list))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--root",
        type=Path,
        default=Path("/glade/derecho/scratch/bwest/drought-ensemble"),
        help="Project root",
    )
    p.add_argument(
        "--domains",
        nargs="+",
        default=["wolf2", "potomac2"],
        help="Domains to process (extensible)",
    )
    p.add_argument(
        "--ensembles",
        nargs="+",
        default=["droughts"],
        help="Ensemble folder names under processed_full_runs",
    )
    p.add_argument(
        "--members",
        nargs="+",
        default=None,
        help="Optional member subset (default: all members with file_locations.json)",
    )
    p.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Hours per consolidated step (default {DEFAULT_INTERVAL})",
    )
    p.add_argument("--workers", type=int, default=1, help="Parallel year-file workers")
    p.add_argument("--overwrite", action="store_true", help="Replace existing consolidated files")
    p.add_argument("--dry-run", action="store_true", help="List work without writing")
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only consolidate the first N unique hourly files (smoke tests)",
    )
    p.add_argument(
        "--indexes-only",
        action="store_true",
        help="Only (re)write file_locations_{interval}h.json from existing hourly indexes",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if ONE_YEAR_HOURS % args.interval != 0:
        log.error(
            "interval %d does not divide %d (got %.4f steps/year)",
            args.interval,
            ONE_YEAR_HOURS,
            ONE_YEAR_HOURS / args.interval,
        )
        return 2

    unique, member_files = collect_hourly_files(
        args.root, args.domains, args.ensembles, args.members
    )
    log.info(
        "found %d unique hourly files across %d member sequences",
        len(unique),
        len(member_files),
    )

    if args.indexes_only:
        write_interval_indexes(args.root, member_files, args.interval, dry_run=args.dry_run)
        return 0

    to_run = unique[: args.limit] if args.limit is not None else unique
    log.info(
        "consolidating %d files to %dh with %d worker(s)",
        len(to_run),
        args.interval,
        args.workers,
    )

    failures: list[tuple[str, str]] = []
    if args.workers <= 1:
        for hourly in to_run:
            _, out, err = _worker((hourly, args.interval, args.overwrite, args.dry_run))
            if err:
                log.error("%s -> %s", hourly, err)
                failures.append((hourly, err))
    else:
        tasks = [
            (hourly, args.interval, args.overwrite, args.dry_run) for hourly in to_run
        ]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_worker, t): t[0] for t in tasks}
            for fut in as_completed(futures):
                hourly, out, err = fut.result()
                if err:
                    log.error("%s -> %s", hourly, err)
                    failures.append((hourly, err))

    # Refresh indexes only when we intended the full unique set (or indexes-only).
    # A --limit smoke test would otherwise point at missing consolidated files.
    if args.limit is None:
        write_interval_indexes(args.root, member_files, args.interval, dry_run=args.dry_run)
    else:
        log.warning(
            "skipped writing file_locations_%dh.json because --limit=%d; "
            "re-run without --limit (or with --indexes-only) after the full job",
            args.interval,
            args.limit,
        )

    if failures:
        log.error("%d file(s) failed", len(failures))
        return 1
    log.info("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
