#!/usr/bin/env python3
"""Merged figures for the condensed drought storage-memory deck.

Half the deck reuses canonical figures unchanged (see
``make_drought_story_slides.py`` for the slide order). The merged figures live
here:

* ``story_recovery_storage_and_wtd_maps.png`` — annotated ΔS (temporary vs persistent)
  over the ΔWTD recovery map grid (old slide 3 top + old slide 4).
* ``story_recovery_flow_anomaly.png`` — yearly outlet-flow anomaly alone (old slide 3
  bottom); pumping twin ``story_pumping_recovery_flow_anomaly.png``.
* ``story_wtd_recovery_maps.png`` — standalone ΔWTD grid (kept for catalog).
* ``story_pumping_recovery_storage_and_wtd_maps.png`` — pumping ΔS temp/persist over
  pumping ΔWTD recovery maps (drought-parity, focus rate 1e-5 maps).
* ``story_overland_controls_persistence.png`` — persistent-mass concentration vs
  overland rank next to mean persistent deficit vs log overland flow, merging
  ``drought_recovery_drainage_deficit_concentration.png`` with the log-overland
  half of ``drought_recovery_drainage_threshold_bins.png``.

Loaders come from the analysis scripts so the numbers match those figures.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis import pumping_overland_persist as POP  # noqa: E402
from analysis import pumping_recovery_timeseries as PT  # noqa: E402
from analysis import redo_recovery_with_50yr as R  # noqa: E402
from analysis import shallow_deep_shielding as S  # noqa: E402
from analysis import wtd_threshold_vs_overland as WT  # noqa: E402
from analysis.redo_pumping_recovery_analogues import read_wtd  # noqa: E402

DOMAINS = R.DOMAINS
DOMAIN_LABELS = R.DOMAIN_LABELS
DROUGHT_LENGTHS = R.DROUGHT_LENGTHS
COLORS = R.COLORS
TEMP_COLOR = R.TEMP_COLOR
PERSIST_COLOR = R.PERSIST_COLOR
LABEL_FS, LEGEND_FS, TITLE_FS = R.LABEL_FS, R.LEGEND_FS, R.TITLE_FS
FIG_DIR = R.FIG_DIR
FOCUS_L = 10

DOMAIN_COLORS = {"potomac2": "#4A2410", "wolf2": "#B86B2B"}
DOMAIN_MARKERS = {"potomac2": "o", "wolf2": "s"}

# The two longest droughts are near-identical dark browns, and in the flow-anomaly
# row every length collapses onto ~0 after year 1, so colour alone cannot key the
# legend to the points. Shape does. Sizes carry no meaning; they only stop
# coincident markers from hiding each other.
LENGTH_MARKERS = {1: "o", 3: "s", 10: "^", 50: "D"}
LENGTH_MARKER_SIZES = {1: 5.5, 3: 6.5, 10: 4.5, 50: 8.0}

PUMP_RATES = PT.RATES
PUMP_FOCUS = PT.FOCUS_RATE
PUMP_SPINUP = PT.SPINUP_YEARS
PUMP_YEARS = PT.PUMP_YEARS
PUMP_RECOVERY_MAP_YEARS = 5
RATE_MARKERS = {1e-7: "o", 1e-6: "s", 1e-5: "^", 1e-4: "D"}
RATE_MARKER_SIZES = {1e-7: 5.5, 1e-6: 6.5, 1e-5: 4.5, 1e-4: 8.0}

# Deck-only pumping palette: purple sequential, distinct from drought browns.
# Light → dark = weak → strong rate. Purple avoids blue/green “wetness” cues and
# stays separable from tan/brown under deuteranopia (most common CVD).
STORY_PUMP_COLORS = {
    1e-7: "#DCCCE5",
    1e-6: "#B084CC",
    1e-5: "#7B3294",
    1e-4: "#3C096C",
}
STORY_PUMP_TEMP = "#C994C7"
STORY_PUMP_PERSIST = "#984EA3"
PUMP_COLORS = STORY_PUMP_COLORS


def _save_fig(fig, out, **kwargs):
    R.despine_axes(fig)
    fig.savefig(out, **kwargs)


def _legend_bottom(fig, handles, *, ncol, title=None, bbox_to_anchor=None, loc=None):
    """Figure legend under the plots; titles stay on the axes."""
    kw = dict(
        handles=handles,
        ncol=ncol,
        frameon=False,
        fontsize=LEGEND_FS,
    )
    if title is not None:
        kw["title"] = title
        kw["title_fontsize"] = LEGEND_FS
    if bbox_to_anchor is not None:
        kw["loc"] = loc or "lower center"
        kw["bbox_to_anchor"] = bbox_to_anchor
    else:
        kw["loc"] = loc or "outside lower center"
    return fig.legend(**kw)

WTD_COL_KEYS = ("start", "yr1", "end5")
WTD_COL_TITLES = {
    "start": "Recovery start\n(end of drought)",
    "yr1": "1 year\nrecovery",
    "end5": "5 year\nrecovery",
}
PUMP_WTD_COL_TITLES = {
    "start": "Recovery start\n(end of pumping)",
    "yr1": "1 year\nrecovery",
    "end5": "5 year\nrecovery",
}


def _length_marker_style(L: int, focus_length: int) -> dict:
    """Focus length filled and on top; others open and nested outward by size.

    Used for both the plotted points and the legend handles so the two cannot
    drift apart — the previous legend mirrored the faded top-row line style and
    so looked nothing like the markers it was meant to identify.
    """
    ms = LENGTH_MARKER_SIZES[L]
    return dict(
        marker=LENGTH_MARKERS[L],
        ms=ms,
        markerfacecolor=COLORS[L] if L == focus_length else "none",
        markeredgecolor=COLORS[L],
        markeredgewidth=1.4,
        zorder=20.0 if L == focus_length else 10.0 - ms,
    )


def _rate_marker_style(rate: float, focus_rate: float) -> dict:
    ms = RATE_MARKER_SIZES[rate]
    return dict(
        marker=RATE_MARKERS[rate],
        ms=ms,
        markerfacecolor=PUMP_COLORS[rate] if rate == focus_rate else "none",
        markeredgecolor=PUMP_COLORS[rate],
        markeredgewidth=1.4,
        zorder=20.0 if rate == focus_rate else 10.0 - ms,
    )


def _drought_length_handles(focus_length: int, *, include_patches: bool = False):
    handles = [
        Line2D(
            [0],
            [0],
            color=COLORS[L],
            lw=2.2 if L == focus_length else 1.4,
            label=f"{L}-year",
            **_length_marker_style(L, focus_length),
        )
        for L in DROUGHT_LENGTHS
    ]
    if include_patches:
        handles += [
            Patch(
                facecolor=TEMP_COLOR,
                alpha=0.35,
                edgecolor="none",
                label="Temporary (recovered in yr 1)",
            ),
            Patch(
                facecolor=PERSIST_COLOR,
                alpha=0.25,
                edgecolor="none",
                label="Persistent (still missing after yr 1)",
            ),
        ]
    return handles


def _pump_rate_handles(focus_rate: float, *, include_patches: bool = False):
    handles = [
        Line2D(
            [0],
            [0],
            color=PUMP_COLORS[r],
            lw=2.2 if r == focus_rate else 1.4,
            label=PT.RATE_LABELS[r],
            **_rate_marker_style(r, focus_rate),
        )
        for r in PUMP_RATES
    ]
    if include_patches:
        handles += [
            Patch(facecolor=STORY_PUMP_TEMP, alpha=0.35, edgecolor="none", label="Temporary (yr 1)"),
            Patch(facecolor=STORY_PUMP_PERSIST, alpha=0.25, edgecolor="none", label="Persistent"),
        ]
    return handles


# ---------------------------------------------------------------------------
# Two-phase recovery + streamflow
# ---------------------------------------------------------------------------


def _annual_flow_anomaly(w, recovery_years: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Per-recovery-year mean outlet flow as % departure from baseline.

    Sub-annual ΔQ is dominated by single storm peaks; yearly means are what the
    "streamflow has recovered while storage has not" claim rests on.
    """
    t, Q, Qb = w["t"], w["Q"], w["Qb"]
    if recovery_years is None:
        recovery_years = R.RECOVERY_YEARS
    mids, pct = [], []
    for year in range(1, recovery_years + 1):
        m = (t >= year - 1) & (t < year)
        if m.sum() < 5:
            continue
        qb = float(Qb[m].mean())
        if qb <= 0:
            continue
        mids.append(year - 0.5)
        pct.append(100.0 * (float(Q[m].mean()) / qb - 1.0))
    return np.asarray(mids), np.asarray(pct)


def _plot_recovery_dS_on_axes(axes, series, focus_length: int = FOCUS_L):
    """One ΔS panel per domain with temp/persist shading on the focus length."""
    for col, domain_name in enumerate(DOMAINS):
        ax = axes[col]
        baseline = series[domain_name]["_baseline"]
        windows = {}
        for L in DROUGHT_LENGTHS:
            w = R.recovery_window(
                series[domain_name][f"{L}_year_drought"],
                baseline,
                L,
                domain_name=domain_name,
            )
            windows[L] = w
            ax.plot(
                w["t"],
                w["dS"],
                color=COLORS[L],
                lw=2.2 if L == focus_length else 1.0,
                alpha=1.0 if L == focus_length else 0.35,
                zorder=3 if L == focus_length else 2,
            )

        w = windows[focus_length]
        t, dS = w["t"], w["dS"]
        d0 = float(dS[int(np.argmin(np.abs(t - 0.0)))])
        d1 = float(dS[int(np.argmin(np.abs(t - 1.0)))])
        ax.axvspan(0.0, 1.0, color=TEMP_COLOR, alpha=0.22, zorder=0)
        t_tail = t[t >= 1.0]
        if t_tail.size:
            ax.fill_between(t_tail, d1, 0.0, color=PERSIST_COLOR, alpha=0.18, zorder=0)
        ax.annotate(
            "",
            xy=(0.55, d0),
            xytext=(0.55, d1),
            arrowprops=dict(arrowstyle="<->", color=TEMP_COLOR, lw=1.6),
        )
        _label_kw = dict(
            fontsize=10,
            fontweight="semibold",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.92),
        )
        ax.text(
            0.03,
            0.93,
            "temporary",
            transform=ax.transAxes,
            color=TEMP_COLOR,
            va="top",
            ha="left",
            **_label_kw,
        )
        ax.annotate(
            "",
            xy=(1.35, d1),
            xytext=(1.35, 0.0),
            arrowprops=dict(arrowstyle="<->", color=PERSIST_COLOR, lw=1.6),
        )
        ax.text(
            0.52,
            0.93,
            "persistent",
            transform=ax.transAxes,
            color=PERSIST_COLOR,
            va="top",
            ha="left",
            **_label_kw,
        )

        ax.axhline(0.0, color="0.45", lw=0.7)
        for ax_i in (ax,):
            ax_i.axvline(0.0, color="k", ls="--", lw=0.8)
            ax_i.axvline(1.0, color="0.35", ls=":", lw=0.9)
            ax_i.set_xlim(-0.15, 5.05)
            ax_i.grid(True, alpha=0.3)
            ax_i.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax_i.xaxis.set_major_locator(MultipleLocator(1))
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)

    lo, hi = axes[0].get_ylim()
    axes[0].set_ylim(min(lo, 0.0), max(hi, 0.0))
    axes[1].sharey(axes[0])
    axes[0].set_ylabel(r"$\Delta$ storage ($10^6$ m$^3$)", fontsize=LABEL_FS)
    axes[1].tick_params(labelleft=False)


def _plot_recovery_flow_on_axes(axes, series, focus_length: int = FOCUS_L):
    all_pct = []
    for col, domain_name in enumerate(DOMAINS):
        ax = axes[col]
        baseline = series[domain_name]["_baseline"]
        for L in DROUGHT_LENGTHS:
            w = R.recovery_window(
                series[domain_name][f"{L}_year_drought"],
                baseline,
                L,
                domain_name=domain_name,
            )
            yr, pct = _annual_flow_anomaly(w)
            all_pct.append(pct)
            ax.plot(
                yr, pct, color=COLORS[L], lw=1.5, **_length_marker_style(L, focus_length)
            )

        ax.axhline(0.0, color="k", lw=0.8)
        ax.axvline(0.0, color="k", ls="--", lw=0.8)
        ax.axvline(1.0, color="0.35", ls=":", lw=0.9)
        ax.set_xlim(-0.15, 5.05)
        ax.grid(True, alpha=0.3)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)

    pct = np.concatenate(all_pct)
    pad = 0.08 * (pct.max() - pct.min())
    for ax in axes:
        ax.set_ylim(pct.min() - pad, pct.max() + pad)
    axes[0].set_ylabel(
        "Outlet flow anomaly,\nyearly mean (% of baseline)", fontsize=LABEL_FS
    )
    axes[1].sharey(axes[0])
    axes[1].tick_params(labelleft=False)


def _plot_grouped_flow_anomaly_bars(
    ax,
    bundles: list[tuple],
    colors: dict,
    recovery_years: int,
):
    """Grouped bars: one cluster per recovery year, one bar per bundle key."""
    n = len(bundles)
    x = np.arange(recovery_years)
    width = 0.82 / n
    for i, (key, pct) in enumerate(bundles):
        offset = (i - (n - 1) / 2) * width
        ax.bar(
            x + offset,
            pct[:recovery_years],
            width * 0.94,
            color=colors[key],
            edgecolor="0.30",
            linewidth=0.45,
            zorder=3,
        )
    ax.set_xticks(x)
    ax.set_xticklabels([str(y + 1) for y in x])
    ax.axhline(0.0, color="k", lw=0.8, zorder=2)
    ax.axvline(0.5, color="0.35", ls=":", lw=0.9, zorder=1)
    ax.set_xlim(-0.55, recovery_years - 0.45)
    ax.grid(True, axis="y", alpha=0.3, zorder=0)
    ax.ticklabel_format(axis="y", style="plain", useOffset=False)


def _plot_recovery_flow_bars_on_axes(axes, series, focus_length: int = FOCUS_L):
    all_pct = []
    for col, domain_name in enumerate(DOMAINS):
        ax = axes[col]
        baseline = series[domain_name]["_baseline"]
        bundles = []
        for L in DROUGHT_LENGTHS:
            w = R.recovery_window(
                series[domain_name][f"{L}_year_drought"],
                baseline,
                L,
                domain_name=domain_name,
            )
            _, pct = _annual_flow_anomaly(w)
            bundles.append((L, pct))
            all_pct.append(pct)
        _plot_grouped_flow_anomaly_bars(ax, bundles, COLORS, R.RECOVERY_YEARS)
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)

    pct = np.concatenate(all_pct)
    pad = 0.10 * (pct.max() - pct.min())
    for ax in axes:
        ax.set_ylim(pct.min() - pad, pct.max() + pad)
    axes[0].set_ylabel(
        "Outlet flow anomaly,\nyearly mean (% of baseline)", fontsize=LABEL_FS
    )
    axes[1].sharey(axes[0])
    axes[1].tick_params(labelleft=False)


def _plot_pumping_flow_bars_on_axes(axes, series, focus_rate: float = PUMP_FOCUS):
    all_pct = []
    for col, domain_name in enumerate(DOMAINS):
        ax = axes[col]
        bl = series[domain_name]["_baseline"]
        bundles = []
        for rate in PUMP_RATES:
            w = PT.recovery_window(series[domain_name][rate], bl, years=PT.RECOVERY_YEARS)
            _, pct = _annual_flow_anomaly(w, recovery_years=PT.RECOVERY_YEARS)
            bundles.append((rate, pct))
            all_pct.append(pct)
        _plot_grouped_flow_anomaly_bars(ax, bundles, PUMP_COLORS, PT.RECOVERY_YEARS)
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)

    pct = np.concatenate(all_pct)
    pad = 0.10 * (pct.max() - pct.min())
    for ax in axes:
        ax.set_ylim(pct.min() - pad, pct.max() + pad)
    axes[0].set_ylabel(
        "Outlet flow anomaly,\nyearly mean (% of baseline)", fontsize=LABEL_FS
    )
    axes[1].sharey(axes[0])
    axes[1].tick_params(labelleft=False)


def _flow_anomaly_pct_arrays(drought_series, pump_series) -> np.ndarray:
    pct = []
    for domain_name in DOMAINS:
        bl_d = drought_series[domain_name]["_baseline"]
        bl_p = pump_series[domain_name]["_baseline"]
        for L in DROUGHT_LENGTHS:
            w = R.recovery_window(
                drought_series[domain_name][f"{L}_year_drought"], bl_d, L, domain_name=domain_name
            )
            _, p = _annual_flow_anomaly(w)
            pct.append(p)
        for rate in PUMP_RATES:
            w = PT.recovery_window(pump_series[domain_name][rate], bl_p, years=PT.RECOVERY_YEARS)
            _, p = _annual_flow_anomaly(w, recovery_years=PT.RECOVERY_YEARS)
            pct.append(p)
    return np.concatenate(pct)


# Inch layout for storage+maps composites (slides 3 & 8).  Series legend sits
# under the maps; ΔS titles stay on the axes at the top.  Band bottom leaves
# room for that legend; ΔS uses the space formerly reserved above the plots.
STORAGE_MAPS_FIG_H = 7.4
STORAGE_MAPS_BAND_Y = (0.78, 4.05)
STORAGE_MAPS_DS_BOTTOM = (STORAGE_MAPS_BAND_Y[1] + 0.38) / STORAGE_MAPS_FIG_H
STORAGE_MAPS_DS_HEIGHT = 0.32


def fig_recovery_storage_and_wtd_maps(series, landscape, focus_length: int = FOCUS_L):
    """Deck slide 3: domain ΔS temp/persist over the ΔWTD recovery map band."""
    fig_w = 12.5
    fig_h = STORAGE_MAPS_FIG_H
    fig = plt.figure(figsize=(fig_w, fig_h))
    ds_bottom = STORAGE_MAPS_DS_BOTTOM
    ds_h = STORAGE_MAPS_DS_HEIGHT
    ax_l = fig.add_axes([0.08, ds_bottom, 0.38, ds_h])
    ax_r = fig.add_axes([0.52, ds_bottom, 0.38, ds_h])
    _plot_recovery_dS_on_axes([ax_l, ax_r], series, focus_length)

    prep, norm = _wtd_prep(landscape, focus_length)
    _domain_band_map_grid(
        prep=prep,
        col_keys=WTD_COL_KEYS,
        col_titles=WTD_COL_TITLES,
        norm=norm,
        cmap="RdBu_r",
        cbar_label="Δ WTD (m)  (+ deeper / drier)",
        fig=fig,
        fig_w=fig_w,
        band_y=STORAGE_MAPS_BAND_Y,
        stream_outline=False,
        stream_legend_pos="below",
        col_titles_at_bottom=True,
    )
    _legend_bottom(
        fig,
        _drought_length_handles(focus_length, include_patches=True),
        ncol=3,
        bbox_to_anchor=(0.47, 0.01),
    )
    out = FIG_DIR / "story_recovery_storage_and_wtd_maps.png"
    _save_fig(fig, out, dpi=150, bbox_inches="tight", facecolor="white", pad_inches=0.12)
    plt.close(fig)
    print("wrote", out)


def fig_recovery_flow_anomaly_combined(
    drought_series, pump_series, focus_length: int = FOCUS_L, focus_rate: float = PUMP_FOCUS
):
    """Deck slide 4: drought + pumping yearly-mean outlet flow anomaly (lines)."""
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 7.2))
    fig.subplots_adjust(left=0.14, right=0.97, top=0.91, bottom=0.20, hspace=0.40, wspace=0.10)

    _plot_recovery_flow_on_axes(axes[0], drought_series, focus_length)
    _plot_pumping_flow_on_axes(axes[1], pump_series, focus_rate)

    pct = _flow_anomaly_pct_arrays(drought_series, pump_series)
    pad = 0.10 * (pct.max() - pct.min())
    ylo, yhi = pct.min() - pad, pct.max() + pad
    for ax in axes.ravel():
        ax.set_ylim(ylo, yhi)

    for ax in axes[0]:
        ax.set_xlabel("")
    axes[1, 1].set_xlabel("")
    axes[1, 0].set_xlabel("Years into recovery (after 3-yr pumping)", fontsize=LABEL_FS)

    fig.canvas.draw()
    pos_d = axes[0, 0].get_position()
    pos_p = axes[1, 0].get_position()
    fig.text(
        0.02,
        0.5 * (pos_d.y0 + pos_d.y1),
        "Drought",
        rotation=90,
        va="center",
        ha="center",
        fontsize=13,
        fontweight="semibold",
    )
    fig.text(
        0.02,
        0.5 * (pos_p.y0 + pos_p.y1),
        "Pumping",
        rotation=90,
        va="center",
        ha="center",
        fontsize=13,
        fontweight="semibold",
    )
    gap_y = 0.5 * (pos_d.y0 + pos_p.y1)
    fig.text(0.55, gap_y, "Years into recovery", ha="center", va="center", fontsize=LABEL_FS)

    leg_d = _legend_bottom(
        fig,
        _drought_length_handles(focus_length),
        ncol=4,
        title="Drought length",
        bbox_to_anchor=(0.55, 0.055),
    )
    fig.add_artist(leg_d)
    _legend_bottom(
        fig,
        _pump_rate_handles(focus_rate),
        ncol=4,
        title="Pumping rate (m/h)",
        bbox_to_anchor=(0.55, 0.0),
    )
    out = FIG_DIR / "story_recovery_flow_anomaly_combined.png"
    _save_fig(fig, out, dpi=150, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print("wrote", out)


def fig_recovery_flow_anomaly(series, focus_length: int = FOCUS_L):
    """Deck slide 4: yearly-mean outlet flow anomaly during recovery."""
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 3.6), constrained_layout=True)
    fig.set_constrained_layout_pads(w_pad=0.04, h_pad=0.06)
    _plot_recovery_flow_on_axes(axes, series, focus_length)
    fig.supxlabel("Years into recovery", fontsize=LABEL_FS)
    _legend_bottom(fig, _drought_length_handles(focus_length), ncol=4)
    out = FIG_DIR / "story_recovery_flow_anomaly.png"
    _save_fig(fig, out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_recovery_and_streamflow(series, focus_length: int = FOCUS_L):
    """Legacy 2×2 composite — kept for catalog; deck uses the split figures."""
    fig, axes = plt.subplots(
        2, 2, figsize=(11.0, 6.4), sharex="col", constrained_layout=True
    )
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.04, hspace=0.07, wspace=0.05)
    _plot_recovery_dS_on_axes(axes[0], series, focus_length)
    _plot_recovery_flow_on_axes(axes[1], series, focus_length)
    fig.supxlabel("Years into recovery", fontsize=LABEL_FS)
    _legend_bottom(
        fig, _drought_length_handles(focus_length, include_patches=True), ncol=3
    )
    out = FIG_DIR / "story_recovery_and_streamflow.png"
    _save_fig(fig, out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


# ---------------------------------------------------------------------------
# Spatial WTD recovery, both domains in one grid
# ---------------------------------------------------------------------------


def _wtd_prep(landscape, drought_length: int = FOCUS_L):
    prep, all_vals = {}, []
    for domain_name in DOMAINS:
        print(f"WTD anomalies {domain_name} {drought_length}-yr…", flush=True)
        anoms = R.wtd_anomaly_triple(domain_name, drought_length)
        streams, active = landscape[domain_name]
        maps = {}
        for key in WTD_COL_KEYS:
            maps[key] = R._prepare_map(
                anoms[key].values, streams, active, align_landscape=True
            )
            all_vals.append(maps[key][0][np.isfinite(maps[key][0])])
        z0 = maps["start"][0]
        prep[domain_name] = {"maps": maps, "aspect": z0.shape[1] / max(z0.shape[0], 1)}
    vmax = float(np.nanpercentile(np.abs(np.concatenate(all_vals)), 98))
    return prep, TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)


def _domain_band_map_grid(
    *,
    prep: dict,
    col_keys: tuple[str, ...],
    col_titles: dict[str, str],
    norm,
    cmap: str,
    cbar_label: str,
    outfile: str | None = None,
    fig: plt.Figure | None = None,
    fig_w: float = 13.0,
    band_y: tuple[float, float] | None = None,
    stream_outline: bool = True,
    stream_legend_pos: str | None = None,
    col_titles_at_bottom: bool = False,
):
    """One map row per domain; each domain's row height follows its own aspect.

    When ``fig`` and ``band_y=(y_bottom, y_top)`` are given, maps are drawn into
    that inch band of an existing figure (used by the storage+maps composites).
    Otherwise a standalone figure is created and saved to ``outfile``.

    ``col_titles_at_bottom=True`` places the recovery-stage labels under each
    heatmap column (deck composites); the default keeps them above (standalone).
    """
    left_gutter, right_cbar = 1.55, 1.70
    key_gap, band_gap = 0.16, 0.30
    col_hdr, bottom_leg = 0.52, 0.40
    title_gap = 0.10
    n_keys = len(col_keys)

    col_w = (fig_w - left_gutter - right_cbar - (n_keys - 1) * key_gap) / n_keys
    map_h = {d: col_w / max(prep[d]["aspect"], 0.35) for d in DOMAINS}

    standalone = fig is None
    top_reserve = 0.0 if col_titles_at_bottom else col_hdr
    bottom_title = col_hdr if col_titles_at_bottom else 0.0
    if standalone:
        fig_h = top_reserve + sum(map_h.values()) + (len(DOMAINS) - 1) * band_gap + bottom_leg
        if col_titles_at_bottom:
            fig_h += bottom_title
        fig = plt.figure(figsize=(fig_w, fig_h))
        y_bottom, y_top = bottom_leg + bottom_title, fig_h - top_reserve
    else:
        fig_h = fig.get_figheight()
        y_bottom, y_top = band_y
        available = y_top - y_bottom
        needed = (
            sum(map_h.values())
            + (len(DOMAINS) - 1) * band_gap
            + top_reserve
            + bottom_leg
            + bottom_title
        )
        if needed > available:
            scale = available / needed
            col_w *= scale
            map_h = {d: col_w / max(prep[d]["aspect"], 0.35) for d in DOMAINS}
            col_hdr *= scale
            bottom_leg *= scale
            band_gap *= scale
            title_gap *= scale

    def ax_rect(x_in, y_in, w_in, h_in):
        return [x_in / fig_w, y_in / fig_h, w_in / fig_w, h_in / fig_h]

    if not col_titles_at_bottom:
        header_y = y_top + (0.06 if standalone else 0.03)
        for k_i, key in enumerate(col_keys):
            fig.text(
                (left_gutter + k_i * (col_w + key_gap) + col_w / 2) / fig_w,
                min(header_y, fig_h - 0.08) / fig_h,
                col_titles[key],
                ha="center",
                va="bottom",
                fontsize=12 if not standalone else 13,
                linespacing=1.15,
            )

    im = None
    y_cursor = y_top
    for domain_name in DOMAINS:
        h = map_h[domain_name]
        y0 = y_cursor - h
        fig.text(
            (left_gutter - 0.20) / fig_w,
            (y0 + h / 2) / fig_h,
            DOMAIN_LABELS[domain_name],
            ha="right",
            va="center",
            fontsize=14 if not standalone else 15,
            fontweight="semibold",
        )
        for k_i, key in enumerate(col_keys):
            x0 = left_gutter + k_i * (col_w + key_gap)
            ax = fig.add_axes(ax_rect(x0, y0, col_w, h))
            z, streams = prep[domain_name]["maps"][key]
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
                scatter_kw = dict(s=7, c=R.STREAM_COLOR, marker="s", zorder=3)
                if stream_outline:
                    scatter_kw.update(linewidths=0.25, edgecolors="0.15")
                else:
                    scatter_kw.update(linewidths=0, edgecolors="none")
                ax.scatter(sx + 0.5, sy + 0.5, **scatter_kw)
            ax.set_aspect("auto")
            ax.set_xlim(0, nx)
            ax.set_ylim(ny, 0)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
        y_cursor = y0 - band_gap

    if col_titles_at_bottom:
        title_y = y_cursor + title_gap
        for k_i, key in enumerate(col_keys):
            fig.text(
                (left_gutter + k_i * (col_w + key_gap) + col_w / 2) / fig_w,
                title_y / fig_h,
                col_titles[key],
                ha="center",
                va="top",
                fontsize=12 if not standalone else 13,
                linespacing=1.15,
            )

    cbar_bottom = y_bottom + bottom_leg + bottom_title + 0.05
    if stream_legend_pos == "below":
        cbar_bottom += 0.20
    cbar_top = y_top - top_reserve + 0.02
    cax = fig.add_axes(
        ax_rect(fig_w - right_cbar + 0.30, cbar_bottom, 0.18, cbar_top - cbar_bottom)
    )
    cbar = fig.colorbar(im, cax=cax)
    cbar.set_label(cbar_label, fontsize=13)
    cbar.ax.tick_params(labelsize=11)
    cbar_cx = (fig_w - right_cbar + 0.39) / fig_w
    if stream_legend_pos == "above":
        fig.legend(
            handles=[R._add_stream_legend_handle()],
            loc="lower center",
            frameon=False,
            fontsize=11,
            bbox_to_anchor=(cbar_cx, (cbar_top + 0.08) / fig_h),
        )
    elif stream_legend_pos == "below":
        fig.legend(
            handles=[R._add_stream_legend_handle()],
            loc="upper center",
            frameon=False,
            fontsize=11,
            bbox_to_anchor=(cbar_cx, max((cbar_bottom - 0.22) / fig_h, 0.02)),
        )
    elif standalone:
        fig.legend(
            handles=[R._add_stream_legend_handle()],
            loc="lower center",
            frameon=False,
            fontsize=13,
            bbox_to_anchor=(0.47, 0.01),
        )
    if standalone and outfile:
        out = FIG_DIR / outfile
        _save_fig(fig, out, dpi=160, facecolor="white")
        plt.close(fig)
        print("wrote", out)
    return im


def fig_wtd_recovery_maps(landscape, drought_length: int = FOCUS_L):
    prep, norm = _wtd_prep(landscape, drought_length)
    _domain_band_map_grid(
        prep=prep,
        col_keys=WTD_COL_KEYS,
        col_titles=WTD_COL_TITLES,
        norm=norm,
        cmap="RdBu_r",
        cbar_label="Δ WTD (m)  (+ deeper / drier)",
        outfile="story_wtd_recovery_maps.png",
    )


# ---------------------------------------------------------------------------
# Overland connectivity sets where the persistent deficit sits
# ---------------------------------------------------------------------------


def _load_pump_overland_table(domain_name: str, rate: float) -> dict:
    """Per-cell persist vs overland for one pumping rate (same masks as POP.load_all)."""
    base = POP.baseline_fields(domain_name)
    base["dist_km"] = POP.distance_to_stream_km(base["streams"], base["active"])
    bpaths = POP._paths(POP.DROUGHT_ENSEMBLE, POP.BASE_MEMBER, domain_name)
    pp = POP._paths(POP.PUMP_ENSEMBLE, POP._resolve_pump(rate), domain_name)
    pers = POP.persist_map(pp, bpaths)
    temp = POP.temp_map(pp, bpaths)
    return POP.cell_vectors(base, pers, temp)


def fig_overland_controls(
    tables: dict,
    pump_tables: dict | None = None,
    pump_rate: float = PUMP_FOCUS,
):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
    fig.set_constrained_layout_pads(w_pad=0.06, wspace=0.06, h_pad=0.06)
    ax_cum, ax_flow = axes
    pump_color = PUMP_COLORS[pump_rate]
    pump_ls = (0, (4, 2))

    for domain_name in DOMAINS:
        t = tables[domain_name]
        color = DOMAIN_COLORS[domain_name]
        marker = DOMAIN_MARKERS[domain_name]
        label = DOMAIN_LABELS[domain_name]

        order = np.argsort(t["log_flow"])
        pers = t["persistent"][order]
        cum = np.cumsum(pers) / pers.sum()
        frac_cells = np.arange(1, pers.size + 1) / pers.size
        ax_cum.plot(frac_cells, cum, color=color, lw=2.0, label=label)
        share = float(np.interp(0.20, frac_cells, cum))
        ax_cum.plot([0.20], [share], marker=marker, color=color, ms=7, zorder=4)
        y_off = 0.13 if domain_name == "potomac2" else -0.13
        ax_cum.annotate(
            f"{label}: {share * 100:.0f}%",
            xy=(0.20, share),
            xytext=(0.33, share + y_off),
            color=color,
            fontsize=11,
            fontweight="semibold",
            arrowprops=dict(arrowstyle="->", color=color, lw=1.0, shrinkA=2, shrinkB=2),
        )

        xc, yc, _ = WT.binned_curve(t["log_flow"], t["persistent"], 12)
        ax_flow.plot(xc, yc, marker=marker, color=color, lw=1.8, ms=5, label=label)

        if pump_tables is not None:
            pt = pump_tables[domain_name]
            order_p = np.argsort(pt["log_flow"])
            pers_p = pt["persistent"][order_p]
            cum_p = np.cumsum(pers_p) / pers_p.sum()
            frac_p = np.arange(1, pers_p.size + 1) / pers_p.size
            ax_cum.plot(
                frac_p,
                cum_p,
                color=pump_color,
                lw=1.8,
                ls=pump_ls,
                marker=marker,
                markevery=max(pers_p.size // 10, 1),
                ms=4.5,
                alpha=0.95,
                zorder=3,
            )
            xc_p, yc_p, _ = WT.binned_curve(pt["log_flow"], pt["persistent"], 12)
            ax_flow.plot(
                xc_p,
                yc_p,
                marker=marker,
                color=pump_color,
                lw=1.6,
                ls=pump_ls,
                ms=5,
                alpha=0.95,
                zorder=3,
            )

    ax_cum.plot([0, 1], [0, 1], color="0.6", ls="--", lw=1.0, label="Uniform")
    ax_cum.axvline(0.20, color="0.4", ls=":", lw=1.0)
    ax_cum.set_xlim(0, 1)
    ax_cum.set_ylim(0, 1.02)
    ax_cum.set_xlabel("Fraction of cells (low → high overland flow)", fontsize=LABEL_FS)
    ax_cum.set_ylabel(
        "Cumulative fraction of\npersistent storage deficit", fontsize=LABEL_FS
    )
    ax_cum.set_title("Lowest-flow fifth holds most of the deficit", fontsize=TITLE_FS)

    ax_flow.set_xlabel(r"log$_{10}$ overland flow (m$^3$/h)", fontsize=LABEL_FS)
    ax_flow.set_ylabel("Mean persistent deficit (m)", fontsize=LABEL_FS)
    ax_flow.set_ylim(bottom=0.0)
    ax_flow.set_title("Less overland flow, more persistent loss", fontsize=TITLE_FS)

    for ax in axes:
        ax.grid(True, alpha=0.3)

    handles = [
        Line2D(
            [0],
            [0],
            color=DOMAIN_COLORS[d],
            marker=DOMAIN_MARKERS[d],
            lw=2.0,
            ms=6,
            label=DOMAIN_LABELS[d],
        )
        for d in DOMAINS
    ]
    if pump_tables is not None:
        handles.append(
            Line2D(
                [0],
                [0],
                color=pump_color,
                lw=1.8,
                ls=pump_ls,
                label=f"Pumping {PT.RATE_LABELS[pump_rate]} m/h",
            )
        )
    handles.append(Line2D([0], [0], color="0.6", ls="--", lw=1.0, label="Uniform"))
    _legend_bottom(fig, handles, ncol=4)

    out = FIG_DIR / "story_overland_controls_persistence.png"
    _save_fig(fig, out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


# ---------------------------------------------------------------------------
# Pumping recovery parity (focus-rate maps, all rates on line plots)
# ---------------------------------------------------------------------------


def _pumping_wtd_anomaly_triple(domain_name: str, rate: float):
    paths_rate = PT._paths(PT.PUMP_ENSEMBLE, PT._resolve_member(rate), domain_name)
    paths_base = PT._paths(PT.BASE_ENSEMBLE, PT.BASE_MEMBER, domain_name)
    i_start = PUMP_SPINUP + PUMP_YEARS - 1
    i_yr1 = PUMP_SPINUP + PUMP_YEARS
    i_end = PUMP_SPINUP + PUMP_YEARS + PUMP_RECOVERY_MAP_YEARS - 1
    return {
        "start": read_wtd(paths_rate[i_start]) - read_wtd(paths_base[i_start]),
        "yr1": read_wtd(paths_rate[i_yr1]) - read_wtd(paths_base[i_yr1]),
        "end5": read_wtd(paths_rate[i_end]) - read_wtd(paths_base[i_end]),
    }


def _pumping_wtd_prep(landscape, focus_rate: float = PUMP_FOCUS):
    prep, all_vals = {}, []
    for domain_name in DOMAINS:
        print(f"Pumping WTD {domain_name} {PT.RATE_LABELS[focus_rate]}…", flush=True)
        anoms = _pumping_wtd_anomaly_triple(domain_name, focus_rate)
        streams, active = landscape[domain_name]
        maps = {}
        for key in WTD_COL_KEYS:
            maps[key] = R._prepare_map(
                anoms[key].values, streams, active, align_landscape=True
            )
            all_vals.append(maps[key][0][np.isfinite(maps[key][0])])
        z0 = maps["start"][0]
        prep[domain_name] = {"maps": maps, "aspect": z0.shape[1] / max(z0.shape[0], 1)}
    vmax = max(float(np.nanpercentile(np.abs(np.concatenate(all_vals)), 98)), 1e-3)
    return prep, TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)


def _plot_pumping_dS_on_axes(
    axes, series, focus_rate: float = PUMP_FOCUS, rates: list[float] | None = None
):
    plot_rates = rates if rates is not None else PUMP_RATES
    for col, domain_name in enumerate(DOMAINS):
        ax = axes[col]
        bl = series[domain_name]["_baseline"]
        windows = {}
        for rate in plot_rates:
            w = PT.recovery_window(series[domain_name][rate], bl, years=5)
            windows[rate] = w
            ax.plot(
                w["t"],
                w["dS"],
                color=PUMP_COLORS[rate],
                lw=2.2 if rate == focus_rate else 1.0,
                alpha=1.0 if rate == focus_rate else 0.35,
                zorder=3 if rate == focus_rate else 2,
            )

        if focus_rate in windows:
            w = windows[focus_rate]
            t, dS = w["t"], w["dS"]
            d0 = float(dS[int(np.argmin(np.abs(t - 0.0)))])
            d1 = float(dS[int(np.argmin(np.abs(t - 1.0)))])
            ax.axvspan(0.0, 1.0, color=STORY_PUMP_TEMP, alpha=0.22, zorder=0)
            t_tail = t[t >= 1.0]
            if t_tail.size:
                ax.fill_between(t_tail, d1, 0.0, color=STORY_PUMP_PERSIST, alpha=0.18, zorder=0)

        ax.axhline(0.0, color="0.45", lw=0.7)
        ax.axvline(0.0, color="k", ls="--", lw=0.8)
        ax.axvline(1.0, color="0.35", ls=":", lw=0.9)
        ax.set_xlim(-0.15, 5.05)
        ax.grid(True, alpha=0.3)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)

    lo, hi = axes[0].get_ylim()
    axes[0].set_ylim(min(lo, 0.0), max(hi, 0.0))
    axes[1].sharey(axes[0])
    axes[0].set_ylabel(r"$\Delta$ storage ($10^6$ m$^3$)", fontsize=LABEL_FS)
    axes[1].tick_params(labelleft=False)


def _plot_pumping_flow_on_axes(axes, series, focus_rate: float = PUMP_FOCUS):
    all_pct = []
    for col, domain_name in enumerate(DOMAINS):
        ax = axes[col]
        bl = series[domain_name]["_baseline"]
        for rate in PUMP_RATES:
            w = PT.recovery_window(series[domain_name][rate], bl, years=PT.RECOVERY_YEARS)
            yr, pct = _annual_flow_anomaly(w, recovery_years=PT.RECOVERY_YEARS)
            all_pct.append(pct)
            ax.plot(
                yr, pct, color=PUMP_COLORS[rate], lw=1.5, **_rate_marker_style(rate, focus_rate)
            )

        ax.axhline(0.0, color="k", lw=0.8)
        ax.axvline(0.0, color="k", ls="--", lw=0.8)
        ax.axvline(1.0, color="0.35", ls=":", lw=0.9)
        ax.set_xlim(-0.15, 10.05)
        ax.grid(True, alpha=0.3)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.xaxis.set_major_locator(MultipleLocator(2))
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)

    pct = np.concatenate(all_pct)
    pad = 0.08 * (pct.max() - pct.min())
    for ax in axes:
        ax.set_ylim(pct.min() - pad, pct.max() + pad)
    axes[0].set_ylabel(
        "Outlet flow anomaly,\nyearly mean (% of baseline)", fontsize=LABEL_FS
    )
    axes[1].sharey(axes[0])
    axes[1].tick_params(labelleft=False)


def fig_pumping_recovery_storage_and_wtd_maps(series, landscape, focus_rate: float = PUMP_FOCUS):
    fig_w = 12.5
    fig_h = STORAGE_MAPS_FIG_H
    fig = plt.figure(figsize=(fig_w, fig_h))
    ds_bottom = STORAGE_MAPS_DS_BOTTOM
    ds_h = STORAGE_MAPS_DS_HEIGHT
    ax_l = fig.add_axes([0.08, ds_bottom, 0.38, ds_h])
    ax_r = fig.add_axes([0.52, ds_bottom, 0.38, ds_h])
    _plot_pumping_dS_on_axes([ax_l, ax_r], series, focus_rate, rates=[focus_rate])

    prep, norm = _pumping_wtd_prep(landscape, focus_rate)
    _domain_band_map_grid(
        prep=prep,
        col_keys=WTD_COL_KEYS,
        col_titles=PUMP_WTD_COL_TITLES,
        norm=norm,
        cmap="RdBu_r",
        cbar_label="Δ WTD (m)  (+ deeper / drier)",
        fig=fig,
        fig_w=fig_w,
        band_y=STORAGE_MAPS_BAND_Y,
        stream_outline=False,
        stream_legend_pos="below",
        col_titles_at_bottom=True,
    )
    _legend_bottom(
        fig,
        [
            Line2D(
                [0],
                [0],
                color=PUMP_COLORS[focus_rate],
                lw=2.2,
                label=f"{PT.RATE_LABELS[focus_rate]} m/h (maps)",
            ),
            Patch(facecolor=STORY_PUMP_TEMP, alpha=0.35, edgecolor="none", label="Temporary (yr 1)"),
            Patch(facecolor=STORY_PUMP_PERSIST, alpha=0.25, edgecolor="none", label="Persistent"),
        ],
        ncol=3,
        bbox_to_anchor=(0.47, 0.01),
    )
    out = FIG_DIR / "story_pumping_recovery_storage_and_wtd_maps.png"
    _save_fig(fig, out, dpi=150, bbox_inches="tight", facecolor="white", pad_inches=0.12)
    plt.close(fig)
    print("wrote", out)


def fig_pumping_recovery_flow_anomaly(series, focus_rate: float = PUMP_FOCUS):
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 3.6), constrained_layout=True)
    fig.set_constrained_layout_pads(w_pad=0.04, h_pad=0.06)
    _plot_pumping_flow_on_axes(axes, series, focus_rate)
    fig.supxlabel("Years into recovery (after 3-yr pumping)", fontsize=LABEL_FS)
    _legend_bottom(fig, _pump_rate_handles(focus_rate), ncol=4)
    out = FIG_DIR / "story_pumping_recovery_flow_anomaly.png"
    _save_fig(fig, out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


# ---------------------------------------------------------------------------
# Near-surface vs deep, one drought length, through recovery
# ---------------------------------------------------------------------------


def fig_mid_drought_regen_10yr(drought_length: int = FOCUS_L):
    """Deck version of the shielding drought course: 10-yr only, plus recovery.

    Both canonical variants overlay the 1 / 3 / 10-year courses, and the shorter
    two sit underneath the 10-year line over most of the axis without adding to
    the argument. Dropping to the focus length keeps the near-surface seasonal
    pulses legible, and carrying the axis through recovery is what shows that the
    near-surface returns to baseline while the deep deficit only partly refills.
    """
    series = {}
    for domain_name in DOMAINS:
        print(f"Zone series {domain_name} {drought_length}-yr + recovery…", flush=True)
        series[domain_name] = {
            drought_length: S.drought_zone_series(
                domain_name,
                drought_length,
                include_recovery=True,
                spinup_years=R.COURSE_SPINUP_YEARS,
            )
        }
    # Recovery stretches the axis from 10 to 15 years, so widen to the slide
    # aspect (~12.5 x 6.3 in of content) rather than compressing the seasonal
    # pulses into the canonical figure's width.
    S.fig_mid_drought_regen(
        series,
        outfile="story_mid_drought_regen_10yr.png",
        include_recovery=True,
        spinup_years=R.COURSE_SPINUP_YEARS,
        figsize=(11.8, 6.3),
        legend_loc="outside lower center",
    )


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    landscape = {d: R.stream_mask(d) for d in DOMAINS}

    drought_series = R.load_all_series()
    fig_recovery_storage_and_wtd_maps(drought_series, landscape)
    fig_recovery_and_streamflow(drought_series)
    fig_wtd_recovery_maps(landscape)
    fig_mid_drought_regen_10yr()

    print("Loading pumping recovery series…", flush=True)
    pump_series = PT.load_all()
    fig_recovery_flow_anomaly(drought_series)
    fig_recovery_flow_anomaly_combined(drought_series, pump_series)
    fig_pumping_recovery_storage_and_wtd_maps(pump_series, landscape)
    fig_pumping_recovery_flow_anomaly(pump_series)

    tables = {}
    pump_tables = {}
    for domain_name in DOMAINS:
        t = WT.cell_table(WT.load_bundle_lean(domain_name, FOCUS_L), FOCUS_L)
        # Cells with zero baseline overland flow have no meaningful log-flow rank;
        # excluding them reproduces the published 54% / 42% mass shares.
        keep = t["flow"] > 0
        tables[domain_name] = {
            k: (v[keep] if isinstance(v, np.ndarray) else v) for k, v in t.items()
        }
        print(f"Pumping overland table {domain_name} {PT.RATE_LABELS[PUMP_FOCUS]}…", flush=True)
        pump_tables[domain_name] = _load_pump_overland_table(domain_name, PUMP_FOCUS)
    fig_overland_controls(tables, pump_tables)


if __name__ == "__main__":
    main()
