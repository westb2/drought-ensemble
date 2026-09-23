#!/usr/bin/env python3
"""Outlet cell choice and true 219 h window-mean outlet flow.

* ``analysis_outlet(domain)`` — the config outlet, except Potomac, whose config
  cell (66, 135) is a near-dry side cell (~0.07 mm/yr domain-equivalent). The
  mainstem (63, 129) is the max-baseline-flow cell and the USGS-validation snap.
* ``window_mean_outlet_flow(path, x, y)`` — per-window mean ``overland_flow`` at
  one cell. Some backfilled 219 h files (catalog ``10_year_pumping_tests``
  rates, years 43–49) store end-of-window *snapshots* while tagged as means;
  for those the mean is rebuilt from the sibling ``derived_hourly.nc``.
  Membership comes from ``figures/_data/overland_flow_aggregation_audit.json``
  (``analysis/.tmp_psa/detect_snapshots.py``), with an on-the-fly check for
  files not in the audit.
* ``block_mean(a, stride)`` — downsample a flux series by averaging, never by
  subsampling (subsampled window means / snapshots alias the repeated storm
  calendar).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
AUDIT_JSON = ROOT / "analysis" / "figures" / "_data" / "overland_flow_aggregation_audit.json"
INTERVAL = 219
OUTLET_OVERRIDES = {"potomac2": (63, 129)}  # (x, y)
FLOW_TAG = "wm1"  # bump when outlet-flow semantics change (series cache keys)


def analysis_outlet(domain: str) -> tuple[int, int]:
    if domain in OUTLET_OVERRIDES:
        return OUTLET_OVERRIDES[domain]
    from classes import Domain

    dom = Domain(domain, full_config_file_path_given=False)
    return (dom.outlet_x, dom.outlet_y)


@lru_cache(maxsize=1)
def _audit() -> dict[str, str]:
    if not AUDIT_JSON.exists():
        return {}
    return json.loads(AUDIT_JSON.read_text())["by_path"]


def _resolve(path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _is_snapshot_file(path: Path) -> bool:
    tag = _audit().get(str(path)) or _audit().get(str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else "")
    if tag:
        return tag == "snap"
    import netCDF4
    from parflow.tools.hydrology import calculate_overland_flow_grid

    with netCDF4.Dataset(path) as nc:
        if "pressure" not in nc.variables:
            return False
        mask = np.asarray(nc["mask"][:])
        mask = mask[0] if mask.ndim == 4 else mask
        sx, sy, man = (np.asarray(nc[v][:]) for v in ("slopex", "slopey", "mannings"))
        sx, sy = (a[0] if a.ndim == 3 else a for a in (sx, sy))
        man = man[0] if man.ndim == 3 else man
        t = int(nc["pressure"].shape[0]) // 2
        snap = calculate_overland_flow_grid(np.asarray(nc["pressure"][t]), sx, sy, man, 1000.0, 1000.0, mask=mask)
        st = np.asarray(nc["overland_flow"][t])
    return float(np.nanmax(np.abs(st - snap))) < 1e-4 * max(float(np.nanmax(np.abs(snap))), 1e-9)


def window_mean_outlet_flow(path: Path, x: int, y: int) -> np.ndarray:
    """Per-219 h-window mean outlet flow (m³/h) for one consolidated year file."""
    import netCDF4

    path = _resolve(path)
    if not _is_snapshot_file(path):
        with netCDF4.Dataset(path) as nc:
            return np.asarray(nc["overland_flow"][:, y, x], dtype=np.float64)
    hourly = path.parent / "derived_hourly.nc"
    if not hourly.exists():
        raise RuntimeError(f"{path}: snapshot overland_flow and no derived_hourly.nc to rebuild means")
    with netCDF4.Dataset(hourly) as nc:
        h = np.asarray(nc["overland_flow"][:, y, x], dtype=np.float64)
    n = h.shape[0] // INTERVAL
    return h[: n * INTERVAL].reshape(n, INTERVAL).mean(axis=1)


def block_mean(a: np.ndarray, stride: int) -> np.ndarray:
    """Average consecutive ``stride`` samples (matches ``a[::stride]`` length)."""
    a = np.asarray(a, dtype=np.float64)
    if stride <= 1:
        return a
    n = a.shape[0]
    idx = np.arange(0, n, stride)
    return np.add.reduceat(a, idx) / np.diff(np.append(idx, n))
