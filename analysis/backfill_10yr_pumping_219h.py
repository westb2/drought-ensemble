#!/usr/bin/env python3
"""Backfill 219h products for finished 10-yr pumping years (memory-light).

Writes ``processed_output_219h.nc`` directly from raw ParFlow output one
219 h window at a time — avoids materializing a full-year derived sidecar
(which OOMs on login nodes for these domains).

Also writes ``file_locations.json`` / ``file_locations_219h.json`` truncated
to completed stress years (0–49) when present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import xarray as xr
from parflow.tools.hydrology import (
    calculate_overland_flow_grid,
    calculate_subsurface_storage,
    calculate_water_table_depth,
)

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from ensemble_running.hourly_year import STATIC_VARS  # noqa: E402

ENSEMBLE = "10_year_pumping_tests"
INTERVAL = 219
ONE_YEAR = 8760
DZ = np.array([1.0, 0.5, 0.25, 0.125, 0.05, 0.025, 0.005, 0.003, 0.0015, 0.0005]) * 200.0
DEFAULT_RATES = ["1e-7", "1e-6", "1e-5", "1e-4"]
DEFAULT_DOMAINS = ["potomac2", "wolf2"]
DEFAULT_YEAR_LO = 37
DEFAULT_YEAR_HI = 49


def _year_dir(domain: str, seq_years: list[dict], year_idx: int) -> Path:
    key = "_".join(
        f"{y['wetness']}_{y['pumping_rate_fraction']}_{y['irrigation']}"
        for y in seq_years[: year_idx + 1]
    )
    return ROOT / "domains" / domain / "raw_runs" / hashlib.sha256(key.encode()).hexdigest()


def _raw_complete(year_dir: Path) -> bool:
    nc = year_dir / "run.out.00001.nc"
    if not nc.exists():
        return False
    with xr.open_dataset(nc) as ds:
        return int(ds.sizes.get("time", 0)) >= ONE_YEAR


def _load_statics(year_dir: Path) -> dict[str, np.ndarray]:
    with xr.open_dataset(year_dir / "run.out.00000.nc") as st:
        out = {}
        for name in STATIC_VARS:
            if name not in st:
                continue
            da = st[name]
            if "time" in da.dims:
                da = da.isel(time=0)
            out[name] = np.asarray(da.values)
        return out


def write_219h_from_raw(year_dir: Path, *, overwrite: bool = False) -> Path:
    """Build processed_output_219h.nc from raw end-of-window snapshots.

    Storage matches the canonical consolidator (last of each 219 h window).
    Overland flow here is also the end-of-window snapshot (not the window mean)
    so we can finish on a login node without materializing hourly derived fields.
    Rebuild with the full consolidator later for final-fidelity Q.
    """
    year_dir = Path(year_dir)
    out_path = year_dir / f"processed_output_{INTERVAL}h.nc"
    if out_path.exists() and not overwrite:
        return out_path

    statics = _load_statics(year_dir)
    mask = statics["mask"]
    porosity = statics["porosity"]
    specific_storage = statics["specific_storage"]
    slopex = statics["slopex"]
    slopey = statics["slopey"]
    mannings = statics["mannings"]
    n_win = ONE_YEAR // INTERVAL
    ends = np.arange(INTERVAL, ONE_YEAR + 1, INTERVAL) - 1  # 218, 437, …

    press_snap, sat_snap, stor_snap, flow_snap, times = [], [], [], [], []

    with xr.open_dataset(year_dir / "run.out.00001.nc") as tr:
        assert int(tr.sizes["time"]) >= ONE_YEAR
        z = tr["z"].values if "z" in tr.coords else None
        y = tr["y"].values if "y" in tr.coords else None
        x = tr["x"].values if "x" in tr.coords else None
        p_ends = tr["pressure"].isel(time=ends).load()
        s_ends = tr["saturation"].isel(time=ends).load()
        t_ends = tr["time"].isel(time=ends).values
        for w in range(n_win):
            p_end = np.asarray(p_ends.isel(time=w).values)
            s_end = np.asarray(s_ends.isel(time=w).values)
            flow = calculate_overland_flow_grid(
                p_end, slopex, slopey, mannings, 1000.0, 1000.0, mask=mask
            )
            stor = calculate_subsurface_storage(
                porosity,
                p_end,
                s_end,
                specific_storage,
                1000.0,
                1000.0,
                DZ,
                mask=mask,
            )
            press_snap.append(p_end)
            sat_snap.append(s_end)
            stor_snap.append(stor)
            flow_snap.append(flow)
            times.append(float(t_ends[w]))
        del p_ends, s_ends

    press = np.stack(press_snap)
    sat = np.stack(sat_snap)
    stor = np.stack(stor_snap)
    flow = np.stack(flow_snap)
    time_c = np.asarray(times)
    total = np.nansum(stor, axis=(1, 2, 3))
    wtd = np.stack(
        [calculate_water_table_depth(press[i], sat[i], DZ) for i in range(n_win)]
    )
    active = mask.any(axis=0) > 0 if mask.ndim == 3 else mask > 0
    wtd = np.where(active, wtd, np.nan)

    if z is None:
        z = np.arange(press.shape[1])
    if y is None:
        y = np.arange(press.shape[2])
    if x is None:
        x = np.arange(press.shape[3])

    data_vars = {
        "pressure": (["time", "z", "y", "x"], press),
        "saturation": (["time", "z", "y", "x"], sat),
        "subsurface_storage": (["time", "z", "y", "x"], stor),
        "overland_flow": (["time", "y", "x"], flow),
        "total_storage": (["time"], total),
        "wtd": (["time", "y", "x"], wtd),
    }
    for name, arr in statics.items():
        if arr.ndim == 3:
            data_vars[name] = (["z", "y", "x"], arr)
        elif arr.ndim == 2:
            data_vars[name] = (["y", "x"], arr)
        else:
            data_vars[name] = (["z", "y", "x"][: arr.ndim], arr)

    ds = xr.Dataset(
        data_vars,
        coords={"time": time_c, "z": z, "y": y, "x": x},
        attrs={
            "aggregation_interval_h": INTERVAL,
            "source": "backfill_10yr_pumping_219h (raw→219h direct)",
        },
    )
    ds["subsurface_storage"].attrs["aggregation"] = f"last of each {INTERVAL}-hour window"
    ds["overland_flow"].attrs["aggregation"] = (
        f"end-of-window snapshot (not window mean; draft backfill)"
    )
    ds["total_storage"].attrs["units"] = "m3"

    tmp = Path(tempfile.mktemp(prefix=out_path.name + ".", dir=year_dir))
    try:
        ds.to_netcdf(tmp)
        tmp.replace(out_path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return out_path


def write_indexes(domain: str, member: str, seq_years: list[dict], n_years: int) -> tuple[int, int]:
    out_dir = ROOT / "domains" / domain / "processed_full_runs" / ENSEMBLE / member
    out_dir.mkdir(parents=True, exist_ok=True)
    hourly, h219 = [], []
    for yi in range(n_years):
        yd = _year_dir(domain, seq_years, yi)
        if not _raw_complete(yd):
            break
        hourly.append(str(yd / "run.out.00001.nc"))
        p219 = yd / f"processed_output_{INTERVAL}h.nc"
        h219.append(str(p219) if p219.exists() else str(yd / "run.out.00001.nc"))
    (out_dir / "file_locations.json").write_text(json.dumps(hourly))
    (out_dir / "file_locations_219h.json").write_text(json.dumps(h219))
    (out_dir / "sequence.json").write_text(
        (ROOT / "run_sequences" / ENSEMBLE / f"{member}.json").read_text()
    )
    n219 = sum(1 for p in h219 if Path(p).name.startswith("processed_output_219h"))
    return len(hourly), n219


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domains", nargs="+", default=DEFAULT_DOMAINS)
    p.add_argument("--rates", nargs="+", default=DEFAULT_RATES)
    p.add_argument("--year-lo", type=int, default=DEFAULT_YEAR_LO)
    p.add_argument("--year-hi", type=int, default=DEFAULT_YEAR_HI)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--indexes-only", action="store_true")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args(argv)

    work: list[tuple[str, str, int, Path]] = []
    for domain in args.domains:
        for rate in args.rates:
            member = f"pumping_{rate}"
            seq = json.loads(
                (ROOT / "run_sequences" / ENSEMBLE / f"{member}.json").read_text()
            )["years"]
            for yi in range(args.year_lo, args.year_hi + 1):
                if yi >= len(seq):
                    break
                yd = _year_dir(domain, seq, yi)
                if not _raw_complete(yd):
                    print(f"skip missing raw {domain}/{member} y{yi}")
                    continue
                out = yd / f"processed_output_{INTERVAL}h.nc"
                if out.exists() and not args.overwrite:
                    continue
                work.append((domain, member, yi, yd))

    print(f"{len(work)} years need 219h", flush=True)
    if args.dry_run:
        for domain, member, yi, yd in work:
            print(f"  {domain}/{member} y{yi} {yd.name[:12]}")
        return 0

    if not args.indexes_only:
        for i, (domain, member, yi, yd) in enumerate(work, 1):
            t0 = time.time()
            print(f"[{i}/{len(work)}] {domain}/{member} y{yi}…", flush=True)
            write_219h_from_raw(yd, overwrite=args.overwrite)
            print(f"  done in {time.time() - t0:.0f}s", flush=True)

    for domain in args.domains:
        for rate in args.rates:
            member = f"pumping_{rate}"
            seq = json.loads(
                (ROOT / "run_sequences" / ENSEMBLE / f"{member}.json").read_text()
            )["years"]
            n = 0
            for yi in range(len(seq)):
                if _raw_complete(_year_dir(domain, seq, yi)):
                    n = yi + 1
                else:
                    break
            n_stress = min(n, 50)
            nh, n219 = write_indexes(domain, member, seq, n_stress)
            print(f"index {domain}/{member}: {nh} years, {n219} with 219h", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
