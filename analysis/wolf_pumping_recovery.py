#!/usr/bin/env python3
"""Wolf pumping analysis with 10-yr recovery — drought-parity figures by rate.

Uses native ``file_locations_219h.json`` (53 yr: 40 spinup + 3 pump + 10 recovery).
Baseline for recovery anomalies: ``droughts/short_baseline`` (shared spinup).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import Normalize, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, DrawingArea, TextArea, VPacker
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import MultipleLocator

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis.paper_figures import utils  # noqa: E402
from classes import Domain  # noqa: E402

DOMAIN = "wolf2"
DOMAIN_LABEL = "Wolf"
PUMP_ENSEMBLE = "3_year_pumping_tests"
BASE_ENSEMBLE = "droughts"
BASE_MEMBER = "short_baseline"
RATES = [1e-7, 1e-6, 1e-5, 1e-4]
SPINUP_YEARS = 40
PUMP_YEARS = 3
RECOVERY_YEARS = 10
RECOVERY_MAP_YEARS = 5  # drought-parity map columns
INTERVAL = 219
STEPS_PER_YEAR = utils.ONE_YEAR // INTERVAL
STREAM_FLOW_PERCENTILE = 97.0
CELL_AREA_M2 = 1_000_000.0
STREAM_COLOR = "#F0E442"
FOCUS_RATE = 1e-5

from analysis.figure_paths import FIG_DIR, FIG_ROOT, fig_path, resolve_figure  # noqa: E402
SUMMARY_MD = ROOT / "analysis/wolf_pumping_recovery_summary.md"
FIG_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {1e-7: "#E8C39E", 1e-6: "#B86B2B", 1e-5: "#4A2410", 1e-4: "#140A05"}
RATE_LABELS = {r: f"{r:.0e}" for r in RATES}
TEMP_COLOR = "#D4A574"
PERSIST_COLOR = "#5C3317"
LABEL_FS, LEGEND_FS, TITLE_FS = 12, 11, 13
S_SCALE = 1e9
DS_SCALE = 1e6

_dom = Domain(DOMAIN, full_config_file_path_given=False)
OUTLET = (_dom.outlet_x, _dom.outlet_y)


def _resolve_member(rate: float) -> str:
    return {1e-7: "pumping_1e-7", 1e-6: "pumping_1e-6", 1e-5: "pumping_1e-5", 1e-4: "pumping_1e-4"}[rate]


def pumping_paths(rate: float) -> list[Path]:
    files = utils._file_locations(PUMP_ENSEMBLE, _resolve_member(rate), DOMAIN, 0, interval=INTERVAL)
    paths = [Path(p) for p in files]
    if len(paths) < SPINUP_YEARS + PUMP_YEARS + 1:
        raise RuntimeError(f"{_resolve_member(rate)}: expected ≥44 years, got {len(paths)}")
    return paths


def baseline_paths(n_years: int) -> list[Path]:
    files = utils._file_locations(BASE_ENSEMBLE, BASE_MEMBER, DOMAIN, 0, interval=INTERVAL)
    return [Path(p) for p in files[:n_years]]


def read_series(paths: list[Path], start_year: int = 0) -> xr.Dataset:
    ox, oy = OUTLET
    times, storage, outlet = [], [], []
    for year_offset, path in enumerate(paths):
        with xr.open_dataset(path) as ds:
            if "total_storage" in ds:
                stor = np.asarray(ds["total_storage"].values, dtype=np.float64)
            else:
                stor = ds["subsurface_storage"].sum(dim=("x", "y", "z"), skipna=True).values.astype(np.float64)
            flow = np.asarray(ds["overland_flow"].isel(x=ox, y=oy).values, dtype=np.float64)
        n = stor.shape[0]
        times.append(start_year + year_offset + np.arange(n, dtype=np.float64) / STEPS_PER_YEAR)
        storage.append(stor)
        outlet.append(flow)
    return xr.Dataset(
        {"storage": ("time", np.concatenate(storage)), "outlet_flow": ("time", np.concatenate(outlet))},
        coords={"time": np.concatenate(times)},
    )


def recovery_window(ds: xr.Dataset, baseline: xr.Dataset, *, years: int = RECOVERY_MAP_YEARS) -> dict:
    t0 = SPINUP_YEARS + PUMP_YEARS
    t1 = t0 + years
    d_sel = ds.sel(time=slice(t0, t1 - 1e-9))
    b_sel = baseline.sel(time=slice(t0, t1 - 1e-9))
    n = min(d_sel.sizes["time"], b_sel.sizes["time"])
    t = d_sel.time.values[:n] - t0
    Sb = b_sel.storage.values[:n]
    Qb = b_sel.outlet_flow.values[:n]
    return {
        "t": t,
        "S": d_sel.storage.values[:n] / S_SCALE,
        "Q": d_sel.outlet_flow.values[:n],
        "Sb": Sb / S_SCALE,
        "Qb": Qb,
        "dS": (d_sel.storage.values[:n] - Sb) / DS_SCALE,
        "dQ": d_sel.outlet_flow.values[:n] - Qb,
    }


def read_wtd(path: Path, which: str = "last") -> xr.DataArray:
    with xr.open_dataset(path) as ds:
        wtd = ds["wtd"].isel(time=0 if which == "first" else -1)
        mask = ds["mask"]
        active = mask.any(dim="z") > 0 if "z" in mask.dims else mask > 0
        return wtd.where(active).load()


def read_col_storage_m(path: Path, which: str = "last") -> xr.DataArray:
    with xr.open_dataset(path) as ds:
        stor = ds["subsurface_storage"].isel(time=0 if which == "first" else -1).sum(dim="z")
        mask = ds["mask"]
        active = mask.any(dim="z") > 0 if "z" in mask.dims else mask > 0
        return (stor / CELL_AREA_M2).where(active).load()


def stream_mask() -> tuple[np.ndarray, np.ndarray]:
    path = baseline_paths(SPINUP_YEARS)[39]
    with xr.open_dataset(path) as ds:
        flow = ds["overland_flow"].mean(dim="time")
        mask = ds["mask"]
        active = (mask.any(dim="z") > 0).values if "z" in mask.dims else (mask > 0).values
        vals = np.where(active, flow.values, np.nan)
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
    return float(np.degrees(np.arctan2(vt[0, 1], vt[0, 0])))


def _prepare_map(z, streams, active, align_landscape=True):
    z = np.array(z, dtype=float, copy=True)
    streams = np.asarray(streams, dtype=bool)
    active = np.asarray(active, dtype=bool)
    z = np.where(active, z, np.nan)
    if align_landscape and z.shape[0] > z.shape[1]:
        k = int(round(_principal_axis_angle_deg(active) / 90.0)) % 4
        z = np.rot90(z, k=k)
        streams = np.rot90(streams, k=k)
        active = np.rot90(active, k=k)
    rows = np.any(np.isfinite(z), axis=1)
    cols = np.any(np.isfinite(z), axis=0)
    if rows.any() and cols.any():
        r0, r1 = np.where(rows)[0][[0, -1]]
        c0, c1 = np.where(cols)[0][[0, -1]]
        z = z[r0 : r1 + 1, c0 : c1 + 1]
        streams = streams[r0 : r1 + 1, c0 : c1 + 1]
    return z, streams


def _add_stream_key(cbar):
    swatch = DrawingArea(14, 14, 0, 0)
    swatch.add_artist(Rectangle((2, 2), 10, 10, facecolor=STREAM_COLOR, edgecolor="0.15", linewidth=0.8))
    stream_label = TextArea("Stream", textprops=dict(size=15))
    stream_box = VPacker(children=[swatch, stream_label], align="center", pad=0, sep=3)
    cbar.ax.add_artist(
        AnnotationBbox(stream_box, (0.5, 1.06), xycoords="axes fraction", box_alignment=(0.5, 0.0), frameon=False, pad=0.0)
    )


def load_all() -> tuple[dict, dict]:
    n = SPINUP_YEARS + PUMP_YEARS + RECOVERY_YEARS
    print(f"Loading baseline {DOMAIN}/{BASE_MEMBER}…", flush=True)
    baseline = read_series(baseline_paths(n))
    series, paths = {"_baseline": baseline}, {}
    for rate in RATES:
        print(f"Loading {DOMAIN}/{_resolve_member(rate)}…", flush=True)
        pp = pumping_paths(rate)
        paths[rate] = pp
        series[rate] = read_series(pp)
    return series, paths


def wtd_anomaly_triple(paths_rate: list[Path], paths_base: list[Path]) -> dict[str, xr.DataArray]:
    i_start = SPINUP_YEARS + PUMP_YEARS - 1
    i_yr1 = SPINUP_YEARS + PUMP_YEARS
    i_end = SPINUP_YEARS + PUMP_YEARS + RECOVERY_MAP_YEARS - 1
    return {
        "start": read_wtd(paths_rate[i_start]) - read_wtd(paths_base[i_start]),
        "yr1": read_wtd(paths_rate[i_yr1]) - read_wtd(paths_base[i_yr1]),
        "end5": read_wtd(paths_rate[i_end]) - read_wtd(paths_base[i_end]),
    }


def storage_deficit_pair(paths_rate: list[Path], paths_base: list[Path]) -> dict[str, xr.DataArray]:
    i0 = SPINUP_YEARS + PUMP_YEARS - 1
    i1 = SPINUP_YEARS + PUMP_YEARS
    d0, b0 = read_col_storage_m(paths_rate[i0]), read_col_storage_m(paths_base[i0])
    d1, b1 = read_col_storage_m(paths_rate[i1]), read_col_storage_m(paths_base[i1])
    deficit0, deficit1 = b0 - d0, b1 - d1
    return {
        "temporary": xr.apply_ufunc(np.maximum, deficit0 - deficit1, 0.0),
        "persistent": xr.apply_ufunc(np.maximum, deficit1, 0.0),
    }


def fig_recovery_totals(series: dict):
    ylabels = ["Total storage (10⁹ m³)", "Δ storage (10⁶ m³)", "Outlet flow (m³/h)", "Δ outlet flow (m³/h)"]
    fig, axes = plt.subplots(4, 1, figsize=(7, 10), sharex=True, constrained_layout=True)
    bl = series["_baseline"]
    for rate in RATES:
        w = recovery_window(series[rate], bl)
        axes[0].plot(w["t"], w["Sb"], color="0.75", lw=0.9, alpha=0.5)
        axes[2].plot(w["t"], w["Qb"], color="0.75", lw=0.9, alpha=0.5)
        lab = RATE_LABELS[rate]
        axes[0].plot(w["t"], w["S"], color=COLORS[rate], lw=1.5, label=lab)
        axes[1].plot(w["t"], w["dS"], color=COLORS[rate], lw=1.5, label=lab)
        axes[2].plot(w["t"], w["Q"], color=COLORS[rate], lw=1.5, label=lab)
        axes[3].plot(w["t"], w["dQ"], color=COLORS[rate], lw=1.5, label=lab)
    for ax in (axes[1], axes[3]):
        ax.axhline(0, color="k", lw=0.6)
    for ax in axes:
        ax.axvline(0, color="k", ls="--", lw=0.8)
        ax.grid(True, alpha=0.3)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.xaxis.set_major_locator(MultipleLocator(1))
    for ax, label in zip(axes, ylabels):
        ax.set_ylabel(label, fontsize=LABEL_FS)
    fig.supxlabel("Years into recovery (after 3-yr pumping)", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=COLORS[r], lw=1.5, label=RATE_LABELS[r]) for r in RATES]
    handles.append(Line2D([0], [0], color="0.65", lw=1.2, label="baseline"))
    fig.legend(handles=handles, loc="outside upper center", ncol=5, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "wolf_pumping_recovery_totals_and_anomalies.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_recovery_fractional(series: dict):
    fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
    bl = series["_baseline"]
    for rate in RATES:
        w = recovery_window(series[rate], bl, years=RECOVERY_YEARS)
        d0 = w["dS"][0]
        if d0 == 0:
            continue
        ax.plot(w["t"], w["dS"] / d0, color=COLORS[rate], lw=1.5, label=RATE_LABELS[rate])
    ax.axhline(0, color="k", lw=0.6)
    ax.axhline(1.0, color="k", lw=0.6, ls=":")
    ax.axvline(0, color="k", ls="--", lw=0.8)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(MultipleLocator(1))
    ax.set_ylabel("Fraction of initial storage deficit", fontsize=LABEL_FS)
    ax.set_xlabel("Years into recovery", fontsize=LABEL_FS)
    fig.legend(handles=[Line2D([0], [0], color=COLORS[r], lw=1.5, label=RATE_LABELS[r]) for r in RATES],
               loc="outside upper center", ncol=4, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "wolf_pumping_recovery_fractional_storage.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_course(series: dict):
    plot_start = SPINUP_YEARS - 3
    plot_end = SPINUP_YEARS + PUMP_YEARS + RECOVERY_YEARS
    bl = series["_baseline"].sel(time=slice(plot_start, plot_end))
    tb = bl.time.values - SPINUP_YEARS
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True, constrained_layout=True)
    axes[1].plot(tb, bl.storage.values / S_SCALE, color="0.65", lw=1.0, label="baseline")
    for rate in RATES:
        ds = series[rate].sel(time=slice(plot_start, plot_end))
        t = ds.time.values - SPINUP_YEARS
        axes[0].plot(t, ds.outlet_flow.values, color=COLORS[rate], lw=1.3, label=RATE_LABELS[rate])
        axes[1].plot(t, ds.storage.values / S_SCALE, color=COLORS[rate], lw=1.3, label=RATE_LABELS[rate])
    for ax in axes:
        ax.axvline(0, color="k", ls="--", lw=0.9)
        ax.axvline(PUMP_YEARS, color="k", ls=":", lw=0.9)
        ax.axvspan(0, PUMP_YEARS, color="C3", alpha=0.08)
        ax.axvspan(PUMP_YEARS, PUMP_YEARS + RECOVERY_YEARS, color="C0", alpha=0.06)
        ax.grid(True, alpha=0.3)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
    axes[0].set_ylabel("Outlet flow (m³/h)", fontsize=LABEL_FS)
    axes[1].set_ylabel("Total storage (10⁹ m³)", fontsize=LABEL_FS)
    fig.supxlabel("Year (pumping start = 0; blue shade = 10-yr recovery)", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=COLORS[r], lw=1.3, label=RATE_LABELS[r]) for r in RATES]
    handles += [
        Line2D([0], [0], color="0.65", lw=1.0, label="baseline"),
        Patch(facecolor="C3", alpha=0.25, edgecolor="none", label="pumping"),
        Patch(facecolor="C0", alpha=0.2, edgecolor="none", label="recovery"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=6, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "wolf_pumping_course_streamflow_storage.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_during_pumping_totals(series: dict):
    bl = series["_baseline"]
    t0, t1 = SPINUP_YEARS, SPINUP_YEARS + PUMP_YEARS
    fig, axes = plt.subplots(4, 1, figsize=(7, 10), sharex=True, constrained_layout=True)
    for rate in RATES:
        d_sel = series[rate].sel(time=slice(t0, t1 - 1e-9))
        b_sel = bl.sel(time=slice(t0, t1 - 1e-9))
        t = d_sel.time.values - t0
        axes[0].plot(t, b_sel.storage.values / S_SCALE, color="0.75", lw=0.9, alpha=0.5)
        axes[2].plot(t, b_sel.outlet_flow.values, color="0.75", lw=0.9, alpha=0.5)
        axes[0].plot(t, d_sel.storage.values / S_SCALE, color=COLORS[rate], lw=1.5, label=RATE_LABELS[rate])
        axes[1].plot(t, (d_sel.storage.values - b_sel.storage.values) / DS_SCALE, color=COLORS[rate], lw=1.5)
        axes[2].plot(t, d_sel.outlet_flow.values, color=COLORS[rate], lw=1.5)
        axes[3].plot(t, d_sel.outlet_flow.values - b_sel.outlet_flow.values, color=COLORS[rate], lw=1.5)
    for ax in (axes[1], axes[3]):
        ax.axhline(0, color="k", lw=0.6)
    for ax in axes:
        ax.axvspan(0, PUMP_YEARS, color="C3", alpha=0.08)
        ax.grid(True, alpha=0.3)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.xaxis.set_major_locator(MultipleLocator(1))
    for ax, label in zip(axes, ["Total storage (10⁹ m³)", "Δ storage (10⁶ m³)", "Outlet flow (m³/h)", "Δ outlet flow (m³/h)"]):
        ax.set_ylabel(label, fontsize=LABEL_FS)
    fig.supxlabel("Years into pumping", fontsize=LABEL_FS)
    fig.legend(handles=[Line2D([0], [0], color=COLORS[r], lw=1.5, label=RATE_LABELS[r]) for r in RATES],
               loc="outside upper center", ncol=4, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "wolf_pumping_during_totals_and_anomalies.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_wtd_maps(paths: dict, streams, active):
    col_keys = ("start", "yr1", "end5")
    col_titles = {"start": "Recovery start\n(end of pumping)", "yr1": "1 yr\nrecovery", "end5": "5 yr\nrecovery"}
    base = baseline_paths(SPINUP_YEARS + PUMP_YEARS + RECOVERY_MAP_YEARS)
    anoms = {r: wtd_anomaly_triple(paths[r], base) for r in RATES}
    prep, all_vals = {}, []
    align = active.shape[0] > active.shape[1]
    prepared = {}
    for rate in RATES:
        for key in col_keys:
            prepared[(rate, key)] = _prepare_map(anoms[rate][key].values, streams, active, align_landscape=align)
            all_vals.append(prepared[(rate, key)][0][np.isfinite(prepared[(rate, key)][0])])
    z0, _ = prepared[(RATES[0], "start")]
    prep["aspect"] = z0.shape[1] / max(z0.shape[0], 1)
    prep["maps"] = prepared
    vmax = max(float(np.nanpercentile(np.abs(np.concatenate(all_vals)), 98)), 1e-3)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    nrows, ncols = len(RATES), len(col_keys)
    fig = plt.figure(figsize=(2.2 * ncols + 0.8, 2.4 * nrows + 1.0))
    gs = fig.add_gridspec(nrows, ncols, width_ratios=[prep["aspect"]] * ncols, wspace=0.08, hspace=0.12)
    map_axes, im = [], None
    for row, rate in enumerate(RATES):
        for col, key in enumerate(col_keys):
            ax = fig.add_subplot(gs[row, col])
            z, strm = prep["maps"][(rate, key)]
            ny, nx = z.shape
            im = ax.pcolormesh(np.arange(nx + 1), np.arange(ny + 1), z, shading="flat", cmap="RdBu_r", norm=norm)
            sy, sx = np.where(strm)
            if sy.size:
                ax.scatter(sx + 0.5, sy + 0.5, s=6, c=STREAM_COLOR, marker="s", linewidths=0.35, edgecolors="0.15", zorder=3)
            ax.set_aspect("equal")
            ax.set_xticks([]); ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            if col == 0:
                ax.set_ylabel(RATE_LABELS[rate], fontsize=13)
            if row == 0:
                ax.set_title(col_titles[key], fontsize=13)
            map_axes.append(ax)
    fig.subplots_adjust(left=0.10, right=0.88, top=0.92, bottom=0.06)
    fig.text(0.5, 0.97, DOMAIN_LABEL, ha="center", va="top", fontsize=16, fontweight="semibold")
    cbar = fig.colorbar(im, ax=map_axes, fraction=0.03, pad=0.02)
    cbar.set_label("Δ WTD (m)  (+ deeper / drier)", fontsize=14)
    _add_stream_key(cbar)
    out = FIG_DIR / "wolf_pumping_wtd_anomaly_maps.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_temp_persist_maps(paths: dict, streams, active) -> dict:
    deficits = {r: storage_deficit_pair(paths[r], baseline_paths(SPINUP_YEARS + PUMP_YEARS + 1)) for r in RATES}
    col_keys = ("temporary", "persistent")
    col_titles = {"temporary": "Temporary\n(recovered in yr 1)", "persistent": "Persistent\n(after yr 1)"}
    all_vals, prepared = [], {}
    align = active.shape[0] > active.shape[1]
    for rate in RATES:
        for key in col_keys:
            prepared[(rate, key)] = _prepare_map(deficits[rate][key].values, streams, active, align_landscape=align)
            v = prepared[(rate, key)][0]
            all_vals.append(v[np.isfinite(v)])
    vmax = max(float(np.nanpercentile(np.concatenate(all_vals), 98)), 1e-6)
    norm = Normalize(0, vmax)
    nrows, ncols = len(RATES), 2
    z0, _ = prepared[(RATES[0], "temporary")]
    aspect = z0.shape[1] / max(z0.shape[0], 1)
    fig = plt.figure(figsize=(1.9 * ncols * aspect + 1.2, 2.4 * nrows + 1.0))
    gs = fig.add_gridspec(nrows, ncols, width_ratios=[aspect] * ncols, wspace=0.08, hspace=0.12)
    map_axes, im = [], None
    for row, rate in enumerate(RATES):
        for col, key in enumerate(col_keys):
            ax = fig.add_subplot(gs[row, col])
            z, strm = prepared[(rate, key)]
            ny, nx = z.shape
            im = ax.pcolormesh(np.arange(nx + 1), np.arange(ny + 1), z, shading="flat", cmap="YlOrBr", norm=norm)
            sy, sx = np.where(strm)
            if sy.size:
                ax.scatter(sx + 0.5, sy + 0.5, s=6, c=STREAM_COLOR, marker="s", linewidths=0.35, edgecolors="0.15", zorder=3)
            ax.set_aspect("equal")
            ax.set_xticks([]); ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            if col == 0:
                ax.set_ylabel(RATE_LABELS[rate], fontsize=13)
            if row == 0:
                ax.set_title(col_titles[key], fontsize=13)
            map_axes.append(ax)
    fig.subplots_adjust(left=0.10, right=0.88, top=0.92, bottom=0.06)
    fig.text(0.5, 0.97, DOMAIN_LABEL, ha="center", va="top", fontsize=16, fontweight="semibold")
    cbar = fig.colorbar(im, ax=map_axes, fraction=0.03, pad=0.02)
    cbar.set_label("Storage deficit (m water equiv.)", fontsize=14)
    _add_stream_key(cbar)
    out = FIG_DIR / "wolf_pumping_temp_persistent_storage_deficit_maps.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return deficits


def fig_temp_persist_bars(deficits: dict):
    x = np.arange(len(RATES), dtype=float)
    width = 0.36
    temp = [float(np.nansum(deficits[r]["temporary"].values)) * CELL_AREA_M2 / 1e6 for r in RATES]
    pers = [float(np.nansum(deficits[r]["persistent"].values)) * CELL_AREA_M2 / 1e6 for r in RATES]
    fig, ax = plt.subplots(figsize=(8, 4.2), constrained_layout=True)
    ax.bar(x - width / 2, temp, width, color=TEMP_COLOR, edgecolor="0.25", linewidth=0.6, label="Temporary (yr 1)")
    ax.bar(x + width / 2, pers, width, color=PERSIST_COLOR, edgecolor="0.25", linewidth=0.6, label="Persistent")
    ax.set_xticks(x)
    ax.set_xticklabels([RATE_LABELS[r] for r in RATES])
    ax.set_ylabel("Storage deficit (10⁶ m³)", fontsize=LABEL_FS)
    ax.set_xlabel("Pumping rate (m/h domain-average)", fontsize=LABEL_FS)
    ax.set_ylim(bottom=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.legend(loc="outside upper center", ncol=2, frameon=False, fontsize=LEGEND_FS)
    out = FIG_DIR / "wolf_pumping_temp_persistent_deficit_bars.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return temp, pers


def fig_temp_persist_definition(series: dict):
    fig, ax = plt.subplots(figsize=(8.5, 4.0), constrained_layout=True)
    bl = series["_baseline"]
    for rate in RATES:
        w = recovery_window(series[rate], bl)
        lw = 2.2 if rate == FOCUS_RATE else 1.0
        alpha = 1.0 if rate == FOCUS_RATE else 0.35
        ax.plot(w["t"], w["dS"], color=COLORS[rate], lw=lw, alpha=alpha, label=RATE_LABELS[rate])
    w = recovery_window(series[FOCUS_RATE], bl)
    t, dS = w["t"], w["dS"]
    i0, i1 = int(np.argmin(np.abs(t - 0.0))), int(np.argmin(np.abs(t - 1.0)))
    d0, d1 = float(dS[i0]), float(dS[i1])
    ax.axvspan(0.0, 1.0, color=TEMP_COLOR, alpha=0.22, zorder=0)
    t_tail = t[t >= 1.0]
    if t_tail.size:
        ax.fill_between(t_tail, d1, 0.0, color=PERSIST_COLOR, alpha=0.18, zorder=0)
    ax.axhline(0.0, color="0.45", lw=0.7)
    ax.axvline(0.0, color="k", ls="--", lw=0.8)
    ax.set_xlim(-0.15, 5.05)
    ax.set_ylabel(r"$\Delta$ storage ($10^6$ m$^3$)", fontsize=LABEL_FS)
    ax.set_xlabel("Years into recovery", fontsize=LABEL_FS)
    ax.xaxis.set_major_locator(MultipleLocator(1))
    ax.ticklabel_format(axis="y", style="plain", useOffset=False)
    handles = [Line2D([0], [0], color=COLORS[r], lw=2.0 if r == FOCUS_RATE else 1.0, label=RATE_LABELS[r]) for r in RATES]
    handles += [
        Patch(facecolor=TEMP_COLOR, alpha=0.35, edgecolor="none", label="Temporary (yr 1)"),
        Patch(facecolor=PERSIST_COLOR, alpha=0.25, edgecolor="none", label="Persistent"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=3, frameon=False, fontsize=LEGEND_FS)
    out = FIG_DIR / "wolf_pumping_temp_persist_definition.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def write_summary(temp: list, pers: list):
    lines = [
        "# Wolf pumping + 10-yr recovery — summary",
        "",
        f"Domain: **{DOMAIN_LABEL}** · ensemble `{PUMP_ENSEMBLE}` · rates {', '.join(RATE_LABELS[r] for r in RATES)}.",
        "",
        "## Temp vs persistent (recovery yr-1 split, end of pumping → after yr 1)",
        "",
        "| Rate | Temporary (10⁶ m³) | Persistent (10⁶ m³) | f_persist |",
        "|------|------------------|---------------------|-----------|",
    ]
    for r, t, p in zip(RATES, temp, pers):
        tot = t + p
        fp = p / tot if tot > 0 else float("nan")
        lines.append(f"| {RATE_LABELS[r]} | {t:.1f} | {p:.1f} | {fp:.2f} |")
    lines += [
        "",
        "## Figures",
        "",
        "- `wolf_pumping_course_streamflow_storage.png` — full course (pump + 10-yr recovery)",
        "- `wolf_pumping_during_totals_and_anomalies.png` — during pumping by rate",
        "- `wolf_pumping_recovery_totals_and_anomalies.png` — recovery window (5 yr shown in maps)",
        "- `wolf_pumping_recovery_fractional_storage.png` — deficit fraction through 10-yr recovery",
        "- `wolf_pumping_wtd_anomaly_maps.png` — ΔWTD at recovery start / +1 / +5 yr",
        "- `wolf_pumping_temp_persist_definition.png` — temp/persist schematic (focus 1e-5)",
        "- `wolf_pumping_temp_persistent_storage_deficit_maps.png` — spatial temp/persist",
        "- `wolf_pumping_temp_persistent_deficit_bars.png` — domain totals by rate",
        "",
        f"*Generated by `{Path(__file__).name}`.*",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n")
    print("wrote", SUMMARY_MD)


def main():
    series, paths = load_all()
    streams, active = stream_mask()
    fig_course(series)
    fig_during_pumping_totals(series)
    fig_recovery_totals(series)
    fig_recovery_fractional(series)
    fig_wtd_maps(paths, streams, active)
    fig_temp_persist_definition(series)
    deficits = fig_temp_persist_maps(paths, streams, active)
    temp, pers = fig_temp_persist_bars(deficits)
    write_summary(temp, pers)


if __name__ == "__main__":
    main()
