#!/usr/bin/env python3
"""Per-year slim extraction for the Potomac sensitivity attribution analysis.

One cache file per raw-run hash (years shared between members are extracted
once) under ``figures/_cache/psa/<domain>/<hash>.nc`` with 40 × 219 h windows:

- ``q``        outlet-style overland flow grid from pressure snapshots (m³/h)
- ``gain``     net surface outflow divergence per cell (m³/h, + = cell exports)
- ``s_ns`` / ``s_deep``  near-surface (z≥6, top 2 m) / deep storage (m water)
- ``wtd``      water-table depth snapshot (m)
- ``sat_rz``   dz-weighted saturation of the CLM root zone (top 4 layers)
- ``pf_et_ns`` / ``pf_et_deep``  ParFlow evaptrans source, window mean (m/h, + = source)
- CLM window means (mm/s or W/m²): see ``CLM_VARS``

CLM hourly files interleave variables per timestep, so a per-variable read
touches every chunk of the file; ``read_clm_219h`` indexes chunk offsets for the
needed variables and reads the file once in offset order.

Usage::

    python analysis/psa_extract.py --list            # jobs + cache status
    python analysis/psa_extract.py --workers 16      # extract missing years
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

CACHE = ROOT / "analysis" / "figures" / "_cache" / "psa"
INTERVAL = 219
STEPS = 40
NS_Z0 = 6
DZ_M = np.array([1.0, 0.5, 0.25, 0.125, 0.05, 0.025, 0.005, 0.003, 0.0015, 0.0005]) * 200.0
CELL_AREA_M2 = 1_000_000.0
DOMAINS = ["potomac2", "wolf2"]
MATCHED = {"potomac2": "pumping_8.64e-7", "wolf2": "pumping_2.49e-6"}
# Catalog ladder (full 10-yr recovery available); used by recovery multi-rate panels.
CATALOG_PUMP_RATES = ("1e-7", "1e-6", "1e-5", "1e-4")
CLM_VARS = [
    "qflx_evap_tot",
    "qflx_tran_veg",
    "qflx_evap_soi",
    "qflx_evap_veg",
    "qflx_infl",
    "eflx_lh_tot",
    "eflx_sh_tot",
    "swe_out",
]


def year_jobs(domain: str) -> list[tuple[str, str, int, Path]]:
    """(ensemble, member, year_index, path_219h) needed by the analysis."""
    from analysis.paper_figures import utils

    def paths(ens, mem):
        try:
            return [Path(p) for p in utils._file_locations(ens, mem, domain, 0, interval=INTERVAL)]
        except FileNotFoundError:
            return []

    jobs = []
    sb = paths("droughts", "short_baseline")
    jobs += [("droughts", "short_baseline", y, sb[y]) for y in range(35, min(55, len(sb)))]
    d10 = paths("droughts", "10_year_drought")
    jobs += [("droughts", "10_year_drought", y, d10[y]) for y in range(40, 55)]
    d50 = paths("droughts", "50_year_drought")
    jobs += [("droughts", "50_year_drought", y, d50[y]) for y in (40, 41, *range(85, 95))]
    pm = paths("10_year_pumping_tests", MATCHED[domain])
    jobs += [("10_year_pumping_tests", MATCHED[domain], y, pm[y]) for y in range(40, 60)]
    for rate in CATALOG_PUMP_RATES:
        mem = f"pumping_{rate}"
        pr = paths("10_year_pumping_tests", mem)
        if len(pr) >= 60:
            jobs += [("10_year_pumping_tests", mem, y, pr[y]) for y in range(40, 60)]
    bl = paths("droughts", "baseline")
    if len(bl) >= 95:
        jobs += [("droughts", "baseline", y, bl[y]) for y in (*range(55, 60), *range(90, 95))]
    return jobs


def cache_path(domain: str, path219: Path) -> Path:
    return CACHE / domain / f"{path219.parent.name}.nc"


def read_clm_219h(clm_path: Path, variables=CLM_VARS) -> dict[str, np.ndarray]:
    """219 h window means of hourly CLM 2-D variables in a single ordered pass."""
    import h5py

    recs = []
    with h5py.File(clm_path, "r") as h:
        ny, nx = h[variables[0]].shape[1:]
        nt = h[variables[0]].shape[0]
        for vi, v in enumerate(variables):
            d = h[v]
            if d.compression is not None or d.dtype != np.float64:
                raise RuntimeError(f"{clm_path}:{v} not raw float64")
            d.id.chunk_iter(
                lambda info, vi=vi: recs.append(
                    (info.byte_offset, info.size, vi, info.chunk_offset[0])
                )
            )
    recs.sort()
    nwin = nt // INTERVAL
    acc = np.zeros((len(variables), nwin, ny, nx), dtype=np.float64)
    block = 256 * 1024**2
    npx = ny * nx
    with open(clm_path, "rb", buffering=0) as fh:
        i = 0
        while i < len(recs):
            start = recs[i][0]
            j = i
            while j < len(recs) and recs[j][0] + recs[j][1] - start <= block:
                j += 1
            end = recs[j - 1][0] + recs[j - 1][1]
            fh.seek(start)
            buf = fh.read(end - start)
            for off, _sz, vi, t in recs[i:j]:
                w = t // INTERVAL
                if w < nwin:
                    acc[vi, w] += np.frombuffer(buf, dtype="<f8", count=npx, offset=off - start).reshape(ny, nx)
            i = j
    acc /= INTERVAL
    return {v: acc[k] for k, v in enumerate(variables)}


def _gain_and_q(pressure, sx, sy, man, mask3):
    from parflow.tools.hydrology import calculate_overland_flow_grid, calculate_overland_fluxes

    nt = pressure.shape[0]
    ny, nx = sx.shape
    gain = np.empty((nt, ny, nx), dtype=np.float32)
    q = np.empty((nt, ny, nx), dtype=np.float32)
    for t in range(nt):
        p = pressure[t]
        qe, qn = calculate_overland_fluxes(p, sx, sy, man, 1000.0, 1000.0, mask=mask3)
        gain[t] = (qe[:, 1:] - qe[:, :-1]) + (qn[1:, :] - qn[:-1, :])
        q[t] = calculate_overland_flow_grid(p, sx, sy, man, 1000.0, 1000.0, mask=mask3)
    return gain, q


def face_weights(sx, sy, man, mask3) -> dict[str, np.ndarray]:
    """Fraction of each cell's outflow leaving through each face.

    Kinematic upwind face fluxes scale with the upwind cell's ponded depth
    times static slope/Manning terms, and face direction is fixed by slope
    sign, so the partition is time-invariant and window-mean face fluxes follow
    from the window-mean outflow grid.
    """
    from parflow.tools.hydrology import calculate_overland_fluxes

    p = np.where(mask3 > 0, 0.0, 0.0)
    p[-1] = np.where(mask3[-1] > 0, 0.01, 0.0)
    qe, qn = calculate_overland_fluxes(p, sx, sy, man, 1000.0, 1000.0, mask=mask3)
    out = {
        "col_plus": np.maximum(0, qe[:, 1:]),
        "col_minus": np.maximum(0, -qe[:, :-1]),
        "row_plus": np.maximum(0, qn[1:, :]),
        "row_minus": np.maximum(0, -qn[:-1, :]),
    }
    tot = sum(out.values())
    return {k: np.where(tot > 0, v / np.maximum(tot, 1e-30), 0.0) for k, v in out.items()}


def gain_from_outflow(q: np.ndarray, w: dict[str, np.ndarray]) -> np.ndarray:
    """Net surface outflow divergence from an outflow grid q (..., y, x)."""
    q = np.nan_to_num(q)
    inflow = np.zeros_like(q)
    inflow[..., :, 1:] += (w["col_plus"] * q)[..., :, :-1]
    inflow[..., :, :-1] += (w["col_minus"] * q)[..., :, 1:]
    inflow[..., 1:, :] += (w["row_plus"] * q)[..., :-1, :]
    inflow[..., :-1, :] += (w["row_minus"] * q)[..., 1:, :]
    return q - inflow


def flowmean_path(domain: str, path219: Path) -> Path:
    return CACHE / domain / f"{path219.parent.name}_qwm.nc"


def extract_flowmean(domain: str, path219: str) -> str:
    """Window-mean outflow grid and local gain from stored ``overland_flow``."""
    import xarray as xr

    path219 = Path(path219)
    out = flowmean_path(domain, path219)
    if out.exists():
        return "skip"
    with xr.open_dataset(path219) as ds:
        if "mean" not in ds["overland_flow"].attrs.get("aggregation", ""):
            raise RuntimeError(f"{path219}: overland_flow is not a window mean")
        mask3 = np.asarray(ds["mask"].values)
        active = np.nanmax(mask3, axis=0) > 0
        sx = np.asarray(ds["slopex"].values).squeeze()
        sy = np.asarray(ds["slopey"].values).squeeze()
        man = np.asarray(ds["mannings"].values).squeeze()
        q = np.asarray(ds["overland_flow"].values, dtype=np.float64)
    w = face_weights(sx, sy, man, mask3)
    gain = gain_from_outflow(q, w)
    data = {
        "q_wm": (("time", "y", "x"), np.where(active[None], q, np.nan).astype(np.float32)),
        "gain_wm": (("time", "y", "x"), np.where(active[None], gain, np.nan).astype(np.float32)),
    }
    tmp = out.with_suffix(".tmp.nc")
    xr.Dataset(data).to_netcdf(tmp, encoding={k: {"zlib": True, "complevel": 3} for k in data})
    os.replace(tmp, out)
    return "done"


def extract_one(domain: str, path219: str) -> str:
    import xarray as xr

    path219 = Path(path219)
    out = cache_path(domain, path219)
    if out.exists():
        return f"skip {out.name[:12]}"
    out.parent.mkdir(parents=True, exist_ok=True)
    with xr.open_dataset(path219) as ds:
        mask3 = np.asarray(ds["mask"].values)
        active = np.nanmax(mask3, axis=0) > 0
        sx = np.asarray(ds["slopex"].values)
        sy = np.asarray(ds["slopey"].values)
        man = np.asarray(ds["mannings"].values)
        if sx.ndim == 3:
            sx, sy = sx[0], sy[0]
        if man.ndim == 3:
            man = man[0]
        pressure = np.asarray(ds["pressure"].values)
        stor = np.asarray(ds["subsurface_storage"].values) / CELL_AREA_M2
        sat = np.asarray(ds["saturation"].values)
        # Catalog 10-yr pumping years 43–49 omit evaptrans in some 219h files.
        et = np.asarray(ds["evaptrans"].values) if "evaptrans" in ds else None
        wtd = np.asarray(ds["wtd"].values)
    nt = pressure.shape[0]
    if nt != STEPS:
        raise RuntimeError(f"{path219}: {nt} steps")
    gain, q = _gain_and_q(pressure, sx, sy, man, mask3)
    dz = DZ_M[None, :, None, None]
    s_ns = np.nansum(stor[:, NS_Z0:], axis=1)
    s_deep = np.nansum(stor[:, :NS_Z0], axis=1)
    w_rz = DZ_M[NS_Z0:][None, :, None, None]
    sat_rz = np.nansum(sat[:, NS_Z0:] * w_rz, axis=1) / DZ_M[NS_Z0:].sum()
    if et is None:
        pf_et_ns = np.zeros((nt,) + active.shape, dtype=np.float64)
        pf_et_deep = np.zeros_like(pf_et_ns)
    else:
        et_d = np.nan_to_num(et) * dz
        pf_et_ns = et_d[:, NS_Z0:].sum(axis=1)
        pf_et_deep = et_d[:, :NS_Z0].sum(axis=1)

    clm_path = path219.parent / "run.out.CLM.00001.nc"
    clm = read_clm_219h(clm_path)

    def da(a):
        a = np.where(active[None], a, np.nan).astype(np.float32)
        return (("time", "y", "x"), a)

    data = {
        "q": da(q),
        "gain": da(gain),
        "s_ns": da(s_ns),
        "s_deep": da(s_deep),
        "wtd": da(wtd),
        "sat_rz": da(sat_rz),
        "pf_et_ns": da(pf_et_ns),
        "pf_et_deep": da(pf_et_deep),
    }
    for v, a in clm.items():
        data[v] = da(a)
    ds_out = xr.Dataset(data, attrs={"source_219h": str(path219)})
    enc = {k: {"zlib": True, "complevel": 3} for k in data}
    tmp = out.with_suffix(".tmp.nc")
    ds_out.to_netcdf(tmp, encoding=enc)
    os.replace(tmp, out)
    return f"done {out.name[:12]}"


def unique_jobs(domains=DOMAINS):
    seen = set()
    jobs = []
    for d in domains:
        for ens, mem, y, p in year_jobs(d):
            key = (d, p.parent.name)
            if key in seen:
                continue
            seen.add(key)
            jobs.append((d, ens, mem, y, p))
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--domains", nargs="*", default=DOMAINS)
    ap.add_argument("--flowmean", action="store_true", help="only write *_qwm.nc window-mean flow caches")
    args = ap.parse_args()
    jobs = unique_jobs(args.domains)
    if args.flowmean:
        for d, ens, mem, y, p in jobs:
            print(d, mem, y, extract_flowmean(d, str(p)), flush=True)
        return
    missing = [j for j in jobs if not cache_path(j[0], j[4]).exists()]
    print(f"{len(jobs)} unique year-files, {len(missing)} missing", flush=True)
    if args.list:
        for d, ens, mem, y, p in jobs:
            print(d, ens, mem, y, p.parent.name[:12], cache_path(d, p).exists())
        return
    # Wolf files are ~3× smaller: interleave so workers stay balanced.
    missing.sort(key=lambda j: (j[0] != "potomac2", j[3]))
    if args.workers <= 1:
        for d, ens, mem, y, p in missing:
            print(d, mem, y, extract_one(d, str(p)), flush=True)
        return
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(extract_one, d, str(p)): (d, mem, y) for d, ens, mem, y, p in missing}
        for f in as_completed(futs):
            d, mem, y = futs[f]
            try:
                print(d, mem, y, f.result(), flush=True)
            except Exception as e:  # keep other years going
                print(d, mem, y, "FAILED", repr(e), flush=True)


if __name__ == "__main__":
    main()
