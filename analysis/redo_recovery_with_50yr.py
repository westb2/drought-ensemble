#!/usr/bin/env python3
"""Regenerate drought recovery figures including 50-year members.

Baseline handling
-----------------
* wolf2: full ``droughts/baseline`` (95 yr, same paths as short_baseline for 0–54)
* potomac2: ``short_baseline`` (55 yr) for timeseries; for sequence years ≥55,
  recovery anomalies remap onto the last 5 average years of short_baseline.
  Spatial WTD/storage at years 89/90/94 use raw-derived snapshots under
  ``processed_full_runs/droughts/baseline/snapshots/`` (long baseline 219h
  not fully condensed for potomac2).

Figure fidelity
---------------
``FIGURE_FIDELITY`` defaults to ``draft`` (every 4th 219 h step, ~36 days)
so iterating on story course plots stays cheap. Series are cached under
``analysis/.tmp_figure_cache/``. Set ``FIGURE_FIDELITY=final`` (or ask for
the high-fidelity / final version) to plot every condensed step.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import deque
from math import erfc, sqrt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import Normalize, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis import outlet_flow as OF  # noqa: E402
from analysis.paper_figures import utils  # noqa: E402
from classes import Domain  # noqa: E402

ENSEMBLE = "droughts"
DOMAINS = ["potomac2", "wolf2"]
DOMAIN_LABELS = {"potomac2": "Potomac", "wolf2": "Wolf"}
DROUGHT_LENGTHS = [1, 3, 10, 50]
MAP_LENGTHS = [1, 3, 10]  # heatmaps omit 50-yr to save space
SPINUP_YEARS = 40
RECOVERY_YEARS = 5
INTERVAL = 219
STEPS_PER_YEAR = utils.ONE_YEAR // INTERVAL
STREAM_FLOW_PERCENTILE = 97.0
CELL_AREA_M2 = 1_000_000.0
STREAM_COLOR = "#F0E442"

# Draft skips 219 h steps for fast iteration; final uses every condensed step.
# Override with FIGURE_FIDELITY=final (env) or when the user asks for the
# high-fidelity / final version of the figures.
FIGURE_FIDELITY = os.environ.get("FIGURE_FIDELITY", "draft").strip().lower()
DRAFT_TIME_STRIDE = 4  # 219 h × 4 ≈ 36 days; 10 points / year
_SERIES_CACHE = ROOT / "analysis" / ".tmp_figure_cache"

from analysis.figure_paths import FIG_DIR, FIG_ROOT, fig_path, resolve_figure  # noqa: E402

# Back-compat alias: absolute figures root (category subdirs live underneath).
FIG_DIR_ROOT = FIG_ROOT
FIG_DIR.mkdir(parents=True, exist_ok=True)


def figure_fidelity() -> str:
    fid = FIGURE_FIDELITY
    if fid not in ("draft", "final"):
        raise ValueError(f"FIGURE_FIDELITY must be 'draft' or 'final', got {fid!r}")
    return fid


def time_stride() -> int:
    return 1 if figure_fidelity() == "final" else DRAFT_TIME_STRIDE


def log_figure_fidelity() -> None:
    print(
        f"FIGURE_FIDELITY={figure_fidelity()} (time stride={time_stride()})",
        flush=True,
    )


def despine_axes(fig) -> None:
    """Hide top and right spines on plot axes; leave colorbars boxed."""
    for ax in fig.axes:
        if ax.get_label() == "<colorbar>":
            continue
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(which="both", top=False, right=False)

COLORS = {
    1: "#E8C39E",
    3: "#B86B2B",
    10: "#4A2410",
    50: "#140A05",
}
TEMP_COLOR = "#D4A574"
PERSIST_COLOR = "#5C3317"
LABEL_FS, LEGEND_FS, TITLE_FS = 12, 11, 13
S_SCALE = 1e9
DS_SCALE = 1e6

# Sequence period backgrounds (story course + mid-drought regen).
# Okabe–Ito orange = spinup (not olive/green: unsafe next to drought red),
# C3 pink = drought, sky blue = recovery.
COURSE_SPINUP_YEARS = 3
PERIOD_SPINUP_FACE = "#E69F00"
PERIOD_DROUGHT_FACE = "C3"
PERIOD_RECOVERY_FACE = "#9ECAE1"
PERIOD_SPINUP_ALPHA = 0.18
PERIOD_DROUGHT_ALPHA = 0.08
PERIOD_RECOVERY_ALPHA = 0.14


def shade_sequence_periods(ax, drought_length: float, t_left: float, t_right: float) -> None:
    """Fill spinup / drought / recovery flush to the axis frame (no white x-margin)."""
    bleed = 1.0
    spans = (
        (-np.inf, 0.0, PERIOD_SPINUP_FACE, PERIOD_SPINUP_ALPHA),
        (0.0, drought_length, PERIOD_DROUGHT_FACE, PERIOD_DROUGHT_ALPHA),
        (drought_length, np.inf, PERIOD_RECOVERY_FACE, PERIOD_RECOVERY_ALPHA),
    )
    for a, b, color, alpha in spans:
        lo = max(a, t_left)
        hi = min(b, t_right)
        if hi <= lo:
            continue
        if lo <= t_left:
            lo = t_left - bleed
        if hi >= t_right:
            hi = t_right + bleed
        ax.axvspan(lo, hi, color=color, alpha=alpha, lw=0, zorder=0)
    ax.set_xlim(t_left, t_right)
    ax.margins(x=0)
    ax.autoscale(enable=False, axis="x")


def sequence_period_legend_handles(*, include_spinup: bool = True, include_recovery: bool = True):
    handles = []
    if include_spinup:
        handles.append(
            Patch(
                facecolor=PERIOD_SPINUP_FACE,
                alpha=0.40,
                edgecolor="none",
                label="spinup",
            )
        )
    handles.append(
        Patch(
            facecolor=PERIOD_DROUGHT_FACE,
            alpha=0.25,
            edgecolor="none",
            label="drought period",
        )
    )
    if include_recovery:
        handles.append(
            Patch(
                facecolor=PERIOD_RECOVERY_FACE,
                alpha=0.35,
                edgecolor="none",
                label="recovery",
            )
        )
    return handles

POTOMAC_SNAP = (
    ROOT
    / "domains/potomac2/processed_full_runs/droughts/baseline/snapshots"
)


def baseline_member(domain_name: str) -> str:
    """Prefer full baseline when a 95-year 219h index exists."""
    bl = (
        ROOT
        / "domains"
        / domain_name
        / "processed_full_runs"
        / ENSEMBLE
        / "baseline"
        / "file_locations_219h.json"
    )
    if bl.exists() and len(json.loads(bl.read_text())) >= 95:
        return "baseline"
    return "short_baseline"


def outlets_for_domains():
    out = {}
    for d in DOMAINS:
        out[d] = OF.analysis_outlet(d)
        print(d, "outlet", out[d], "baseline_member", baseline_member(d))
    return out


OUTLETS = outlets_for_domains()


def read_condensed_series(domain_name, member, start_year=0):
    stride = time_stride()
    cache = (
        _SERIES_CACHE
        / (
            f"condensed_{domain_name}_{member}_y{start_year}_{figure_fidelity()}_s{stride}"
            f"_o{OUTLETS[domain_name][0]}-{OUTLETS[domain_name][1]}_{OF.FLOW_TAG}.npz"
        )
    )
    if cache.exists():
        z = np.load(cache)
        return xr.Dataset(
            {
                "storage": ("time", z["storage"]),
                "outlet_flow": ("time", z["outlet_flow"]),
            },
            coords={"time": z["time"]},
        )
    ox, oy = OUTLETS[domain_name]
    files = utils._file_locations(
        ENSEMBLE, member, domain_name, start_year, interval=INTERVAL
    )
    times, storage, outlet = [], [], []
    for year_offset, path in enumerate(files):
        with xr.open_dataset(path) as ds:
            if "total_storage" in ds:
                stor = np.asarray(ds["total_storage"].values, dtype=np.float64)
            else:
                name = (
                    "subsurface_storage"
                    if "subsurface_storage" in ds
                    else "storage"
                )
                stor = (
                    ds[name]
                    .sum(dim=("x", "y", "z"), skipna=True)
                    .values.astype(np.float64)
                )
        flow = OF.block_mean(OF.window_mean_outlet_flow(path, ox, oy), stride)
        orig_n = stor.shape[0]
        stor = stor[::stride]
        times.append(
            start_year
            + year_offset
            + np.arange(0, orig_n, stride, dtype=np.float64) / STEPS_PER_YEAR
        )
        storage.append(stor)
        outlet.append(flow)
    time = np.concatenate(times)
    storage_a = np.concatenate(storage)
    outlet_a = np.concatenate(outlet)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, time=time, storage=storage_a, outlet_flow=outlet_a)
    return xr.Dataset(
        {
            "storage": ("time", storage_a),
            "outlet_flow": ("time", outlet_a),
        },
        coords={"time": time},
    )


def _potomac_baseline_storage_offset(drought_length: int) -> float:
    """Align remapped short_baseline storage to long-baseline snapshots (m³).

    Potomac ``baseline`` years 90–94 are not fully condensed; recovery anomalies
    reuse short_baseline years 50–54 for the seasonal cycle and add this offset
    so end-of-year-1 storage matches the year-90 snapshot.
    """
    if drought_length <= 10:
        return 0.0
    snap = potomac_snapshot_path(SPINUP_YEARS + drought_length)  # end of recovery yr1
    if snap is None:
        return 0.0
    with xr.open_dataset(snap) as ds:
        snap_s = float(ds["total_storage"].values)
    # short_baseline year corresponding to first recovery year of a 10-yr member
    sb_year = SPINUP_YEARS + 10
    path = condensed_year_path("potomac2", "short_baseline", sb_year)
    with xr.open_dataset(path) as ds:
        sb_s = float(ds["total_storage"].isel(time=-1).values)
    return snap_s - sb_s


def recovery_window(ds, baseline, drought_length, domain_name: str | None = None):
    """Align recovery; if baseline is short, use its last RECOVERY_YEARS.

    Remapped windows must start on the same intra-year phase as the drought
    recovery (integer year boundary). A plain ``slice(b_max-5, b_max)`` can
    pick up the final step of the prior year (e.g. 49.975) and shift the
    seasonal cycle by one 219 h step — that makes Potomac ΔS look jagged.
    """
    t0 = SPINUP_YEARS + drought_length
    t1 = t0 + RECOVERY_YEARS
    d_sel = ds.sel(time=slice(t0, t1 - 1e-9))
    b_max = float(baseline.time.max())
    remapped = t0 > b_max - 1e-6
    if remapped:
        # Last RECOVERY_YEARS complete years on short_baseline, e.g. 50–54 when
        # time runs through 54.975 (years 0..54 inclusive).
        b_last_year = int(np.floor(b_max + 1e-9))
        b_start = b_last_year - RECOVERY_YEARS + 1
        b_sel = baseline.sel(time=slice(b_start, b_last_year + 1 - 1e-9))
    else:
        b_sel = baseline.sel(time=slice(t0, t1 - 1e-9))
    n = min(d_sel.sizes["time"], b_sel.sizes["time"])
    # Guard: intra-year phases must match (same water-year calendar)
    d_phase = np.mod(d_sel.time.values[:n], 1.0)
    b_phase = np.mod(b_sel.time.values[:n], 1.0)
    if n and np.max(np.abs(d_phase - b_phase)) > 1e-6:
        raise RuntimeError(
            f"baseline remap phase mismatch for {domain_name} L={drought_length}: "
            f"drought {d_phase[:3]} vs baseline {b_phase[:3]}"
        )
    t = d_sel.time.values[:n] - t0
    Sb = b_sel.storage.values[:n].copy()
    Qb = b_sel.outlet_flow.values[:n].copy()
    if remapped and domain_name == "potomac2":
        Sb = Sb + _potomac_baseline_storage_offset(drought_length)
    return {
        "t": t,
        "S": d_sel.storage.values[:n] / S_SCALE,
        "Q": d_sel.outlet_flow.values[:n],
        "Sb": Sb / S_SCALE,
        "Qb": Qb,
        "dS": (d_sel.storage.values[:n] - Sb) / DS_SCALE,
        "dQ": d_sel.outlet_flow.values[:n] - Qb,
    }


def condensed_year_path(domain_name, member, year_index):
    files = utils._file_locations(
        ENSEMBLE, member, domain_name, start_year=0, interval=INTERVAL
    )
    return files[year_index]


def potomac_snapshot_path(year_index: int) -> Path | None:
    p = POTOMAC_SNAP / f"year_{year_index:03d}_last.nc"
    return p if p.exists() else None


def read_wtd_snapshot(domain_name, member, year_index, *, which="last"):
    if (
        domain_name == "potomac2"
        and member in ("baseline", "short_baseline")
        and year_index >= 55
    ):
        snap = potomac_snapshot_path(year_index)
        if snap is not None:
            with xr.open_dataset(snap) as ds:
                wtd = ds["wtd"]
                mask = ds["mask"]
                if "z" in mask.dims:
                    active = mask.any(dim="z") > 0
                else:
                    active = mask > 0
                return wtd.where(active).load()
        # fall back to last short_baseline year
        year_index = min(year_index, 54)
        member = "short_baseline"

    path = condensed_year_path(domain_name, member, year_index)
    with xr.open_dataset(path) as ds:
        t_idx = 0 if which == "first" else -1
        wtd = ds["wtd"].isel(time=t_idx)
        mask = ds["mask"]
        if "z" in mask.dims:
            active = mask.any(dim="z") > 0
        else:
            active = mask > 0
        return wtd.where(active).load()


def read_column_storage_snapshot(domain_name, member, year_index, *, which="last"):
    if (
        domain_name == "potomac2"
        and member in ("baseline", "short_baseline")
        and year_index >= 55
    ):
        snap = potomac_snapshot_path(year_index)
        if snap is not None:
            with xr.open_dataset(snap) as ds:
                stor = ds["subsurface_storage"].sum(dim="z")
                mask = ds["mask"]
                if "z" in mask.dims:
                    active = mask.any(dim="z") > 0
                else:
                    active = mask > 0
                return (stor / CELL_AREA_M2).where(active).load()
        year_index = min(year_index, 54)
        member = "short_baseline"

    path = condensed_year_path(domain_name, member, year_index)
    with xr.open_dataset(path) as ds:
        t_idx = 0 if which == "first" else -1
        stor = ds["subsurface_storage"].isel(time=t_idx).sum(dim="z")
        mask = ds["mask"]
        if "z" in mask.dims:
            active = mask.any(dim="z") > 0
        else:
            active = mask > 0
        return (stor / CELL_AREA_M2).where(active).load()


def baseline_name(domain_name: str) -> str:
    return baseline_member(domain_name)


def stream_mask(domain_name: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (streams bool yx, active bool yx) from late-spinup baseline flow."""
    member = baseline_name(domain_name)
    # year 39 always on short/full baseline
    path = condensed_year_path(domain_name, member if member == "baseline" else "short_baseline", 39)
    # short_baseline always has year 39
    path = condensed_year_path(domain_name, "short_baseline", 39)
    with xr.open_dataset(path) as ds:
        flow = ds["overland_flow"].mean(dim="time")
        mask = ds["mask"]
        if "z" in mask.dims:
            active = (mask.any(dim="z") > 0).values
        else:
            active = (mask > 0).values
        vals = flow.values
        vals = np.where(active, vals, np.nan)
        thr = np.nanpercentile(vals, STREAM_FLOW_PERCENTILE)
        streams = np.isfinite(vals) & (vals >= thr)
    return streams, active


def _principal_axis_angle_deg(active: np.ndarray) -> float:
    ys, xs = np.where(active)
    if ys.size < 2:
        return 0.0
    coords = np.column_stack([xs.astype(float), ys.astype(float)])
    coords -= coords.mean(axis=0)
    _, _, vt = np.linalg.svd(coords, full_matrices=False)
    ang = np.degrees(np.arctan2(vt[0, 1], vt[0, 0]))
    return float(ang)


def _rotate_nearest(arr: np.ndarray, angle_deg: float, cval=np.nan) -> np.ndarray:
    """Nearest-neighbor 2D rotation (no scipy); expands canvas to fit."""
    theta = np.deg2rad(angle_deg)
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    ny, nx = arr.shape
    # corner mapping to size output
    corners = np.array(
        [[0, 0], [0, nx - 1], [ny - 1, 0], [ny - 1, nx - 1]], dtype=float
    )
    cy, cx = (ny - 1) / 2.0, (nx - 1) / 2.0
    corners[:, 0] -= cy
    corners[:, 1] -= cx
    rot = np.column_stack(
        [
            corners[:, 0] * cos_t - corners[:, 1] * sin_t,
            corners[:, 0] * sin_t + corners[:, 1] * cos_t,
        ]
    )
    ymin, ymax = rot[:, 0].min(), rot[:, 0].max()
    xmin, xmax = rot[:, 1].min(), rot[:, 1].max()
    out_ny = int(np.ceil(ymax - ymin)) + 1
    out_nx = int(np.ceil(xmax - xmin)) + 1
    oy, ox = -ymin, -xmin

    yy, xx = np.meshgrid(np.arange(out_ny), np.arange(out_nx), indexing="ij")
    # map output → source
    y0 = yy - oy
    x0 = xx - ox
    ys = y0 * cos_t + x0 * sin_t + cy
    xs = -y0 * sin_t + x0 * cos_t + cx
    ysi = np.rint(ys).astype(int)
    xsi = np.rint(xs).astype(int)
    out = np.full((out_ny, out_nx), cval, dtype=float)
    valid = (ysi >= 0) & (ysi < ny) & (xsi >= 0) & (xsi < nx)
    out[valid] = arr[ysi[valid], xsi[valid]]
    return out


_ALIGN_ANGLE_CACHE: dict[tuple, float] = {}


def _best_align_angle(active: np.ndarray) -> float:
    """Angle (deg) maximizing cropped fill of the active mask."""
    key = (active.shape, int(active.sum()), int(active[:, :3].sum()) if active.size else 0)
    if key in _ALIGN_ANGLE_CACHE:
        return _ALIGN_ANGLE_CACHE[key]
    z = np.where(active, 1.0, np.nan)
    best_ang, best_fill = 0.0, -1.0
    for ang in np.linspace(-90.0, 90.0, 61):
        zr = _rotate_nearest(z, float(ang), cval=np.nan)
        act = np.isfinite(zr)
        rows = np.any(act, axis=1)
        cols = np.any(act, axis=0)
        if not (rows.any() and cols.any()):
            continue
        r0, r1 = np.where(rows)[0][[0, -1]]
        c0, c1 = np.where(cols)[0][[0, -1]]
        fill = float(act[r0 : r1 + 1, c0 : c1 + 1].mean())
        if fill > best_fill:
            best_fill, best_ang = fill, float(ang)
    _ALIGN_ANGLE_CACHE[key] = best_ang
    return best_ang


def _prepare_map(z, streams, active, align_landscape=True):
    """Crop to active cells; optionally rotate for a compact landscape layout."""
    z = np.array(z, dtype=float, copy=True)
    streams = np.asarray(streams, dtype=bool)
    active = np.asarray(active, dtype=bool)
    z = np.where(active, z, np.nan)
    if align_landscape:
        ang = _best_align_angle(active)
        z = _rotate_nearest(z, ang, cval=np.nan)
        streams = _rotate_nearest(streams.astype(float), ang, cval=0.0) > 0.5
        rows = np.any(np.isfinite(z), axis=1)
        cols = np.any(np.isfinite(z), axis=0)
        if rows.any() and cols.any():
            r0, r1 = np.where(rows)[0][[0, -1]]
            c0, c1 = np.where(cols)[0][[0, -1]]
            if (r1 - r0) > (c1 - c0):
                z = np.rot90(z, 1)
                streams = np.rot90(streams, 1)
    # crop to valid
    rows = np.any(np.isfinite(z), axis=1)
    cols = np.any(np.isfinite(z), axis=0)
    if rows.any() and cols.any():
        r0, r1 = np.where(rows)[0][[0, -1]]
        c0, c1 = np.where(cols)[0][[0, -1]]
        z = z[r0 : r1 + 1, c0 : c1 + 1]
        streams = streams[r0 : r1 + 1, c0 : c1 + 1]
    return z, streams


def _add_stream_legend_handle():
    return Line2D(
        [0],
        [0],
        marker="s",
        color="none",
        markerfacecolor=STREAM_COLOR,
        markeredgecolor="0.15",
        markersize=8,
        label="Stream",
    )


def _plot_map_grid(
    *,
    prep: dict,
    lengths: list[int],
    col_keys: tuple[str, ...],
    col_titles: dict[str, str],
    norm,
    cmap: str,
    cbar_label: str,
    outfile: str,
    domains: list[str] | None = None,
):
    """Map grid sized for 16:9 slides: tall map rows, labels never overlap.

    Domains stack vertically. Column width follows each domain's aspect so
    equal-aspect maps fill their boxes (no letterboxing). Row labels live in a
    left gutter outside the axes.
    """
    n_len = len(lengths)
    n_keys = len(col_keys)
    domains = list(domains) if domains is not None else list(DOMAINS)

    # Prefer tall maps; axes boxes are sized to each domain aspect so maps fill
    # the cell (no equal-aspect letterboxing). Horizontal room is the buffer.
    map_h = 2.35 if n_keys <= 2 else 1.90
    row_gap = 0.08
    key_gap = 0.18
    band_gap = 0.28
    left_gutter = 0.90
    right_cbar = 1.00
    domain_hdr = 0.32
    col_hdr = 0.40
    bottom_leg = 0.36

    asps = {d: max(float(prep[d]["aspect"]), 0.5) for d in domains}
    # Each domain sizes its own columns; combined figures use the max width
    # so bands share a common column grid.
    max_asp = max(asps[d] for d in domains)
    col_w = map_h * max_asp
    map_area_w = n_keys * col_w + (n_keys - 1) * key_gap

    band_h = domain_hdr + col_hdr + n_len * map_h + (n_len - 1) * row_gap
    fig_w = left_gutter + map_area_w + right_cbar
    fig_h = bottom_leg + len(domains) * band_h + (len(domains) - 1) * band_gap + 0.08
    fig = plt.figure(figsize=(fig_w, fig_h))

    def ax_rect(x_in, y_in, w_in, h_in):
        return [x_in / fig_w, y_in / fig_h, w_in / fig_w, h_in / fig_h]

    im = None
    y_cursor = fig_h - 0.08

    for d_i, domain_name in enumerate(domains):
        # Per-domain map width from its own aspect; center in the shared column slot
        mw = map_h * asps[domain_name]
        x_pad = (col_w - mw) / 2.0

        fig.text(
            (left_gutter + map_area_w / 2) / fig_w,
            (y_cursor - 0.02) / fig_h,
            DOMAIN_LABELS[domain_name],
            ha="center",
            va="top",
            fontsize=14,
            fontweight="semibold",
        )
        maps_top = y_cursor - domain_hdr - col_hdr

        for k_i, key in enumerate(col_keys):
            slot_x = left_gutter + k_i * (col_w + key_gap)
            fig.text(
                (slot_x + col_w / 2) / fig_w,
                (y_cursor - domain_hdr + 0.02) / fig_h,
                col_titles[key],
                ha="center",
                va="top",
                fontsize=10,
                linespacing=1.15,
            )
            for row, L in enumerate(lengths):
                y0 = maps_top - (row + 1) * map_h - row * row_gap
                x0 = slot_x + x_pad
                ax = fig.add_axes(ax_rect(x0, y0, mw, map_h))
                z, streams = prep[domain_name]["maps"][(L, key)]
                ny, nx = z.shape
                im = ax.pcolormesh(
                    np.arange(nx + 1),
                    np.arange(ny + 1),
                    z,
                    shading="flat",
                    cmap=cmap,
                    norm=norm,
                )
                sy, sx = np.where(streams)
                if sy.size:
                    ax.scatter(
                        sx + 0.5,
                        sy + 0.5,
                        s=7,
                        c=STREAM_COLOR,
                        marker="s",
                        linewidths=0.25,
                        edgecolors="0.15",
                        zorder=3,
                    )
                ax.set_aspect("auto")
                ax.set_xlim(0, nx)
                ax.set_ylim(ny, 0)  # row 0 at top, matches array orientation
                ax.set_xticks([])
                ax.set_yticks([])
                for spine in ax.spines.values():
                    spine.set_visible(False)
                if k_i == 0:
                    fig.text(
                        (left_gutter - 0.14) / fig_w,
                        (y0 + map_h / 2) / fig_h,
                        f"{L}-year",
                        ha="right",
                        va="center",
                        fontsize=11,
                    )

        y_cursor = y_cursor - band_h - band_gap

    cax = fig.add_axes(
        ax_rect(fig_w - right_cbar + 0.25, bottom_leg + 0.15, 0.16, fig_h - bottom_leg - 0.55)
    )
    cbar = fig.colorbar(im, cax=cax)
    cbar.set_label(cbar_label, fontsize=11)
    cbar.ax.tick_params(labelsize=9)
    fig.legend(
        handles=[_add_stream_legend_handle()],
        loc="lower center",
        frameon=False,
        fontsize=10,
        bbox_to_anchor=(0.48, 0.015),
    )
    out = FIG_DIR / outfile
    fig.savefig(out, dpi=160, facecolor="white")
    plt.close(fig)
    print("wrote", out)



def load_all_series():
    series = {}
    for domain_name in DOMAINS:
        series[domain_name] = {}
        members = [baseline_name(domain_name), "short_baseline"] + [
            f"{L}_year_drought" for L in DROUGHT_LENGTHS
        ]
        # unique preserve order
        seen = set()
        uniq = []
        for m in members:
            if m not in seen:
                seen.add(m)
                uniq.append(m)
        for member in uniq:
            print(f"Loading {domain_name}/{member}…", flush=True)
            ds = read_condensed_series(domain_name, member)
            series[domain_name][member] = ds
            print(
                f"  {float(ds.time.min()):.2f}→{float(ds.time.max()):.2f} "
                f"({ds.sizes['time']} steps)",
                flush=True,
            )
        # alias short_baseline as plotting baseline if using full baseline
        if baseline_name(domain_name) == "baseline":
            series[domain_name]["_baseline"] = series[domain_name]["baseline"]
        else:
            series[domain_name]["_baseline"] = series[domain_name]["short_baseline"]
    return series


def fig_totals_and_anomalies(series):
    ylabels = [
        "Total storage (10⁹ m³)",
        "Δ storage (10⁶ m³)",
        "Outlet flow (m³/h)",
        "Δ outlet flow (m³/h)",
    ]
    fig, axes = plt.subplots(
        4, 2, figsize=(10, 10), sharex="col", constrained_layout=True
    )
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.04, hspace=0.08, wspace=0.04)

    for col, domain_name in enumerate(DOMAINS):
        baseline = series[domain_name]["_baseline"]
        ax_S, ax_dS, ax_Q, ax_dQ = axes[:, col]
        for L in DROUGHT_LENGTHS:
            w = recovery_window(
                series[domain_name][f"{L}_year_drought"],
                baseline,
                L,
                domain_name=domain_name,
            )
            ax_S.plot(w["t"], w["Sb"], color="0.75", lw=0.9, alpha=0.7)
            ax_Q.plot(w["t"], w["Qb"], color="0.75", lw=0.9, alpha=0.7)
            ax_S.plot(w["t"], w["S"], color=COLORS[L], lw=1.5, label=f"{L}-year")
            ax_Q.plot(w["t"], w["Q"], color=COLORS[L], lw=1.5, label=f"{L}-year")
            ax_dS.plot(w["t"], w["dS"], color=COLORS[L], lw=1.5, label=f"{L}-year")
            ax_dQ.plot(w["t"], w["dQ"], color=COLORS[L], lw=1.5, label=f"{L}-year")
        for ax in (ax_dS, ax_dQ):
            ax.axhline(0, color="k", lw=0.6)
        for ax in axes[:, col]:
            ax.axvline(0, color="k", ls="--", lw=0.8)
            ax.grid(True, alpha=0.3)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax.xaxis.set_major_locator(MultipleLocator(1))
        ax_S.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)

    q_lo, q_hi = axes[2, 0].get_ylim()
    d_lo, d_hi = axes[3, 0].get_ylim()
    axes[3, 0].set_ylim(min(q_lo, d_lo, 0.0), max(q_hi, d_hi))
    for ax, label in zip(axes[:, 0], ylabels):
        ax.set_ylabel(label, fontsize=LABEL_FS)
    fig.supxlabel("Years into recovery", fontsize=LABEL_FS)
    handles = [
        Line2D([0], [0], color=COLORS[L], lw=1.5, label=f"{L}-year")
        for L in DROUGHT_LENGTHS
    ]
    handles.append(Line2D([0], [0], color="0.65", lw=1.2, label="baseline"))
    fig.legend(
        handles=handles,
        loc="outside upper center",
        ncol=5,
        fontsize=LEGEND_FS,
        frameon=False,
    )
    out = FIG_DIR / "drought_recovery_totals_and_anomalies.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_fractional_storage(series):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=False, constrained_layout=True)
    for col, domain_name in enumerate(DOMAINS):
        ax = axes[col]
        baseline = series[domain_name]["_baseline"]
        for L in DROUGHT_LENGTHS:
            w = recovery_window(
                series[domain_name][f"{L}_year_drought"],
                baseline,
                L,
                domain_name=domain_name,
            )
            # deficit relative to start of recovery
            dS = w["dS"]
            d0 = dS[0]
            if d0 == 0:
                continue
            # fraction of initial deficit remaining (dS is drought-baseline, usually neg)
            frac = dS / d0
            ax.plot(w["t"], frac, color=COLORS[L], lw=1.5, label=f"{L}-year")
        ax.axhline(0, color="k", lw=0.6)
        ax.axvline(0, color="k", ls="--", lw=0.8)
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        if col == 0:
            ax.set_ylabel("Fraction of initial storage deficit", fontsize=LABEL_FS)
    fig.supxlabel("Years into recovery", fontsize=LABEL_FS)
    handles = [
        Line2D([0], [0], color=COLORS[L], lw=1.5, label=f"{L}-year")
        for L in DROUGHT_LENGTHS
    ]
    fig.legend(
        handles=handles,
        loc="outside upper center",
        ncol=4,
        fontsize=LEGEND_FS,
        frameon=False,
    )
    out = FIG_DIR / "drought_recovery_by_length_fractional_storage.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_drought_course(series, drought_length: int, outfile: str):
    log_figure_fidelity()
    member = f"{drought_length}_year_drought"
    drought_end = SPINUP_YEARS + drought_length
    plot_end = drought_end + RECOVERY_YEARS
    plot_start = SPINUP_YEARS - COURSE_SPINUP_YEARS
    color = COLORS[drought_length]

    fig, axes = plt.subplots(
        2, 2, figsize=(10, 6.9), sharex="col", constrained_layout=True
    )
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.06, hspace=0.10, wspace=0.06)

    for col, domain_name in enumerate(DOMAINS):
        baseline = series[domain_name]["_baseline"]
        drought = series[domain_name][member].sel(time=slice(plot_start, plot_end))
        # baseline may be shorter than 50yr course — only overlay where available
        b_max = float(baseline.time.max())
        b_sel = baseline.sel(time=slice(plot_start, min(plot_end, b_max)))
        t = drought.time.values - SPINUP_YEARS
        q = drought.outlet_flow.values
        s = drought.storage.values / S_SCALE
        ax_q, ax_s = axes[0, col], axes[1, col]
        if b_sel.sizes["time"] > 10:
            tb = b_sel.time.values - SPINUP_YEARS
            ax_s.plot(
                tb,
                b_sel.storage.values / S_SCALE,
                color="0.65",
                lw=1.0,
                label="baseline",
                zorder=3,
            )
        ax_q.plot(t, q, color=color, lw=1.4, label=f"{drought_length}-year drought", zorder=3)
        ax_s.plot(t, s, color=color, lw=1.4, label=f"{drought_length}-year drought", zorder=3)
        t_left = float(plot_start - SPINUP_YEARS)
        t_right = float(plot_end - SPINUP_YEARS)
        for ax in (ax_q, ax_s):
            shade_sequence_periods(ax, drought_length, t_left, t_right)
            ax.axvline(0, color="k", ls="--", lw=0.9, zorder=2)
            ax.axvline(drought_length, color="k", ls=":", lw=0.9, zorder=2)
            ax.grid(True, alpha=0.3)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax.xaxis.set_major_locator(MultipleLocator(5))
            ax.xaxis.set_minor_locator(MultipleLocator(1))
        ax_q.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        if col == 0:
            ax_q.set_ylabel("Outlet flow (m³/h)", fontsize=LABEL_FS)
            ax_s.set_ylabel("Total storage (10⁹ m³)", fontsize=LABEL_FS)

    fig.supxlabel("Year (from drought start)", fontsize=LABEL_FS)
    # Single drought length: the line color is already the only series, so the
    # legend is just baseline + period fills.
    handles = [
        Line2D([0], [0], color="0.65", lw=1.0, label="baseline"),
        *sequence_period_legend_handles(include_spinup=True, include_recovery=True),
    ]
    fig.legend(
        handles=handles,
        loc="outside lower center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=4,
        fontsize=LEGEND_FS,
        frameon=False,
    )
    out = FIG_DIR / outfile
    despine_axes(fig)
    fig.savefig(out, dpi=150, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print("wrote", out)


def wtd_anomaly_triple(domain_name, drought_length):
    member = f"{drought_length}_year_drought"
    bmem = baseline_name(domain_name)
    start_year = SPINUP_YEARS + drought_length - 1
    yr1_year = SPINUP_YEARS + drought_length
    end_year = SPINUP_YEARS + drought_length + RECOVERY_YEARS - 1
    d_start = read_wtd_snapshot(domain_name, member, start_year, which="last")
    b_start = read_wtd_snapshot(domain_name, bmem, start_year, which="last")
    d_yr1 = read_wtd_snapshot(domain_name, member, yr1_year, which="last")
    b_yr1 = read_wtd_snapshot(domain_name, bmem, yr1_year, which="last")
    d_end = read_wtd_snapshot(domain_name, member, end_year, which="last")
    b_end = read_wtd_snapshot(domain_name, bmem, end_year, which="last")
    return {
        "start": d_start - b_start,
        "yr1": d_yr1 - b_yr1,
        "end5": d_end - b_end,
    }


def storage_deficit_pair(domain_name, drought_length):
    member = f"{drought_length}_year_drought"
    bmem = baseline_name(domain_name)
    start_year = SPINUP_YEARS + drought_length - 1
    yr1_year = SPINUP_YEARS + drought_length
    d0 = read_column_storage_snapshot(domain_name, member, start_year)
    b0 = read_column_storage_snapshot(domain_name, bmem, start_year)
    d1 = read_column_storage_snapshot(domain_name, member, yr1_year)
    b1 = read_column_storage_snapshot(domain_name, bmem, yr1_year)
    deficit0 = b0 - d0
    deficit1 = b1 - d1
    temporary = xr.apply_ufunc(np.maximum, deficit0 - deficit1, 0.0)
    persistent = xr.apply_ufunc(np.maximum, deficit1, 0.0)
    return {"temporary": temporary, "persistent": persistent}


def wtd_deficit_pair(domain_name, drought_length):
    trip = wtd_anomaly_triple(domain_name, drought_length)
    temporary = xr.apply_ufunc(np.maximum, trip["start"] - trip["yr1"], 0.0)
    persistent = xr.apply_ufunc(np.maximum, trip["yr1"], 0.0)
    return {"temporary": temporary, "persistent": persistent}


def fig_wtd_anomaly_maps(landscape):
    col_keys = ("start", "yr1", "end5")
    col_titles = {
        "start": "Recovery start\n(end of drought)",
        "yr1": "1 year\nrecovery",
        "end5": "5 year\nrecovery",
    }
    lengths = MAP_LENGTHS
    wtd_anoms = {}
    for domain_name in DOMAINS:
        wtd_anoms[domain_name] = {}
        for L in lengths:
            print(f"WTD anomalies {domain_name} {L}-yr…", flush=True)
            wtd_anoms[domain_name][L] = wtd_anomaly_triple(domain_name, L)

    prep = {}
    all_vals = []
    for domain_name in DOMAINS:
        streams, active = landscape[domain_name]
        prepared = {}
        for L in lengths:
            for key in col_keys:
                prepared[(L, key)] = _prepare_map(
                    wtd_anoms[domain_name][L][key].values,
                    streams,
                    active,
                    align_landscape=True,
                )
                v = prepared[(L, key)][0]
                all_vals.append(v[np.isfinite(v)])
        z0, _ = prepared[(lengths[0], "start")]
        prep[domain_name] = {"maps": prepared, "aspect": z0.shape[1] / max(z0.shape[0], 1)}

    vmax = float(np.nanpercentile(np.abs(np.concatenate(all_vals)), 98))
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    _plot_map_grid(
        prep=prep,
        lengths=lengths,
        col_keys=col_keys,
        col_titles=col_titles,
        norm=norm,
        cmap="RdBu_r",
        cbar_label="Δ WTD (m)  (+ deeper / drier)",
        outfile="drought_recovery_wtd_anomaly_maps.png",
    )
    for domain_name in DOMAINS:
        _plot_map_grid(
            prep=prep,
            lengths=lengths,
            col_keys=col_keys,
            col_titles=col_titles,
            norm=norm,
            cmap="RdBu_r",
            cbar_label="Δ WTD (m)  (+ deeper / drier)",
            outfile=f"drought_recovery_wtd_anomaly_maps_{domain_name}.png",
            domains=[domain_name],
        )
    return wtd_anoms


def _plot_deficit_maps(deficits, landscape, col_keys, col_titles, cbar_label, outfile):
    lengths = MAP_LENGTHS
    prep = {}
    all_vals = []
    for domain_name in DOMAINS:
        streams, active = landscape[domain_name]
        prepared = {}
        for L in lengths:
            for key in col_keys:
                prepared[(L, key)] = _prepare_map(
                    deficits[domain_name][L][key].values,
                    streams,
                    active,
                    align_landscape=True,
                )
                v = prepared[(L, key)][0]
                vv = v[np.isfinite(v)]
                if vv.size:
                    all_vals.append(vv)
        z0, _ = prepared[(lengths[0], col_keys[0])]
        prep[domain_name] = {"maps": prepared, "aspect": z0.shape[1] / max(z0.shape[0], 1)}

    vmax = float(np.nanpercentile(np.concatenate(all_vals), 98))
    norm = Normalize(vmin=0.0, vmax=vmax)
    _plot_map_grid(
        prep=prep,
        lengths=lengths,
        col_keys=col_keys,
        col_titles=col_titles,
        norm=norm,
        cmap="YlOrBr",
        cbar_label=cbar_label,
        outfile=outfile,
    )
    stem = Path(outfile).stem
    for domain_name in DOMAINS:
        _plot_map_grid(
            prep=prep,
            lengths=lengths,
            col_keys=col_keys,
            col_titles=col_titles,
            norm=norm,
            cmap="YlOrBr",
            cbar_label=cbar_label,
            outfile=f"{stem}_{domain_name}.png",
            domains=[domain_name],
        )


def fig_temp_persist_definition(series, focus_length: int = 10):
    """Annotate two-phase recovery on ΔS timeseries (definition of temp vs persist)."""
    fig, axes = plt.subplots(
        1, 2, figsize=(10.5, 4.0), sharey=False, constrained_layout=True
    )
    annotate_handles = [
        Patch(facecolor=TEMP_COLOR, alpha=0.35, edgecolor="none", label="Temporary (recovered in yr 1)"),
        Patch(facecolor=PERSIST_COLOR, alpha=0.25, edgecolor="none", label="Persistent (still missing after yr 1)"),
    ]

    for col, domain_name in enumerate(DOMAINS):
        ax = axes[col]
        baseline = series[domain_name]["_baseline"]
        # light lines for all lengths; bold for focus
        for L in DROUGHT_LENGTHS:
            w = recovery_window(
                series[domain_name][f"{L}_year_drought"],
                baseline,
                L,
                domain_name=domain_name,
            )
            lw = 2.2 if L == focus_length else 1.0
            alpha = 1.0 if L == focus_length else 0.35
            ax.plot(
                w["t"],
                w["dS"],
                color=COLORS[L],
                lw=lw,
                alpha=alpha,
                label=f"{L}-year",
                zorder=3 if L == focus_length else 2,
            )

        w = recovery_window(
            series[domain_name][f"{focus_length}_year_drought"],
            baseline,
            focus_length,
            domain_name=domain_name,
        )
        t = w["t"]
        dS = w["dS"]
        # end-of-year samples for clean brackets
        i0 = int(np.argmin(np.abs(t - 0.0)))
        i1 = int(np.argmin(np.abs(t - 1.0)))
        d0 = float(dS[i0])
        d1 = float(dS[i1])

        # shade year-1 recovery window
        ax.axvspan(0.0, 1.0, color=TEMP_COLOR, alpha=0.22, zorder=0)
        # persistent: remaining deficit after year 1
        t_tail = t[t >= 1.0]
        if t_tail.size:
            ax.fill_between(
                t_tail,
                d1,
                0.0,
                color=PERSIST_COLOR,
                alpha=0.18,
                zorder=0,
            )

        ax.axhline(0.0, color="0.45", lw=0.7)
        ax.axvline(0.0, color="k", ls="--", lw=0.8)
        ax.axvline(1.0, color="0.35", ls=":", lw=0.9)

        # bracket annotations on focus curve
        x_br = 0.55
        ax.annotate(
            "",
            xy=(x_br, d0),
            xytext=(x_br, d1),
            arrowprops=dict(arrowstyle="<->", color=TEMP_COLOR, lw=1.6),
        )
        ax.text(
            x_br + 0.08,
            0.5 * (d0 + d1),
            "temporary",
            color=TEMP_COLOR,
            fontsize=10,
            va="center",
            fontweight="semibold",
        )
        x_br2 = 1.35
        ax.annotate(
            "",
            xy=(x_br2, d1),
            xytext=(x_br2, 0.0),
            arrowprops=dict(arrowstyle="<->", color=PERSIST_COLOR, lw=1.6),
        )
        ax.text(
            x_br2 + 0.08,
            0.5 * (d1 + 0.0),
            "persistent",
            color=PERSIST_COLOR,
            fontsize=10,
            va="center",
            fontweight="semibold",
        )

        ax.set_xlim(-0.15, 5.05)
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        ax.xaxis.set_minor_locator(MultipleLocator(0.5))
        if col == 0:
            ax.set_ylabel(r"$\Delta$ storage ($10^6$ m$^3$)", fontsize=LABEL_FS)

    axes[1].sharey(axes[0])
    for ax in axes:
        lo, hi = ax.get_ylim()
        ax.set_ylim(min(lo, 0.0), max(hi, 0.0))
    fig.supxlabel("Years into recovery", fontsize=LABEL_FS)
    length_handles = [
        Line2D([0], [0], color=COLORS[L], lw=2.0 if L == focus_length else 1.0,
               alpha=1.0 if L == focus_length else 0.45, label=f"{L}-year")
        for L in DROUGHT_LENGTHS
    ]
    fig.legend(
        handles=length_handles + annotate_handles,
        loc="outside upper center",
        ncol=3,
        frameon=False,
        fontsize=LEGEND_FS,
    )
    out = FIG_DIR / "drought_recovery_temp_persist_definition.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_temp_persist_storage(landscape):
    storage_deficits = {}
    for domain_name in DOMAINS:
        storage_deficits[domain_name] = {}
        for L in DROUGHT_LENGTHS:
            print(f"storage deficits {domain_name} {L}-yr…", flush=True)
            pair = storage_deficit_pair(domain_name, L)
            storage_deficits[domain_name][L] = pair
            tvals = pair["temporary"].values
            pvals = pair["persistent"].values
            tvals = tvals[np.isfinite(tvals)]
            pvals = pvals[np.isfinite(pvals)]
            print(
                f"  temp Σ={np.nansum(tvals)*CELL_AREA_M2/1e6:.1f}  "
                f"persist Σ={np.nansum(pvals)*CELL_AREA_M2/1e6:.1f} ×10⁶ m³"
            )
    _plot_deficit_maps(
        storage_deficits,
        landscape,
        ("temporary", "persistent"),
        {
            "temporary": "Temporary\n(recovered in year 1)",
            "persistent": "Persistent\n(remaining after year 1)",
        },
        "Storage deficit (m water equiv.)",
        "drought_recovery_temp_persistent_storage_deficit_maps.png",
    )
    return storage_deficits


def fig_temp_persist_wtd(landscape):
    wtd_deficits = {}
    for domain_name in DOMAINS:
        wtd_deficits[domain_name] = {}
        for L in DROUGHT_LENGTHS:
            print(f"WTD deficits {domain_name} {L}-yr…", flush=True)
            wtd_deficits[domain_name][L] = wtd_deficit_pair(domain_name, L)
    _plot_deficit_maps(
        wtd_deficits,
        landscape,
        ("temporary", "persistent"),
        {
            "temporary": "Temporary\n(recovered in year 1)",
            "persistent": "Persistent\n(remaining after year 1)",
        },
        "WTD deficit (m, deeper)",
        "drought_recovery_temp_persistent_wtd_deficit_maps.png",
    )
    return wtd_deficits


def fig_temp_persist_bars(storage_deficits):
    totals = {d: {"temporary": [], "persistent": []} for d in DOMAINS}
    for domain_name in DOMAINS:
        for L in DROUGHT_LENGTHS:
            temp = storage_deficits[domain_name][L]["temporary"]
            pers = storage_deficits[domain_name][L]["persistent"]
            t_sum = float(np.nansum(temp.values)) * CELL_AREA_M2 / 1e6
            p_sum = float(np.nansum(pers.values)) * CELL_AREA_M2 / 1e6
            totals[domain_name]["temporary"].append(t_sum)
            totals[domain_name]["persistent"].append(p_sum)
            print(f"{domain_name} {L}-yr: temp={t_sum:.1f}  persist={p_sum:.1f}")

    x = np.arange(len(DROUGHT_LENGTHS), dtype=float)
    width = 0.36
    fig, axes = plt.subplots(
        1, 2, figsize=(10.5, 4.2), sharey=True, constrained_layout=True
    )
    bars_t = bars_p = None
    for col, domain_name in enumerate(DOMAINS):
        ax = axes[col]
        bars_t = ax.bar(
            x - width / 2,
            totals[domain_name]["temporary"],
            width,
            color=TEMP_COLOR,
            edgecolor="0.25",
            linewidth=0.6,
            label="Temporary",
        )
        bars_p = ax.bar(
            x + width / 2,
            totals[domain_name]["persistent"],
            width,
            color=PERSIST_COLOR,
            edgecolor="0.25",
            linewidth=0.6,
            label="Persistent",
        )
        ax.set_xticks(x)
        ax.set_xticklabels([f"{L}-year" for L in DROUGHT_LENGTHS])
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.set_ylim(bottom=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if col == 0:
            ax.set_ylabel("Storage deficit (10⁶ m³)", fontsize=LABEL_FS)
    fig.supxlabel("Drought length", fontsize=LABEL_FS)
    fig.legend(
        handles=[bars_t, bars_p],
        labels=["Temporary", "Persistent"],
        loc="outside upper center",
        ncol=2,
        frameon=False,
        fontsize=LEGEND_FS,
    )
    out = FIG_DIR / "drought_recovery_temp_persistent_deficit_bars.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return totals


def fig_spike_corrected_bars(series, storage_deficits):
    """Project slow branch to t=0 to isolate fast spike (domain totals)."""
    rows = []
    corrected = {d: {"temporary": [], "persistent": [], "spike": []} for d in DOMAINS}
    for domain_name in DOMAINS:
        baseline = series[domain_name]["_baseline"]
        for L in DROUGHT_LENGTHS:
            w = recovery_window(
                series[domain_name][f"{L}_year_drought"],
                baseline,
                L,
                domain_name=domain_name,
            )
            # storage deficit magnitude (baseline - drought) = -dS when dS is drought-baseline
            deficit = -w["dS"]  # 10⁶ m³
            t = w["t"]
            # breakpoint search in (0.2, 1.5) yr maximizing piecewise linear R²
            best = None
            for tb in np.linspace(0.25, 1.5, 26):
                early = t <= tb
                late = t >= tb
                if early.sum() < 3 or late.sum() < 5:
                    continue
                # fit late linear, early linear
                coef_l = np.polyfit(t[late], deficit[late], 1)
                coef_e = np.polyfit(t[early], deficit[early], 1)
                pred = np.empty_like(deficit)
                pred[late] = np.polyval(coef_l, t[late])
                pred[early] = np.polyval(coef_e, t[early])
                ss_res = np.sum((deficit - pred) ** 2)
                ss_tot = np.sum((deficit - deficit.mean()) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot > 0 else -np.inf
                if best is None or r2 > best[0]:
                    best = (r2, tb, coef_l, coef_e)
            r2, tb, coef_l, coef_e = best
            slow_at_0 = float(np.polyval(coef_l, 0.0))
            total_at_0 = float(deficit[0])
            spike = max(total_at_0 - slow_at_0, 0.0)
            # map-based persistent after yr1
            pers = float(np.nansum(storage_deficits[domain_name][L]["persistent"].values))
            pers *= CELL_AREA_M2 / 1e6
            temp_map = float(np.nansum(storage_deficits[domain_name][L]["temporary"].values))
            temp_map *= CELL_AREA_M2 / 1e6
            corrected[domain_name]["spike"].append(spike)
            corrected[domain_name]["persistent"].append(pers)
            corrected[domain_name]["temporary"].append(temp_map)
            rows.append(
                {
                    "domain": domain_name,
                    "L": L,
                    "tb_yr": tb,
                    "r2": r2,
                    "spike_1e6m3": spike,
                    "slow_at_0_1e6m3": slow_at_0,
                    "map_temp_1e6m3": temp_map,
                    "map_persist_1e6m3": pers,
                }
            )
            print(
                f"{domain_name} {L}-yr spike={spike:.1f} slow0={slow_at_0:.1f} "
                f"map_temp={temp_map:.1f} persist={pers:.1f} tb={tb:.2f}"
            )

    csv_path = FIG_DIR / "drought_recovery_temp_spike_correction.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("wrote", csv_path)

    # bars: spike vs persistent
    x = np.arange(len(DROUGHT_LENGTHS), dtype=float)
    width = 0.36
    fig, axes = plt.subplots(
        1, 2, figsize=(10.5, 4.2), sharey=True, constrained_layout=True
    )
    for col, domain_name in enumerate(DOMAINS):
        ax = axes[col]
        bars_t = ax.bar(
            x - width / 2,
            corrected[domain_name]["spike"],
            width,
            color=TEMP_COLOR,
            edgecolor="0.25",
            linewidth=0.6,
            label="Fast spike",
        )
        bars_p = ax.bar(
            x + width / 2,
            corrected[domain_name]["persistent"],
            width,
            color=PERSIST_COLOR,
            edgecolor="0.25",
            linewidth=0.6,
            label="Persistent (after yr 1)",
        )
        ax.set_xticks(x)
        ax.set_xticklabels([f"{L}-year" for L in DROUGHT_LENGTHS])
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        ax.set_ylim(bottom=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if col == 0:
            ax.set_ylabel("Storage deficit (10⁶ m³)", fontsize=LABEL_FS)
    fig.supxlabel("Drought length", fontsize=LABEL_FS)
    fig.legend(
        handles=[bars_t, bars_p],
        labels=["Fast spike", "Persistent (after yr 1)"],
        loc="outside upper center",
        ncol=2,
        frameon=False,
        fontsize=LEGEND_FS,
    )
    for name in (
        "drought_recovery_temp_persistent_deficit_bars_corrected.png",
        "drought_recovery_temp_persistent_deficit_bars_spike.png",
    ):
        out = FIG_DIR / name
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print("wrote", out)
    plt.close(fig)


def main():
    series = load_all_series()
    landscape = {d: stream_mask(d) for d in DOMAINS}

    fig_totals_and_anomalies(series)
    fig_fractional_storage(series)
    fig_temp_persist_definition(series, focus_length=10)
    fig_drought_course(series, 10, "ten_year_drought_streamflow_storage.png")
    fig_drought_course(series, 50, "fifty_year_drought_streamflow_storage.png")

    fig_wtd_anomaly_maps(landscape)
    storage_deficits = fig_temp_persist_storage(landscape)
    fig_temp_persist_wtd(landscape)
    fig_temp_persist_bars(storage_deficits)
    fig_spike_corrected_bars(series, storage_deficits)

    # write a small machine-readable totals sidecar for the summary
    summary = {"drought_lengths": DROUGHT_LENGTHS, "domains": {}}
    for d in DOMAINS:
        summary["domains"][d] = {}
        for L in DROUGHT_LENGTHS:
            temp = storage_deficits[d][L]["temporary"].values
            pers = storage_deficits[d][L]["persistent"].values
            summary["domains"][d][str(L)] = {
                "temp_1e6m3": float(np.nansum(temp[np.isfinite(temp)]))
                * CELL_AREA_M2
                / 1e6,
                "persist_1e6m3": float(np.nansum(pers[np.isfinite(pers)]))
                * CELL_AREA_M2
                / 1e6,
            }
    out_json = FIG_DIR / "drought_recovery_50yr_totals.json"
    out_json.write_text(json.dumps(summary, indent=2))
    print("wrote", out_json)


if __name__ == "__main__":
    main()
