#!/usr/bin/env python3
"""Pumping analogues of the drought recovery figures.

Ensemble design differences vs ``droughts``
-------------------------------------------
``3_year_pumping_tests``: 40 yr average spinup + **3 yr pumping** (no post-pump
recovery years). Members vary by **rate** (``pumping_1e-7`` … ``1e-4``), not
stress duration.

Figure mapping
--------------
| Drought figure                         | Pumping analogue                                      |
|----------------------------------------|-------------------------------------------------------|
| Recovery totals/anomalies by length    | During-pumping totals/anomalies by **rate**           |
| Fractional storage recovery            | Fraction of end-of-pump-yr1 deficit remaining         |
| Drought course (10/50 yr)              | Pumping course (last 3 spinup + 3 pump years)         |
| WTD maps start / +1 yr / +5 yr         | WTD maps end spinup / end pump yr1 / end pump yr3     |
| Temp vs persist (recovery yr1 split)   | Early (end yr1) vs buildup (yr3−yr1) storage deficit  |

Baseline: ``droughts/short_baseline`` (shared spinup hashes). Pumping years
are cached as slim 219 h products under ``analysis/figures/_pumping_219h_cache/``.
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
from parflow.tools.hydrology import calculate_water_table_depth

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis.paper_figures import utils  # noqa: E402
from classes import Domain  # noqa: E402

PUMP_ENSEMBLE = "3_year_pumping_tests"
BASE_ENSEMBLE = "droughts"
DOMAINS = ["potomac2", "wolf2"]
DOMAIN_LABELS = {"potomac2": "Potomac", "wolf2": "Wolf"}
# domain-average extraction rates (m/h), light → dark
RATES = [1e-7, 1e-6, 1e-5, 1e-4]
RATE_LABELS = {r: f"{r:.0e}" for r in RATES}
SPINUP_YEARS = 40
PUMP_YEARS = 3
INTERVAL = 219
STEPS_PER_YEAR = utils.ONE_YEAR // INTERVAL
STREAM_FLOW_PERCENTILE = 97.0
CELL_AREA_M2 = 1_000_000.0
STREAM_COLOR = "#F0E442"
DZ_M = np.array([1.0, 0.5, 0.25, 0.125, 0.05, 0.025, 0.005, 0.003, 0.0015, 0.0005]) * 200.0

FIG_DIR = ROOT / "analysis" / "figures"
CACHE_DIR = FIG_DIR / "_pumping_219h_cache"
FIG_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {
    1e-7: "#E8C39E",
    1e-6: "#B86B2B",
    1e-5: "#4A2410",
    1e-4: "#140A05",
}
EARLY_COLOR = "#D4A574"
BUILDUP_COLOR = "#5C3317"
LABEL_FS, LEGEND_FS, TITLE_FS = 12, 11, 13
S_SCALE = 1e9
DS_SCALE = 1e6


def member_name(rate: float) -> str:
    # match on-disk names: pumping_1e-7, pumping_1e-4, …
    return f"pumping_{rate:.0e}".replace("e-0", "e-")


# Normalize member strings to actual folder names
def _resolve_member(rate: float) -> str:
    candidates = [
        f"pumping_{rate:.0e}",
        f"pumping_{rate:.0e}".replace("e-0", "e-"),
        f"pumping_{rate:g}",
    ]
    # known disk names
    known = {
        1e-7: "pumping_1e-7",
        1e-6: "pumping_1e-6",
        1e-5: "pumping_1e-5",
        1e-4: "pumping_1e-4",
    }
    return known[rate]


OUTLETS = {}
for _d in DOMAINS:
    dom = Domain(_d, full_config_file_path_given=False)
    OUTLETS[_d] = (dom.outlet_x, dom.outlet_y)
    print(_d, "outlet", OUTLETS[_d])


def pumping_hourly_files(domain_name: str, rate: float) -> list[str]:
    meta = (
        ROOT
        / "domains"
        / domain_name
        / "processed_full_runs"
        / PUMP_ENSEMBLE
        / _resolve_member(rate)
        / "file_locations.json"
    )
    return json.loads(meta.read_text())


def baseline_219h_files(domain_name: str) -> list[str]:
    return utils._file_locations(
        BASE_ENSEMBLE, "short_baseline", domain_name, 0, interval=INTERVAL
    )


def cache_path(domain_name: str, year_dir: Path) -> Path:
    return CACHE_DIR / domain_name / f"{year_dir.name}_219h_slim.nc"


def build_slim_219h(domain_name: str, hourly_path: str | Path) -> Path:
    """Write slim 219 h product: total_storage, overland_flow, wtd, column storage."""
    hourly_path = Path(hourly_path)
    year_dir = hourly_path.parent
    out = cache_path(domain_name, year_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return out

    ox, oy = OUTLETS[domain_name]
    print(f"  caching slim 219h {domain_name}/{year_dir.name[:12]}…", flush=True)
    with xr.open_dataset(hourly_path, chunks={"time": INTERVAL}) as ds:
        n = int(ds.sizes["time"])
        assert n == 8760
        mask = ds["mask"]
        if "time" in mask.dims:
            mask = mask.isel(time=0)
        active = mask.any(dim="z") > 0 if "z" in mask.dims else mask > 0

        # snapshots: last of each window
        stor_snap = ds["subsurface_storage"].isel(time=slice(INTERVAL - 1, None, INTERVAL))
        stor_snap = stor_snap.compute()
        total = stor_snap.sum(dim=("z", "y", "x"), skipna=True)
        col = stor_snap.sum(dim="z", skipna=True)

        flow_mean = (
            ds["overland_flow"]
            .coarsen(time=INTERVAL, boundary="exact")
            .mean()
            .compute()
        )

        # WTD from last of each window
        p = ds["pressure"].isel(time=slice(INTERVAL - 1, None, INTERVAL)).compute()
        s = ds["saturation"].isel(time=slice(INTERVAL - 1, None, INTERVAL)).compute()
        wtd_list = []
        for i in range(p.sizes["time"]):
            w = calculate_water_table_depth(
                p.isel(time=i).values, s.isel(time=i).values, DZ_M
            )
            wtd_list.append(w)
        wtd = np.stack(wtd_list, axis=0)
        m2 = active.values
        wtd = np.where(m2, wtd, np.nan)

        times = (np.arange(1, STEPS_PER_YEAR + 1) * INTERVAL).astype(float)
        ds_out = xr.Dataset(
            {
                "total_storage": (("time",), total.values.astype(np.float64)),
                "subsurface_storage_col": (("time", "y", "x"), col.values.astype(np.float64)),
                "overland_flow": (("time", "y", "x"), flow_mean.values.astype(np.float64)),
                "wtd": (("time", "y", "x"), wtd.astype(np.float64)),
                "mask": mask,
                "outlet_flow": (("time",), flow_mean.isel(x=ox, y=oy).values.astype(np.float64)),
            },
            coords={"time": times},
        )
        tmp = out.with_suffix(".tmp.nc")
        ds_out.to_netcdf(tmp)
        tmp.replace(out)
    return out


def ensure_pumping_cache(domain_name: str, rate: float) -> list[Path]:
    """Return 43 year paths: spinup from short_baseline 219h, pump years from slim cache."""
    hourly = pumping_hourly_files(domain_name, rate)
    base = baseline_219h_files(domain_name)
    assert len(hourly) == SPINUP_YEARS + PUMP_YEARS
    paths: list[Path] = []
    for i in range(SPINUP_YEARS):
        # prefer shared baseline 219h (same hash)
        paths.append(Path(base[i]))
    for i in range(SPINUP_YEARS, SPINUP_YEARS + PUMP_YEARS):
        paths.append(build_slim_219h(domain_name, hourly[i]))
    return paths


def read_series_from_paths(domain_name: str, paths: list[Path], start_year: int = 0):
    ox, oy = OUTLETS[domain_name]
    times, storage, outlet = [], [], []
    for year_offset, path in enumerate(paths):
        with xr.open_dataset(path) as ds:
            if "total_storage" in ds:
                stor = np.asarray(ds["total_storage"].values, dtype=np.float64)
            else:
                stor = (
                    ds["subsurface_storage"]
                    .sum(dim=("x", "y", "z"), skipna=True)
                    .values.astype(np.float64)
                )
            if "outlet_flow" in ds:
                flow = np.asarray(ds["outlet_flow"].values, dtype=np.float64)
            else:
                flow = np.asarray(
                    ds["overland_flow"].isel(x=ox, y=oy).values, dtype=np.float64
                )
        n = stor.shape[0]
        times.append(
            start_year
            + year_offset
            + np.arange(n, dtype=np.float64) / STEPS_PER_YEAR
        )
        storage.append(stor)
        outlet.append(flow)
    return xr.Dataset(
        {
            "storage": ("time", np.concatenate(storage)),
            "outlet_flow": ("time", np.concatenate(outlet)),
        },
        coords={"time": np.concatenate(times)},
    )


def pumping_window(ds, baseline, *, from_onset: bool = True):
    """During-pumping window aligned so t=0 is pumping onset."""
    t0 = SPINUP_YEARS
    t1 = SPINUP_YEARS + PUMP_YEARS
    d_sel = ds.sel(time=slice(t0, t1 - 1e-9))
    b_sel = baseline.sel(time=slice(t0, t1 - 1e-9))
    n = min(d_sel.sizes["time"], b_sel.sizes["time"])
    t = d_sel.time.values[:n] - t0
    return {
        "t": t,
        "S": d_sel.storage.values[:n] / S_SCALE,
        "Q": d_sel.outlet_flow.values[:n],
        "Sb": b_sel.storage.values[:n] / S_SCALE,
        "Qb": b_sel.outlet_flow.values[:n],
        "dS": (d_sel.storage.values[:n] - b_sel.storage.values[:n]) / DS_SCALE,
        "dQ": d_sel.outlet_flow.values[:n] - b_sel.outlet_flow.values[:n],
    }


def read_wtd(path: Path, which: str = "last") -> xr.DataArray:
    with xr.open_dataset(path) as ds:
        t_idx = 0 if which == "first" else -1
        wtd = ds["wtd"].isel(time=t_idx)
        mask = ds["mask"]
        if "z" in mask.dims:
            active = mask.any(dim="z") > 0
        else:
            active = mask > 0
        return wtd.where(active).load()


def read_col_storage_m(path: Path, which: str = "last") -> xr.DataArray:
    with xr.open_dataset(path) as ds:
        t_idx = 0 if which == "first" else -1
        if "subsurface_storage_col" in ds:
            stor = ds["subsurface_storage_col"].isel(time=t_idx)
        else:
            stor = ds["subsurface_storage"].isel(time=t_idx).sum(dim="z")
        mask = ds["mask"]
        if "z" in mask.dims:
            active = mask.any(dim="z") > 0
        else:
            active = mask > 0
        return (stor / CELL_AREA_M2).where(active).load()


def stream_mask(domain_name: str):
    path = baseline_219h_files(domain_name)[39]
    with xr.open_dataset(path) as ds:
        flow = ds["overland_flow"].mean(dim="time")
        mask = ds["mask"]
        if "z" in mask.dims:
            active = (mask.any(dim="z") > 0).values
        else:
            active = (mask > 0).values
        vals = np.where(active, flow.values, np.nan)
        thr = np.nanpercentile(vals, STREAM_FLOW_PERCENTILE)
        streams = np.isfinite(vals) & (vals >= thr)
    return streams, active


def _principal_axis_angle_deg(active):
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
    swatch.add_artist(
        Rectangle((2, 2), 10, 10, facecolor=STREAM_COLOR, edgecolor="0.15", linewidth=0.8)
    )
    stream_label = TextArea("Stream", textprops=dict(size=15))
    stream_box = VPacker(children=[swatch, stream_label], align="center", pad=0, sep=3)
    cbar.ax.add_artist(
        AnnotationBbox(
            stream_box,
            (0.5, 1.06),
            xycoords="axes fraction",
            box_alignment=(0.5, 0.0),
            frameon=False,
            pad=0.0,
            annotation_clip=False,
        )
    )


def load_all():
    series = {}
    paths = {}
    for d in DOMAINS:
        series[d] = {}
        paths[d] = {}
        print(f"Loading baseline {d}/short_baseline…", flush=True)
        bpaths = [Path(p) for p in baseline_219h_files(d)[: SPINUP_YEARS + PUMP_YEARS]]
        series[d]["_baseline"] = read_series_from_paths(d, bpaths)
        for rate in RATES:
            print(f"Loading {d}/{_resolve_member(rate)}…", flush=True)
            pp = ensure_pumping_cache(d, rate)
            paths[d][rate] = pp
            series[d][rate] = read_series_from_paths(d, pp)
            print(
                f"  {float(series[d][rate].time.min()):.2f}→{float(series[d][rate].time.max()):.2f}",
                flush=True,
            )
    return series, paths


def fig_totals_and_anomalies(series):
    ylabels = [
        "Total storage (10⁹ m³)",
        "Δ storage (10⁶ m³)",
        "Outlet flow (m³/h)",
        "Δ outlet flow (m³/h)",
    ]
    fig, axes = plt.subplots(4, 2, figsize=(10, 10), sharex="col", constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.04, hspace=0.08, wspace=0.04)
    for col, d in enumerate(DOMAINS):
        bl = series[d]["_baseline"]
        ax_S, ax_dS, ax_Q, ax_dQ = axes[:, col]
        for rate in RATES:
            w = pumping_window(series[d][rate], bl)
            ax_S.plot(w["t"], w["Sb"], color="0.75", lw=0.9, alpha=0.7)
            ax_Q.plot(w["t"], w["Qb"], color="0.75", lw=0.9, alpha=0.7)
            lab = RATE_LABELS[rate]
            ax_S.plot(w["t"], w["S"], color=COLORS[rate], lw=1.5, label=lab)
            ax_Q.plot(w["t"], w["Q"], color=COLORS[rate], lw=1.5, label=lab)
            ax_dS.plot(w["t"], w["dS"], color=COLORS[rate], lw=1.5, label=lab)
            ax_dQ.plot(w["t"], w["dQ"], color=COLORS[rate], lw=1.5, label=lab)
        for ax in (ax_dS, ax_dQ):
            ax.axhline(0, color="k", lw=0.6)
        for ax in axes[:, col]:
            ax.axvline(0, color="k", ls="--", lw=0.8)
            ax.axvspan(0, PUMP_YEARS, color="C3", alpha=0.08)
            ax.grid(True, alpha=0.3)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax.xaxis.set_major_locator(MultipleLocator(1))
        ax_S.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
    for ax, label in zip(axes[:, 0], ylabels):
        ax.set_ylabel(label, fontsize=LABEL_FS)
    fig.supxlabel("Years into pumping", fontsize=LABEL_FS)
    handles = [
        Line2D([0], [0], color=COLORS[r], lw=1.5, label=RATE_LABELS[r]) for r in RATES
    ]
    handles.append(Line2D([0], [0], color="0.65", lw=1.2, label="baseline"))
    handles.append(Patch(facecolor="C3", alpha=0.25, edgecolor="none", label="pumping"))
    fig.legend(handles=handles, loc="outside upper center", ncol=6, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_during_totals_and_anomalies.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_fractional(series):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        bl = series[d]["_baseline"]
        for rate in RATES:
            w = pumping_window(series[d][rate], bl)
            # deficit magnitude; fraction of deficit at end of year 1 remaining
            deficit = -w["dS"]
            # end of year 1 index
            i1 = int(np.searchsorted(w["t"], 1.0, side="right") - 1)
            i1 = max(i1, 0)
            d1 = deficit[i1]
            if d1 == 0:
                continue
            ax.plot(w["t"], deficit / d1, color=COLORS[rate], lw=1.5, label=RATE_LABELS[rate])
        ax.axhline(1.0, color="k", lw=0.6, ls=":")
        ax.axvline(1.0, color="k", lw=0.6, ls="--")
        ax.axvspan(0, PUMP_YEARS, color="C3", alpha=0.08)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        if col == 0:
            ax.set_ylabel("Deficit / (deficit at end of pump yr 1)", fontsize=LABEL_FS)
    fig.supxlabel("Years into pumping", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=COLORS[r], lw=1.5, label=RATE_LABELS[r]) for r in RATES]
    fig.legend(handles=handles, loc="outside upper center", ncol=4, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_by_rate_fractional_storage.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_course(series):
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5), sharex="col", constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.04, hspace=0.08, wspace=0.04)
    plot_start = SPINUP_YEARS - 3
    plot_end = SPINUP_YEARS + PUMP_YEARS
    for col, d in enumerate(DOMAINS):
        bl = series[d]["_baseline"].sel(time=slice(plot_start, plot_end))
        tb = bl.time.values - SPINUP_YEARS
        ax_q, ax_s = axes[0, col], axes[1, col]
        ax_s.plot(tb, bl.storage.values / S_SCALE, color="0.65", lw=1.0, label="baseline")
        for rate in RATES:
            ds = series[d][rate].sel(time=slice(plot_start, plot_end))
            t = ds.time.values - SPINUP_YEARS
            ax_q.plot(t, ds.outlet_flow.values, color=COLORS[rate], lw=1.3, label=RATE_LABELS[rate])
            ax_s.plot(t, ds.storage.values / S_SCALE, color=COLORS[rate], lw=1.3, label=RATE_LABELS[rate])
        for ax in (ax_q, ax_s):
            ax.axvline(0, color="k", ls="--", lw=0.9)
            ax.axvline(PUMP_YEARS, color="k", ls=":", lw=0.9)
            ax.axvspan(0, PUMP_YEARS, color="C3", alpha=0.08)
            ax.grid(True, alpha=0.3)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax_q.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        if col == 0:
            ax_q.set_ylabel("Outlet flow (m³/h)", fontsize=LABEL_FS)
            ax_s.set_ylabel("Total storage (10⁹ m³)", fontsize=LABEL_FS)
    fig.supxlabel("Year (from pumping start)", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=COLORS[r], lw=1.3, label=RATE_LABELS[r]) for r in RATES]
    handles += [
        Line2D([0], [0], color="0.65", lw=1.0, label="baseline"),
        Patch(facecolor="C3", alpha=0.25, edgecolor="none", label="pumping"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=6, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_course_streamflow_storage.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_wtd_maps(paths, landscape):
    col_keys = ("pre", "yr1", "yr3")
    col_titles = {
        "pre": "End of spinup\n(pre-pumping)",
        "yr1": "End pump year 1",
        "yr3": "End pump year 3",
    }
    anoms = {}
    for d in DOMAINS:
        anoms[d] = {}
        bpaths = baseline_219h_files(d)
        for rate in RATES:
            pp = paths[d][rate]
            # pre = year 39 last; yr1 = year 40; yr3 = year 42
            trip = {
                "pre": read_wtd(pp[39]) - read_wtd(Path(bpaths[39])),
                "yr1": read_wtd(pp[40]) - read_wtd(Path(bpaths[40])),
                "yr3": read_wtd(pp[42]) - read_wtd(Path(bpaths[42])),
            }
            anoms[d][rate] = trip
            print(f"WTD {d} {RATE_LABELS[rate]} done", flush=True)

    nrows = len(RATES)
    n_map_cols = len(DOMAINS) * len(col_keys)
    prep = {}
    all_vals = []
    for d in DOMAINS:
        streams, active = landscape[d]
        sample = anoms[d][RATES[0]]["yr3"].values
        align = sample.shape[0] > sample.shape[1]
        prepared = {}
        for rate in RATES:
            for key in col_keys:
                prepared[(rate, key)] = _prepare_map(
                    anoms[d][rate][key].values, streams, active, align_landscape=align
                )
                v = prepared[(rate, key)][0]
                all_vals.append(v[np.isfinite(v)])
        z0, _ = prepared[(RATES[0], "yr3")]
        prep[d] = {"maps": prepared, "aspect": z0.shape[1] / max(z0.shape[0], 1)}

    vmax = float(np.nanpercentile(np.abs(np.concatenate(all_vals)), 98))
    vmax = max(vmax, 1e-3)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    width_ratios = [prep[d]["aspect"] for d in DOMAINS for _ in col_keys]
    fig_h = 2.2 * nrows + 1.2
    fig = plt.figure(figsize=(2.0 * n_map_cols, fig_h))
    gs = fig.add_gridspec(nrows, n_map_cols, width_ratios=width_ratios, wspace=0.08, hspace=0.15)
    map_axes, top_axes, im = [], {}, None
    for row, rate in enumerate(RATES):
        for d_i, d in enumerate(DOMAINS):
            for k_i, key in enumerate(col_keys):
                col = d_i * len(col_keys) + k_i
                ax = fig.add_subplot(gs[row, col])
                z, streams = prep[d]["maps"][(rate, key)]
                ny, nx = z.shape
                im = ax.pcolormesh(
                    np.arange(nx + 1), np.arange(ny + 1), z,
                    shading="flat", cmap="RdBu_r", norm=norm,
                )
                sy, sx = np.where(streams)
                if sy.size:
                    ax.scatter(sx + 0.5, sy + 0.5, s=5, c=STREAM_COLOR, marker="s",
                               linewidths=0.35, edgecolors="0.15", zorder=3)
                ax.set_aspect("equal")
                ax.set_xticks([]); ax.set_yticks([])
                for spine in ax.spines.values():
                    spine.set_visible(False)
                if k_i == 0:
                    ax.set_ylabel(RATE_LABELS[rate], fontsize=13)
                if row == 0:
                    ax.set_title(col_titles[key], fontsize=13)
                    top_axes[(d_i, k_i)] = ax
                map_axes.append(ax)
    fig.subplots_adjust(left=0.06, right=0.90, top=0.88, bottom=0.04)
    for d_i, d in enumerate(DOMAINS):
        pos0 = top_axes[(d_i, 0)].get_position()
        pos1 = top_axes[(d_i, len(col_keys) - 1)].get_position()
        fig.text(0.5 * (pos0.x0 + pos1.x1), 0.93, DOMAIN_LABELS[d],
                 ha="center", va="bottom", fontsize=16, fontweight="semibold")
    cbar = fig.colorbar(im, ax=map_axes, fraction=0.025, pad=0.02)
    cbar.set_label("Δ WTD (m)  (+ deeper / drier)", fontsize=14)
    cbar.ax.tick_params(labelsize=12)
    _add_stream_key(cbar)
    out = FIG_DIR / "pumping_wtd_anomaly_maps.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def early_buildup_pair(domain_name: str, paths_rate: list[Path], bpaths: list[str]):
    """Early = deficit end yr1; buildup = additional by end yr3."""
    d1 = read_col_storage_m(paths_rate[40])
    b1 = read_col_storage_m(Path(bpaths[40]))
    d3 = read_col_storage_m(paths_rate[42])
    b3 = read_col_storage_m(Path(bpaths[42]))
    def1 = b1 - d1
    def3 = b3 - d3
    early = xr.apply_ufunc(np.maximum, def1, 0.0)
    buildup = xr.apply_ufunc(np.maximum, def3 - def1, 0.0)
    return {"early": early, "buildup": buildup, "total": xr.apply_ufunc(np.maximum, def3, 0.0)}


def fig_early_buildup_maps(paths, landscape):
    deficits = {}
    for d in DOMAINS:
        deficits[d] = {}
        bpaths = baseline_219h_files(d)
        for rate in RATES:
            pair = early_buildup_pair(d, paths[d][rate], bpaths)
            deficits[d][rate] = pair
            e = float(np.nansum(pair["early"].values)) * CELL_AREA_M2 / 1e6
            b = float(np.nansum(pair["buildup"].values)) * CELL_AREA_M2 / 1e6
            print(f"{d} {RATE_LABELS[rate]}: early={e:.1f} buildup={b:.1f} ×10⁶ m³")

    col_keys = ("early", "buildup")
    col_titles = {
        "early": "Early deficit\n(end of pump year 1)",
        "buildup": "Buildup\n(additional by end year 3)",
    }
    nrows = len(RATES)
    n_map_cols = len(DOMAINS) * len(col_keys)
    prep = {}
    all_vals = []
    for d in DOMAINS:
        streams, active = landscape[d]
        sample = deficits[d][RATES[0]]["early"].values
        align = sample.shape[0] > sample.shape[1]
        prepared = {}
        for rate in RATES:
            for key in col_keys:
                prepared[(rate, key)] = _prepare_map(
                    deficits[d][rate][key].values, streams, active, align_landscape=align
                )
                v = prepared[(rate, key)][0]
                vv = v[np.isfinite(v)]
                if vv.size:
                    all_vals.append(vv)
        z0, _ = prepared[(RATES[0], "early")]
        prep[d] = {"maps": prepared, "aspect": z0.shape[1] / max(z0.shape[0], 1)}

    vmax = float(np.nanpercentile(np.concatenate(all_vals), 98)) if all_vals else 1.0
    vmax = max(vmax, 1e-6)
    norm = Normalize(0, vmax)
    width_ratios = [prep[d]["aspect"] for d in DOMAINS for _ in col_keys]
    fig = plt.figure(figsize=(1.7 * n_map_cols, 2.2 * nrows + 1.2))
    gs = fig.add_gridspec(nrows, n_map_cols, width_ratios=width_ratios, wspace=0.08, hspace=0.15)
    map_axes, top_axes, im = [], {}, None
    for row, rate in enumerate(RATES):
        for d_i, d in enumerate(DOMAINS):
            for k_i, key in enumerate(col_keys):
                col = d_i * len(col_keys) + k_i
                ax = fig.add_subplot(gs[row, col])
                z, streams = prep[d]["maps"][(rate, key)]
                ny, nx = z.shape
                im = ax.pcolormesh(
                    np.arange(nx + 1), np.arange(ny + 1), z,
                    shading="flat", cmap="YlOrBr", norm=norm,
                )
                sy, sx = np.where(streams)
                if sy.size:
                    ax.scatter(sx + 0.5, sy + 0.5, s=5, c=STREAM_COLOR, marker="s",
                               linewidths=0.35, edgecolors="0.15", zorder=3)
                ax.set_aspect("equal")
                ax.set_xticks([]); ax.set_yticks([])
                for spine in ax.spines.values():
                    spine.set_visible(False)
                if k_i == 0:
                    ax.set_ylabel(RATE_LABELS[rate], fontsize=13)
                if row == 0:
                    ax.set_title(col_titles[key], fontsize=13)
                    top_axes[(d_i, k_i)] = ax
                map_axes.append(ax)
    fig.subplots_adjust(left=0.07, right=0.90, top=0.88, bottom=0.04)
    for d_i, d in enumerate(DOMAINS):
        pos0 = top_axes[(d_i, 0)].get_position()
        pos1 = top_axes[(d_i, len(col_keys) - 1)].get_position()
        fig.text(0.5 * (pos0.x0 + pos1.x1), 0.93, DOMAIN_LABELS[d],
                 ha="center", va="bottom", fontsize=16, fontweight="semibold")
    cbar = fig.colorbar(im, ax=map_axes, fraction=0.025, pad=0.02)
    cbar.set_label("Storage deficit (m water equiv.)", fontsize=14)
    cbar.ax.tick_params(labelsize=12)
    _add_stream_key(cbar)
    out = FIG_DIR / "pumping_early_buildup_storage_deficit_maps.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return deficits


def fig_early_buildup_bars(deficits):
    x = np.arange(len(RATES), dtype=float)
    width = 0.36
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=True, constrained_layout=True)
    bars_e = bars_b = None
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        early = [
            float(np.nansum(deficits[d][r]["early"].values)) * CELL_AREA_M2 / 1e6
            for r in RATES
        ]
        buildup = [
            float(np.nansum(deficits[d][r]["buildup"].values)) * CELL_AREA_M2 / 1e6
            for r in RATES
        ]
        bars_e = ax.bar(x - width / 2, early, width, color=EARLY_COLOR, edgecolor="0.25",
                        linewidth=0.6, label="Early (yr 1)")
        bars_b = ax.bar(x + width / 2, buildup, width, color=BUILDUP_COLOR, edgecolor="0.25",
                        linewidth=0.6, label="Buildup (yr 2–3)")
        ax.set_xticks(x)
        ax.set_xticklabels([RATE_LABELS[r] for r in RATES])
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.set_ylim(bottom=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if col == 0:
            ax.set_ylabel("Storage deficit (10⁶ m³)", fontsize=LABEL_FS)
    fig.supxlabel("Pumping rate (m/h domain-average)", fontsize=LABEL_FS)
    fig.legend(handles=[bars_e, bars_b], labels=["Early (yr 1)", "Buildup (yr 2–3)"],
               loc="outside upper center", ncol=2, frameon=False, fontsize=LEGEND_FS)
    out = FIG_DIR / "pumping_early_buildup_deficit_bars.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def main():
    series, paths = load_all()
    landscape = {d: stream_mask(d) for d in DOMAINS}
    fig_totals_and_anomalies(series)
    fig_fractional(series)
    fig_course(series)
    fig_wtd_maps(paths, landscape)
    deficits = fig_early_buildup_maps(paths, landscape)
    fig_early_buildup_bars(deficits)


if __name__ == "__main__":
    main()
