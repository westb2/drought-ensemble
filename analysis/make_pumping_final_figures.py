#!/usr/bin/env python3
"""Condensed pumping story figures → ``figures/pumping_final/``.

Pumping-only set: **never** plot domain-matched rates here. Every panel uses
the catalog rate ladder ``1e-7`` / ``1e-6`` / ``1e-5`` (purple palette).
Drought vs matched contrasts live in ``make_comparison_figures.py`` →
``figures/comparison/``.

Reproduce::

    conda activate /glade/work/bwest/conda-envs/droughts
    cd /glade/derecho/scratch/bwest/drought-ensemble
    # optional: FIGURE_FIDELITY=final
    python analysis/make_pumping_final_figures.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

os.environ.setdefault("PUMPING_STRESS_YEARS", "10")

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis import make_10yr_pumping_story_figures as M10  # noqa: E402
from analysis import make_story_figures as MSF  # noqa: E402
from analysis import pumping_recovery_timeseries as PT  # noqa: E402
from analysis import redo_recovery_with_50yr as R  # noqa: E402
from analysis.figure_paths import FIG_DIR, reload_categories  # noqa: E402
from analysis.redo_pumping_recovery_analogues import read_wtd  # noqa: E402
from analysis.shallow_deep_shielding import SHALLOW_Z0  # noqa: E402

DOMAINS = ["potomac2", "wolf2"]
DOMAIN_LABELS = {"potomac2": "Potomac", "wolf2": "Wolf"}

FOCUS_RATE = 1e-6
CATALOG_RATES = [1e-7, 1e-6, 1e-5]

SPINUP = 40
PUMP_YEARS = 10
RECOVERY_YEARS = 5
COURSE_SPINUP = R.COURSE_SPINUP_YEARS
N_YEARS = SPINUP + PUMP_YEARS + RECOVERY_YEARS

_RATE_LABELS = {
    1e-7: "1e-7",
    5e-7: "5e-7",
    8.64e-7: "8.64e-7",
    1e-6: "1e-6",
    2e-6: "2e-6",
    2.49e-6: "2.49e-6",
    3e-6: "3e-6",
    5e-6: "5e-6",
    1e-5: "1e-5",
    1e-4: "1e-4",
}


def _rate_label(rate: float) -> str:
    for k, v in _RATE_LABELS.items():
        if abs(k - rate) / k < 1e-6:
            return v
    s = f"{rate:.2e}".replace("e-0", "e-").replace("e+0", "e+")
    return s.rstrip("0").rstrip(".") if "." in s.split("e")[0] else s


def _member(rate: float) -> str:
    return f"pumping_{_rate_label(rate)}"


M10._rate_label = _rate_label
M10._member = _member

STORY_PUMP_COLORS = {
    1e-7: "#DCCCE5",
    5e-7: "#C9B0D9",
    8.64e-7: "#9B6BB5",
    1e-6: "#B084CC",
    2e-6: "#9560B0",
    2.49e-6: "#7B3294",
    1e-5: "#5A1F7A",
    1e-4: "#3C096C",
}
FOCUS_COLOR = STORY_PUMP_COLORS[FOCUS_RATE]
STORY_PUMP_TEMP = MSF.STORY_PUMP_TEMP
STORY_PUMP_PERSIST = MSF.STORY_PUMP_PERSIST
LABEL_FS, LEGEND_FS, TITLE_FS = R.LABEL_FS, R.LEGEND_FS, R.TITLE_FS
S_SCALE, DS_SCALE = R.S_SCALE, R.DS_SCALE

PT.PUMP_ENSEMBLE = "10_year_pumping_tests"
PT.PUMP_YEARS = PUMP_YEARS
PT.RECOVERY_YEARS = RECOVERY_YEARS
PT.N_YEARS = N_YEARS
PT.FOCUS_RATE = FOCUS_RATE
PT.RATES = CATALOG_RATES
PT.RATE_LABELS = {r: _rate_label(r) for r in CATALOG_RATES}
PT._resolve_member = _member


M10.N_YEARS = N_YEARS
M10.PUMP_YEARS = PUMP_YEARS
M10.RATES = CATALOG_RATES
M10.FOCUS_RATE = FOCUS_RATE
M10.STORY_PUMP_COLORS = STORY_PUMP_COLORS


def _rate_color(rate: float) -> str:
    for k, v in STORY_PUMP_COLORS.items():
        if abs(k - rate) / max(k, 1e-30) < 1e-6:
            return v
    return FOCUS_COLOR


def _period_handles(*, include_recovery: bool = True):
    h = [
        Patch(facecolor=R.PERIOD_SPINUP_FACE, alpha=0.35, edgecolor="none", label="spinup"),
        Patch(facecolor=R.PERIOD_DROUGHT_FACE, alpha=0.25, edgecolor="none", label="pumping"),
    ]
    if include_recovery:
        h.append(
            Patch(
                facecolor=R.PERIOD_RECOVERY_FACE,
                alpha=0.35,
                edgecolor="none",
                label="recovery",
            )
        )
    return h


def _shade(ax, t_left: float, t_right: float) -> None:
    R.shade_sequence_periods(ax, PUMP_YEARS, t_left, t_right)


def load_series(rates: list[float]) -> dict:
    series: dict = {}
    for d in DOMAINS:
        series[d] = {}
        print(f"Loading baseline {d}…", flush=True)
        bpaths = M10._paths_219h(M10.BASE_ENSEMBLE, M10.BASE_MEMBER, d, N_YEARS)
        series[d]["_baseline"] = M10.read_series(d, bpaths)
        for rate in rates:
            print(f"Loading {d}/{_member(rate)}…", flush=True)
            pp = M10._paths_219h(M10.PUMP_ENSEMBLE, _member(rate), d, N_YEARS)
            series[d][rate] = M10.read_series(d, pp)
    return series



def fig_course_focus(series: dict) -> Path:
    """Q/S course: all catalog rates (drought-twin basename)."""
    return fig_course_by_rate(
        series, outfile="ten_year_pumping_streamflow_storage.png"
    )


def fig_course_by_rate(
    series: dict, *, outfile: str = "ten_year_pumping_streamflow_storage_by_rate.png"
) -> Path:
    """Multi-rate course: catalog rates only (no matched)."""
    plot_start = SPINUP - COURSE_SPINUP
    plot_end = SPINUP + PUMP_YEARS + RECOVERY_YEARS
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.9), sharex="col", constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.06, hspace=0.10, wspace=0.06)

    for col, d in enumerate(DOMAINS):
        bl = series[d]["_baseline"].sel(
            time=slice(plot_start, min(plot_end, float(series[d]["_baseline"].time.max())))
        )
        tb = bl.time.values - SPINUP
        ax_q, ax_s = axes[0, col], axes[1, col]
        ax_s.plot(tb, bl.storage.values / S_SCALE, color="0.65", lw=1.0, zorder=2)
        for rate in CATALOG_RATES:
            ds = series[d][rate].sel(time=slice(plot_start, plot_end))
            t = ds.time.values - SPINUP
            ax_q.plot(t, ds.outlet_flow.values, color=_rate_color(rate), lw=1.5)
            ax_s.plot(t, ds.storage.values / S_SCALE, color=_rate_color(rate), lw=1.5)
        t_left = float(plot_start - SPINUP)
        t_right = float(plot_end - SPINUP)
        for ax in (ax_q, ax_s):
            _shade(ax, t_left, t_right)
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
        Line2D([0], [0], color=_rate_color(r), lw=1.5, label=_rate_label(r))
        for r in CATALOG_RATES
    ]
    handles += [
        Line2D([0], [0], color="0.65", lw=1.0, label="baseline"),
        *_period_handles(),
    ]
    fig.legend(
        handles=handles,
        loc="outside lower center",
        bbox_to_anchor=(0.5, -0.10),
        ncol=6,
        fontsize=LEGEND_FS,
        frameon=False,
    )
    out = FIG_DIR / outfile
    R.despine_axes(fig)
    fig.savefig(out, dpi=150, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print("wrote", out)
    return out


def pump_zone_series(domain_name: str, rate: float) -> dict:
    stride = M10._time_stride()
    cache = M10.CACHE_DIR / (
        f"zone_{domain_name}_{_rate_label(rate)}"
        f"_spin{COURSE_SPINUP}_rec{RECOVERY_YEARS}_s{stride}.npz"
    )
    if cache.exists():
        z = np.load(cache)
        return {"t": z["t"], "shallow": z["shallow"], "deep": z["deep"]}

    pump_paths = M10._paths_219h(M10.PUMP_ENSEMBLE, _member(rate), domain_name, N_YEARS)
    base_paths = M10._paths_219h(M10.BASE_ENSEMBLE, M10.BASE_MEMBER, domain_name, N_YEARS)
    t_all, sh_all, de_all = [], [], []
    years = range(SPINUP - COURSE_SPINUP, SPINUP + PUMP_YEARS + RECOVERY_YEARS)
    for year in years:
        with xr.open_dataset(pump_paths[year]) as pds, xr.open_dataset(base_paths[year]) as bds:
            p_stor = pds["subsurface_storage"].isel(time=slice(None, None, stride))
            b_stor = bds["subsurface_storage"].isel(time=slice(None, None, stride))
            a = p_stor - b_stor
            sh = a.isel(z=slice(SHALLOW_Z0, None)).sum(dim=("z", "y", "x")).values
            de = a.isel(z=slice(0, SHALLOW_Z0)).sum(dim=("z", "y", "x")).values
        n = sh.shape[0]
        samples_per_year = M10.STEPS_PER_YEAR // stride
        t = (year - SPINUP) + np.arange(n, dtype=np.float64) / samples_per_year
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


def fig_mid_pump_regen(series_zones: dict) -> Path:
    """Near-surface / deep ΔS for all catalog rates."""
    fig, axes = plt.subplots(2, 2, figsize=(11.8, 6.3), sharex="col", constrained_layout=True)
    for col, d in enumerate(DOMAINS):
        ax_sh, ax_de = axes[0, col], axes[1, col]
        for rate in CATALOG_RATES:
            ser = series_zones[d][rate]
            color = _rate_color(rate)
            ax_sh.plot(ser["t"], ser["shallow"] / DS_SCALE, color=color, lw=1.5)
            ax_de.plot(ser["t"], ser["deep"] / DS_SCALE, color=color, lw=1.5)
        t_left = -float(COURSE_SPINUP)
        t_right = float(PUMP_YEARS + RECOVERY_YEARS)
        for ax in (ax_sh, ax_de):
            _shade(ax, t_left, t_right)
            ax.axvline(0.0, color="k", ls="--", lw=0.9, zorder=2)
            ax.axvline(PUMP_YEARS, color="k", ls=":", lw=0.9, zorder=2)
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
        Line2D([0], [0], color=_rate_color(r), lw=1.5, label=_rate_label(r))
        for r in CATALOG_RATES
    ] + _period_handles()
    fig.legend(
        handles=handles,
        loc="outside lower center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=6,
        fontsize=LEGEND_FS,
        frameon=False,
    )
    out = FIG_DIR / "story_mid_pump_regen_10yr.png"
    R.despine_axes(fig)
    fig.savefig(out, dpi=150, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print("wrote", out)
    return out


def _recovery_window(ds, baseline, *, years: int = RECOVERY_YEARS) -> dict:
    t0 = SPINUP + PUMP_YEARS
    t1 = t0 + years
    d_sel = ds.sel(time=slice(t0, t1 - 1e-9))
    b_max = float(baseline.time.max())
    if t0 > b_max - 1e-6:
        b_last = int(np.floor(b_max + 1e-9))
        b_start = b_last - years + 1
        b_sel = baseline.sel(time=slice(b_start, b_last + 1 - 1e-9))
    else:
        b_sel = baseline.sel(time=slice(t0, t1 - 1e-9))
    n = min(d_sel.sizes["time"], b_sel.sizes["time"])
    t = d_sel.time.values[:n] - t0
    Sb = b_sel.storage.values[:n]
    Qb = b_sel.outlet_flow.values[:n]
    return {
        "t": t,
        "dS": (d_sel.storage.values[:n] - Sb) / DS_SCALE,
        "Q": d_sel.outlet_flow.values[:n],
        "Qb": Qb,
    }


def _annual_flow_pct(w: dict, *, recovery_years: int = RECOVERY_YEARS):
    t, Q, Qb = w["t"], w["Q"], w["Qb"]
    yrs, pct = [], []
    for y in range(recovery_years):
        m = (t >= y) & (t < y + 1)
        if not np.any(m):
            continue
        qb = float(np.mean(Qb[m]))
        if qb == 0:
            continue
        yrs.append(y + 0.5)
        pct.append(100.0 * (float(np.mean(Q[m])) - qb) / qb)
    return np.asarray(yrs), np.asarray(pct)


RATE_MARKERS = {1e-7: "o", 1e-6: "s", 1e-5: "^"}


def fig_recovery_flow_anomaly(series: dict) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 3.8), constrained_layout=True)
    fig.set_constrained_layout_pads(w_pad=0.04, h_pad=0.06)
    all_pct = []
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        for rate in CATALOG_RATES:
            w = _recovery_window(series[d][rate], series[d]["_baseline"])
            yr, pct = _annual_flow_pct(w)
            all_pct.append(pct)
            ax.plot(
                yr, pct, color=_rate_color(rate), lw=1.5,
                marker=RATE_MARKERS[rate], ms=6,
            )
        ax.axhline(0.0, color="k", lw=0.8)
        ax.axvline(0.0, color="k", ls="--", lw=0.8)
        ax.axvline(1.0, color="0.35", ls=":", lw=0.9)
        ax.set_xlim(-0.15, RECOVERY_YEARS + 0.15)
        ax.grid(True, alpha=0.3)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)

    pct = np.concatenate([p for p in all_pct if len(p)])
    pad = 0.08 * (pct.max() - pct.min() + 1e-6)
    for ax in axes:
        ax.set_ylim(pct.min() - pad, pct.max() + pad)
    axes[0].set_ylabel(
        "Outlet flow anomaly,\nyearly mean (% of baseline)", fontsize=LABEL_FS
    )
    axes[1].sharey(axes[0])
    axes[1].tick_params(labelleft=False)
    fig.supxlabel("Years into recovery (after 10-yr pumping)", fontsize=LABEL_FS)
    handles = [
        Line2D(
            [0], [0], color=_rate_color(r), lw=1.5,
            marker=RATE_MARKERS[r], ms=6, label=_rate_label(r),
        )
        for r in CATALOG_RATES
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=3, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "ten_year_pumping_recovery_flow_anomaly.png"
    R.despine_axes(fig)
    fig.savefig(out, dpi=150, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    print("wrote", out)
    return out


def _wtd_triple(domain_name: str, rate: float) -> dict:
    paths = M10._paths_219h(M10.PUMP_ENSEMBLE, _member(rate), domain_name, N_YEARS)
    bpaths = M10._paths_219h(M10.BASE_ENSEMBLE, M10.BASE_MEMBER, domain_name, N_YEARS)
    i_start = SPINUP + PUMP_YEARS - 1
    i_yr1 = SPINUP + PUMP_YEARS
    i_end = SPINUP + PUMP_YEARS + RECOVERY_YEARS - 1

    def _anom(i):
        return read_wtd(paths[i]) - read_wtd(bpaths[i])

    return {"start": _anom(i_start), "yr1": _anom(i_yr1), "end5": _anom(i_end)}


def fig_recovery_storage_and_wtd(series: dict, landscape: dict) -> Path:
    """ΔS recovery (all catalog rates) + ΔWTD maps at 1e-6."""
    fig_w = 12.5
    fig_h = MSF.STORAGE_MAPS_FIG_H
    fig = plt.figure(figsize=(fig_w, fig_h))
    ds_bottom = MSF.STORAGE_MAPS_DS_BOTTOM
    ds_h = MSF.STORAGE_MAPS_DS_HEIGHT
    ax_l = fig.add_axes([0.08, ds_bottom, 0.38, ds_h])
    ax_r = fig.add_axes([0.52, ds_bottom, 0.38, ds_h])

    for col, d in enumerate(DOMAINS):
        ax = [ax_l, ax_r][col]
        w_f = _recovery_window(series[d][FOCUS_RATE], series[d]["_baseline"])
        d1 = float(w_f["dS"][int(np.argmin(np.abs(w_f["t"] - 1.0)))])
        ax.axvspan(0.0, 1.0, color=STORY_PUMP_TEMP, alpha=0.22, zorder=0)
        t_tail = w_f["t"][w_f["t"] >= 1.0]
        if t_tail.size:
            ax.fill_between(t_tail, d1, 0.0, color=STORY_PUMP_PERSIST, alpha=0.18, zorder=0)
        for rate in CATALOG_RATES:
            w = _recovery_window(series[d][rate], series[d]["_baseline"])
            ax.plot(w["t"], w["dS"], color=_rate_color(rate), lw=1.5)
        for x, lab in ((0.5, "temporary"), (0.78, "persistent")):
            ax.text(
                x, 0.92, lab, transform=ax.transAxes, ha="center", va="top", fontsize=9,
                color="0.25",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.85),
            )
        ax.axhline(0.0, color="0.45", lw=0.7)
        ax.axvline(0.0, color="k", ls="--", lw=0.8)
        ax.axvline(1.0, color="0.35", ls=":", lw=0.9)
        ax.set_xlim(-0.15, RECOVERY_YEARS + 0.05)
        ax.grid(True, alpha=0.3)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)

    lo = min(ax_l.get_ylim()[0], ax_r.get_ylim()[0], 0.0)
    hi = max(ax_l.get_ylim()[1], ax_r.get_ylim()[1], 0.0)
    ax_l.set_ylim(lo, hi)
    ax_r.sharey(ax_l)
    ax_l.set_ylabel(r"$\Delta$ storage ($10^6$ m$^3$)", fontsize=LABEL_FS)
    ax_r.tick_params(labelleft=False)

    prep, all_vals = {}, []
    for d in DOMAINS:
        print(f"Pumping WTD {d} {_rate_label(FOCUS_RATE)}…", flush=True)
        anoms = _wtd_triple(d, FOCUS_RATE)
        streams, active = landscape[d]
        maps = {}
        for key in MSF.WTD_COL_KEYS:
            maps[key] = R._prepare_map(
                np.asarray(anoms[key]), streams, active, align_landscape=True
            )
            all_vals.append(maps[key][0][np.isfinite(maps[key][0])])
        z0 = maps["start"][0]
        prep[d] = {"maps": maps, "aspect": z0.shape[1] / max(z0.shape[0], 1)}
    vmax = max(float(np.nanpercentile(np.abs(np.concatenate(all_vals)), 98)), 1e-3)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)

    MSF._domain_band_map_grid(
        prep=prep,
        col_keys=MSF.WTD_COL_KEYS,
        col_titles=MSF.PUMP_WTD_COL_TITLES,
        norm=norm,
        cmap="RdBu_r",
        cbar_label="Δ WTD (m)  (+ deeper / drier)",
        fig=fig,
        fig_w=fig_w,
        band_y=MSF.STORAGE_MAPS_BAND_Y,
        stream_outline=False,
        stream_legend_pos="below",
        col_titles_at_bottom=True,
    )
    MSF._legend_bottom(
        fig,
        [
            Line2D([0], [0], color=_rate_color(r), lw=1.5, label=f"{_rate_label(r)} ΔS")
            for r in CATALOG_RATES
        ]
        + [
            Patch(facecolor=STORY_PUMP_TEMP, alpha=0.35, edgecolor="none", label="Temporary (yr 1)"),
            Patch(facecolor=STORY_PUMP_PERSIST, alpha=0.25, edgecolor="none", label="Persistent"),
            Line2D([0], [0], color="none", label=f"maps @ {_rate_label(FOCUS_RATE)}"),
        ],
        ncol=5,
        bbox_to_anchor=(0.47, 0.01),
    )
    out = FIG_DIR / "ten_year_pumping_recovery_storage_and_wtd_maps.png"
    MSF._save_fig(fig, out, dpi=150, bbox_inches="tight", facecolor="white", pad_inches=0.12)
    plt.close(fig)
    print("wrote", out)
    return out


def main():
    reload_categories()
    R.log_figure_fidelity()
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    series = load_series(CATALOG_RATES)
    fig_course_focus(series)
    fig_course_by_rate(series)

    zones = {}
    for d in DOMAINS:
        zones[d] = {}
        for rate in CATALOG_RATES:
            print(f"Zone series {d} {_rate_label(rate)}…", flush=True)
            zones[d][rate] = pump_zone_series(d, rate)
    fig_mid_pump_regen(zones)

    fig_recovery_flow_anomaly(series)

    print("Building recovery ΔS + WTD maps…", flush=True)
    landscape = {d: R.stream_mask(d) for d in DOMAINS}
    fig_recovery_storage_and_wtd(series, landscape)

    print("\nDone. PNGs → pumping_final/ (all catalog rates).")


if __name__ == "__main__":
    main()
