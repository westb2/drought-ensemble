#!/usr/bin/env python3
"""Stress-only story figures for ``10_year_pumping_tests``.

Produces the drought-story analogues that do not need recovery years:

* ``ten_year_pumping_streamflow_storage_by_rate.png`` — multi-rate Q + S course
* ``ten_year_pumping_streamflow_storage.png`` — focus-rate story course (1e-5)
* ``story_mid_pump_regen_10yr.png`` — near-surface vs deep ΔS at focus rate

Requires 219h products through year 49 (see ``backfill_10yr_pumping_219h.py``).
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis import outlet_flow as OF  # noqa: E402
from analysis import redo_recovery_with_50yr as R  # noqa: E402
from analysis.paper_figures import utils  # noqa: E402
from analysis.shallow_deep_shielding import (  # noqa: E402
    DEEP_COLOR,
    SHALLOW_COLOR,
    SHALLOW_Z0,
)
PUMP_ENSEMBLE = "10_year_pumping_tests"
BASE_ENSEMBLE = "droughts"
BASE_MEMBER = "short_baseline"
DOMAINS = ["potomac2", "wolf2"]
DOMAIN_LABELS = {"potomac2": "Potomac", "wolf2": "Wolf"}
RATES = [1e-7, 1e-6, 1e-5, 1e-4]
FOCUS_RATE = 1e-5
SPINUP_YEARS = 40
PUMP_YEARS = 10
COURSE_SPINUP_YEARS = R.COURSE_SPINUP_YEARS
INTERVAL = 219
STEPS_PER_YEAR = utils.ONE_YEAR // INTERVAL
N_YEARS = SPINUP_YEARS + PUMP_YEARS  # stress-only index length

# Deck purple sequential (same as make_story_figures.STORY_PUMP_COLORS).
STORY_PUMP_COLORS = {
    1e-7: "#DCCCE5",
    1e-6: "#B084CC",
    1e-5: "#7B3294",
    1e-4: "#3C096C",
}
FOCUS_COLOR = STORY_PUMP_COLORS[FOCUS_RATE]
LABEL_FS, LEGEND_FS, TITLE_FS = R.LABEL_FS, R.LEGEND_FS, R.TITLE_FS
S_SCALE = R.S_SCALE
DS_SCALE = R.DS_SCALE
FIG_DIR = R.FIG_DIR
CACHE_DIR = ROOT / "analysis" / ".tmp_figure_cache" / "10yr_pumping_story"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OUTLETS = {_d: OF.analysis_outlet(_d) for _d in DOMAINS}


def _rate_label(rate: float) -> str:
    return f"{rate:.0e}".replace("e-0", "e-")


def _member(rate: float) -> str:
    return f"pumping_{_rate_label(rate)}"


def _paths_219h(ensemble: str, member: str, domain: str, n_years: int) -> list[Path]:
    files = utils._file_locations(ensemble, member, domain, 0, interval=INTERVAL)
    paths = []
    for p in files[:n_years]:
        path = Path(p)
        if path.name.startswith("processed_output_219h") and path.exists():
            paths.append(path)
            continue
        alt = path.parent / f"processed_output_{INTERVAL}h.nc"
        if alt.exists():
            paths.append(alt)
            continue
        raise RuntimeError(f"{domain}/{member}: no 219h for {path.parent.name[:12]}")
    if len(paths) < n_years:
        raise RuntimeError(f"{domain}/{member}: need {n_years} years, got {len(paths)}")
    return paths


def _time_stride() -> int:
    return 4 if R.figure_fidelity() == "draft" else 1


def read_series(domain_name: str, paths: list[Path]) -> xr.Dataset:
    """Outlet Q (window means, block-averaged to the storage stride) + total storage."""
    ox, oy = OUTLETS[domain_name]
    stride = _time_stride()
    tip = paths[-1].parent.name[:16]
    cache = CACHE_DIR / (
        f"series_{domain_name}_{tip}_n{len(paths)}_s{stride}_o{ox}-{oy}_{OF.FLOW_TAG}.npz"
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

    samples_per_year = STEPS_PER_YEAR // stride
    times, storage, outlet = [], [], []
    for year_offset, path in enumerate(paths):
        with xr.open_dataset(path) as ds:
            if "total_storage" in ds:
                stor = np.asarray(ds["total_storage"].values, dtype=np.float64)[::stride]
            else:
                stor = (
                    ds["subsurface_storage"]
                    .sum(dim=("x", "y", "z"), skipna=True)
                    .values.astype(np.float64)[::stride]
                )
        flow = OF.block_mean(OF.window_mean_outlet_flow(path, ox, oy), stride)
        n = stor.shape[0]
        times.append(year_offset + np.arange(n, dtype=np.float64) / samples_per_year)
        storage.append(stor)
        outlet.append(flow)

    t = np.concatenate(times)
    s = np.concatenate(storage)
    q = np.concatenate(outlet)
    np.savez_compressed(cache, time=t, storage=s, outlet_flow=q)
    return xr.Dataset(
        {"storage": ("time", s), "outlet_flow": ("time", q)},
        coords={"time": t},
    )


def load_all(rates: list[float] | None = None) -> dict:
    rates = rates if rates is not None else RATES
    series = {}
    for d in DOMAINS:
        series[d] = {}
        print(f"Loading baseline {d}/{BASE_MEMBER}…", flush=True)
        bpaths = _paths_219h(BASE_ENSEMBLE, BASE_MEMBER, d, N_YEARS)
        series[d]["_baseline"] = read_series(d, bpaths)
        for rate in rates:
            print(f"Loading {d}/{_member(rate)}…", flush=True)
            pp = _paths_219h(PUMP_ENSEMBLE, _member(rate), d, N_YEARS)
            series[d][rate] = read_series(d, pp)
    return series


def _shade_pump_course(ax, t_left: float, t_right: float) -> None:
    """Spinup / pumping only (no recovery). Reuse drought period colors."""
    R.shade_sequence_periods(ax, PUMP_YEARS, t_left, t_right)


def _pump_period_handles(*, include_spinup: bool = True):
    handles = []
    if include_spinup:
        handles.append(
            Patch(
                facecolor=R.PERIOD_SPINUP_FACE,
                alpha=0.35,
                edgecolor="none",
                label="spinup",
            )
        )
    handles.append(
        Patch(
            facecolor=R.PERIOD_DROUGHT_FACE,
            alpha=0.25,
            edgecolor="none",
            label="pumping",
        )
    )
    return handles


def fig_course_by_rate(series: dict):
    """Multi-rate catalog course (stress only)."""
    plot_start = SPINUP_YEARS - COURSE_SPINUP_YEARS
    plot_end = SPINUP_YEARS + PUMP_YEARS
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.9), sharex="col", constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.06, hspace=0.10, wspace=0.06)
    for col, d in enumerate(DOMAINS):
        bl = series[d]["_baseline"].sel(time=slice(plot_start, plot_end))
        tb = bl.time.values - SPINUP_YEARS
        ax_q, ax_s = axes[0, col], axes[1, col]
        ax_s.plot(tb, bl.storage.values / S_SCALE, color="0.65", lw=1.0, zorder=3)
        for rate in RATES:
            ds = series[d][rate].sel(time=slice(plot_start, plot_end))
            t = ds.time.values - SPINUP_YEARS
            ax_q.plot(t, ds.outlet_flow.values, color=STORY_PUMP_COLORS[rate], lw=1.3, zorder=3)
            ax_s.plot(t, ds.storage.values / S_SCALE, color=STORY_PUMP_COLORS[rate], lw=1.3, zorder=3)
        t_left = float(plot_start - SPINUP_YEARS)
        t_right = float(plot_end - SPINUP_YEARS)
        for ax in (ax_q, ax_s):
            _shade_pump_course(ax, t_left, t_right)
            ax.axvline(0, color="k", ls="--", lw=0.9, zorder=2)
            ax.axvline(PUMP_YEARS, color="k", ls=":", lw=0.9, zorder=2)
            ax.grid(True, alpha=0.3)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax.xaxis.set_major_locator(MultipleLocator(2))
            ax.xaxis.set_minor_locator(MultipleLocator(1))
        ax_q.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        if col == 0:
            ax_q.set_ylabel("Outlet flow (m³/h)", fontsize=LABEL_FS)
            ax_s.set_ylabel("Total storage (10⁹ m³)", fontsize=LABEL_FS)
    fig.supxlabel("Year (from pumping start)", fontsize=LABEL_FS)
    handles = [
        Line2D([0], [0], color=STORY_PUMP_COLORS[r], lw=1.3, label=_rate_label(r))
        for r in RATES
    ]
    handles += [
        Line2D([0], [0], color="0.65", lw=1.0, label="baseline"),
        *_pump_period_handles(include_spinup=True),
    ]
    fig.legend(
        handles=handles,
        loc="outside lower center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=6,
        fontsize=LEGEND_FS,
        frameon=False,
    )
    out = FIG_DIR / "ten_year_pumping_streamflow_storage_by_rate.png"
    R.despine_axes(fig)
    fig.savefig(out, dpi=150, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print("wrote", out)


def fig_course_focus(series: dict, rate: float = FOCUS_RATE, outfile: str | None = None):
    """Single-rate story course (drought slide-2 twin)."""
    plot_start = SPINUP_YEARS - COURSE_SPINUP_YEARS
    plot_end = SPINUP_YEARS + PUMP_YEARS
    color = STORY_PUMP_COLORS[rate]
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.9), sharex="col", constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.06, hspace=0.10, wspace=0.06)
    for col, d in enumerate(DOMAINS):
        baseline = series[d]["_baseline"]
        pump = series[d][rate].sel(time=slice(plot_start, plot_end))
        b_max = float(baseline.time.max())
        b_sel = baseline.sel(time=slice(plot_start, min(plot_end, b_max)))
        t = pump.time.values - SPINUP_YEARS
        ax_q, ax_s = axes[0, col], axes[1, col]
        if b_sel.sizes["time"] > 10:
            tb = b_sel.time.values - SPINUP_YEARS
            ax_s.plot(tb, b_sel.storage.values / S_SCALE, color="0.65", lw=1.0, zorder=3)
        ax_q.plot(t, pump.outlet_flow.values, color=color, lw=1.4, zorder=3)
        ax_s.plot(t, pump.storage.values / S_SCALE, color=color, lw=1.4, zorder=3)
        t_left = float(plot_start - SPINUP_YEARS)
        t_right = float(plot_end - SPINUP_YEARS)
        for ax in (ax_q, ax_s):
            _shade_pump_course(ax, t_left, t_right)
            ax.axvline(0, color="k", ls="--", lw=0.9, zorder=2)
            ax.axvline(PUMP_YEARS, color="k", ls=":", lw=0.9, zorder=2)
            ax.grid(True, alpha=0.3)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax.xaxis.set_major_locator(MultipleLocator(2))
            ax.xaxis.set_minor_locator(MultipleLocator(1))
        ax_q.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        if col == 0:
            ax_q.set_ylabel("Outlet flow (m³/h)", fontsize=LABEL_FS)
            ax_s.set_ylabel("Total storage (10⁹ m³)", fontsize=LABEL_FS)
    fig.supxlabel("Year (from pumping start)", fontsize=LABEL_FS)
    handles = [
        Line2D([0], [0], color="0.65", lw=1.0, label="baseline"),
        *_pump_period_handles(include_spinup=True),
    ]
    fig.legend(
        handles=handles,
        loc="outside lower center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=3,
        fontsize=LEGEND_FS,
        frameon=False,
    )
    name = outfile or (
        "ten_year_pumping_streamflow_storage.png"
        if rate == FOCUS_RATE
        else f"ten_year_pumping_streamflow_storage_{_rate_label(rate)}.png"
    )
    out = FIG_DIR / name
    R.despine_axes(fig)
    fig.savefig(out, dpi=150, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print("wrote", out)


def pump_zone_series(domain_name: str, rate: float, *, spinup_years: int = COURSE_SPINUP_YEARS) -> dict:
    """Shallow/deep ΔS from spinup through 10-yr pump (stress only)."""
    stride = _time_stride()
    cache = CACHE_DIR / (
        f"zone_{domain_name}_{_rate_label(rate)}_spin{spinup_years}_s{stride}.npz"
    )
    if cache.exists():
        z = np.load(cache)
        return {"t": z["t"], "shallow": z["shallow"], "deep": z["deep"]}

    pump_paths = _paths_219h(PUMP_ENSEMBLE, _member(rate), domain_name, N_YEARS)
    base_paths = _paths_219h(BASE_ENSEMBLE, BASE_MEMBER, domain_name, N_YEARS)
    t_all, sh_all, de_all = [], [], []
    years = range(SPINUP_YEARS - spinup_years, SPINUP_YEARS + PUMP_YEARS)
    for year in years:
        with xr.open_dataset(pump_paths[year]) as pds, xr.open_dataset(base_paths[year]) as bds:
            p_stor = pds["subsurface_storage"].isel(time=slice(None, None, stride))
            b_stor = bds["subsurface_storage"].isel(time=slice(None, None, stride))
            a = p_stor - b_stor
            sh = a.isel(z=slice(SHALLOW_Z0, None)).sum(dim=("z", "y", "x")).values
            de = a.isel(z=slice(0, SHALLOW_Z0)).sum(dim=("z", "y", "x")).values
        n = sh.shape[0]
        samples_per_year = STEPS_PER_YEAR // stride
        t = (year - SPINUP_YEARS) + np.arange(n, dtype=np.float64) / samples_per_year
        t_all.append(t)
        sh_all.append(sh.astype(np.float64))
        de_all.append(de.astype(np.float64))
    out = {
        "t": np.concatenate(t_all),
        "shallow": np.concatenate(sh_all),
        "deep": np.concatenate(de_all),
    }
    np.savez_compressed(cache, **out)
    return out


def fig_mid_pump_regen_10yr(rate: float = FOCUS_RATE):
    """Near-surface regenerates; deep ratchets — 10-yr pump, focus rate."""
    series = {}
    for d in DOMAINS:
        print(f"Zone series {d} {_rate_label(rate)}…", flush=True)
        series[d] = pump_zone_series(d, rate, spinup_years=COURSE_SPINUP_YEARS)

    fig, axes = plt.subplots(2, 2, figsize=(11.8, 6.3), sharex="col", constrained_layout=True)
    for col, d in enumerate(DOMAINS):
        ser = series[d]
        ax_sh, ax_de = axes[0, col], axes[1, col]
        ax_sh.plot(ser["t"], ser["shallow"] / DS_SCALE, color=SHALLOW_COLOR, lw=1.3, zorder=3)
        ax_de.plot(ser["t"], ser["deep"] / DS_SCALE, color=DEEP_COLOR, lw=1.3, zorder=3)
        t_left = -float(COURSE_SPINUP_YEARS)
        t_right = float(PUMP_YEARS)
        for ax in (ax_sh, ax_de):
            _shade_pump_course(ax, t_left, t_right)
            ax.axvline(0.0, color="k", ls="--", lw=0.9, zorder=2)
            ax.axhline(0.0, color="0.55", lw=0.7, zorder=2)
            ax.xaxis.set_major_locator(MultipleLocator(2))
            ax.xaxis.set_minor_locator(MultipleLocator(1))
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax_sh.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        if col == 0:
            ax_sh.set_ylabel(r"Near-surface $\Delta S$ ($10^6$ m$^3$)", fontsize=LABEL_FS)
            ax_de.set_ylabel(r"Deep $\Delta S$ ($10^6$ m$^3$)", fontsize=LABEL_FS)
        if col == 1:
            axes[0, 1].sharey(axes[0, 0])
            axes[1, 1].sharey(axes[1, 0])

    fig.supxlabel("Year (from pumping start)", fontsize=LABEL_FS)
    handles = [
        Line2D([0], [0], color=SHALLOW_COLOR, lw=1.8, label="near-surface"),
        Line2D([0], [0], color=DEEP_COLOR, lw=1.8, label="deep"),
        *_pump_period_handles(include_spinup=True),
    ]
    fig.legend(
        handles=handles,
        loc="outside lower center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=4,
        fontsize=LEGEND_FS,
        frameon=False,
    )
    out = FIG_DIR / "story_mid_pump_regen_10yr.png"
    R.despine_axes(fig)
    fig.savefig(out, dpi=150, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print("wrote", out)


def main():
    R.log_figure_fidelity()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    series = load_all(RATES)
    fig_course_by_rate(series)
    fig_course_focus(series, FOCUS_RATE)
    fig_mid_pump_regen_10yr(FOCUS_RATE)


if __name__ == "__main__":
    main()
