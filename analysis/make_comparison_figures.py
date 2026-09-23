#!/usr/bin/env python3
"""Drought vs matched-pumping comparison figures → ``figures/comparison/``.

Condensed set (3 figures): recovery flow anomaly, overland persist controls,
and temp/persist totals. Domain-matched rates only vs 10-yr drought.

Reproduce::

    conda activate /glade/work/bwest/conda-envs/droughts
    cd /glade/derecho/scratch/bwest/drought-ensemble
    python analysis/make_comparison_figures.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

os.environ.setdefault("PUMPING_STRESS_YEARS", "10")

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis import make_10yr_pumping_story_figures as M10  # noqa: E402
from analysis import make_story_figures as MSF  # noqa: E402
from analysis import pumping_overland_persist as POP  # noqa: E402
from analysis import redo_recovery_with_50yr as R  # noqa: E402
from analysis import wtd_threshold_vs_overland as WT  # noqa: E402
from analysis.figure_paths import FIG_DIR, reload_categories  # noqa: E402

DOMAINS = ["potomac2", "wolf2"]
DOMAIN_LABELS = {"potomac2": "Potomac", "wolf2": "Wolf"}
DOMAIN_MARKERS = {"potomac2": "o", "wolf2": "s"}
# Drought twin of story deck: domain browns; matched = purple.
DOMAIN_DROUGHT_COLORS = {"potomac2": "#4A2410", "wolf2": "#B86B2B"}

MATCHED = {"potomac2": 8.64e-7, "wolf2": 2.49e-6}
DROUGHT_MEMBER = "10_year_drought"
DROUGHT_ENSEMBLE = "droughts"
PUMP_ENSEMBLE = "10_year_pumping_tests"

SPINUP = 40
STRESS_YEARS = 10
RECOVERY_YEARS = 5
N_YEARS = SPINUP + STRESS_YEARS + RECOVERY_YEARS

MATCH_COLOR = "#7B3294"
# Overland panel: unused Okabe–Ito pair assigned to **domains**
# (stress = solid drought / dashed matched).
OVERLAND_POTOMAC_COLOR = "#009E73"  # bluish green
OVERLAND_WOLF_COLOR = "#56B4E9"  # sky blue
MATCHED_LS = (0, (4.5, 2.0))
LABEL_FS, LEGEND_FS, TITLE_FS = R.LABEL_FS, R.LEGEND_FS, R.TITLE_FS
DS_SCALE = R.DS_SCALE

_RATE_LABELS = {
    8.64e-7: "8.64e-7",
    2.49e-6: "2.49e-6",
}


def _rate_label(rate: float) -> str:
    for k, v in _RATE_LABELS.items():
        if abs(k - rate) / k < 1e-6:
            return v
    s = f"{rate:.2e}".replace("e-0", "e-").replace("e+0", "e+")
    return s.rstrip("0").rstrip(".") if "." in s.split("e")[0] else s


def _rate_pretty(rate: float) -> str:
    """Compact scientific for axis notes: 8.64×10⁻⁷."""
    exp = int(np.floor(np.log10(abs(rate))))
    mant = rate / 10**exp
    sup = str(exp).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
    mant_s = f"{mant:.2f}".rstrip("0").rstrip(".")
    return f"{mant_s}×10{sup}"


def _member(rate: float) -> str:
    return f"pumping_{_rate_label(rate)}"


M10._rate_label = _rate_label
M10._member = _member
M10.N_YEARS = N_YEARS
M10.PUMP_YEARS = STRESS_YEARS
M10.PUMP_ENSEMBLE = PUMP_ENSEMBLE

POP.PUMP_ENSEMBLE = PUMP_ENSEMBLE
POP.STRESS_YEARS = STRESS_YEARS
POP._resolve_pump = _member


def load_series() -> dict:
    series: dict = {}
    for d in DOMAINS:
        series[d] = {}
        print(f"Loading baseline {d}…", flush=True)
        bpaths = M10._paths_219h(M10.BASE_ENSEMBLE, M10.BASE_MEMBER, d, N_YEARS)
        series[d]["_baseline"] = M10.read_series(d, bpaths)
        print(f"Loading drought {d}/{DROUGHT_MEMBER}…", flush=True)
        dpaths = M10._paths_219h(DROUGHT_ENSEMBLE, DROUGHT_MEMBER, d, N_YEARS)
        series[d]["drought"] = M10.read_series(d, dpaths)
        rate = MATCHED[d]
        print(f"Loading matched {d}/{_member(rate)}…", flush=True)
        ppaths = M10._paths_219h(PUMP_ENSEMBLE, _member(rate), d, N_YEARS)
        series[d]["matched"] = M10.read_series(d, ppaths)
    return series


def _recovery_window(ds, baseline, *, years: int = RECOVERY_YEARS) -> dict:
    t0 = SPINUP + STRESS_YEARS
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
    return {
        "t": t,
        "dS": (d_sel.storage.values[:n] - b_sel.storage.values[:n]) / DS_SCALE,
        "Q": d_sel.outlet_flow.values[:n],
        "Qb": b_sel.outlet_flow.values[:n],
    }


def _annual_flow_pct(w: dict):
    t, Q, Qb = w["t"], w["Q"], w["Qb"]
    yrs, pct = [], []
    for y in range(RECOVERY_YEARS):
        m = (t >= y) & (t < y + 1)
        if not np.any(m):
            continue
        qb = float(np.mean(Qb[m]))
        if qb == 0:
            continue
        yrs.append(y + 0.5)
        pct.append(100.0 * (float(np.mean(Q[m])) - qb) / qb)
    return np.asarray(yrs), np.asarray(pct)


def fig_recovery_flow(series: dict) -> Path:
    """Yearly-mean outlet flow anomaly: drought vs matched, shared y."""
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2), constrained_layout=True)
    fig.set_constrained_layout_pads(w_pad=0.05, h_pad=0.12, wspace=0.04)

    all_pct = []
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        ax.axvspan(0.0, 1.0, color="0.85", alpha=0.40, zorder=0)
        for key, color, marker, lw in (
            ("drought", DOMAIN_DROUGHT_COLORS[d], "^", 2.0),
            ("matched", MATCH_COLOR, "o", 2.0),
        ):
            w = _recovery_window(series[d][key], series[d]["_baseline"])
            yr, pct = _annual_flow_pct(w)
            all_pct.append(pct)
            ax.plot(
                yr, pct, color=color, lw=lw, marker=marker, ms=7,
                markeredgecolor="white", markeredgewidth=0.6, zorder=3,
            )
        ax.axhline(0.0, color="0.25", lw=0.9, zorder=1)
        ax.axvline(1.0, color="0.45", ls=":", lw=0.9, zorder=1)
        ax.set_xlim(0.0, RECOVERY_YEARS)
        ax.set_xticks(range(RECOVERY_YEARS + 1))
        ax.xaxis.set_minor_locator(MultipleLocator(0.5))
        ax.grid(True, alpha=0.28)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        # Band label in data coords (centered in yr-1 window).
        ax.text(
            0.5, 0.0, "yr 1", transform=ax.get_xaxis_transform(),
            ha="center", va="bottom", fontsize=9, color="0.4",
            clip_on=False,
        )

    pct = np.concatenate([p for p in all_pct if len(p)])
    span = pct.max() - pct.min()
    pad = max(0.15 * span, 1.5)
    ylo, yhi = pct.min() - pad, pct.max() + pad
    for ax in axes:
        ax.set_ylim(ylo, yhi)
    axes[0].set_ylabel(
        "Outlet flow anomaly,\nyearly mean (% of baseline)", fontsize=LABEL_FS
    )
    axes[1].sharey(axes[0])
    axes[1].tick_params(labelleft=False)

    fig.supxlabel("Years into recovery (after 10-yr stress)", fontsize=LABEL_FS)
    handles = [
        Line2D(
            [0], [0], color="#6B3A1F", lw=2.0, marker="^", ms=7,
            markeredgecolor="white", label="10-yr drought",
        ),
        Line2D(
            [0], [0], color=MATCH_COLOR, lw=2.0, marker="o", ms=7,
            markeredgecolor="white", label="matched pumping",
        ),
    ]
    fig.legend(
        handles=handles, loc="outside upper center", ncol=2,
        fontsize=LEGEND_FS, frameon=False,
    )
    out = FIG_DIR / "compare_drought_pump_recovery_flow_anomaly.png"
    R.despine_axes(fig)
    fig.savefig(out, dpi=160, bbox_inches="tight", pad_inches=0.16)
    plt.close(fig)
    print("wrote", out)
    return out


def _cum_at_fifth(log_flow: np.ndarray, pers: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    order = np.argsort(log_flow)
    pers_o = pers[order]
    cum = np.cumsum(pers_o) / max(pers_o.sum(), 1e-30)
    frac = np.arange(1, pers_o.size + 1) / pers_o.size
    share = float(np.interp(0.20, frac, cum))
    return frac, cum, share


def fig_overland() -> Path:
    """Persist vs overland: color = domain; dash = stress; circles on bins only."""
    tables = {d: {} for d in DOMAINS}
    for d in DOMAINS:
        t = WT.cell_table(WT.load_bundle_lean(d, STRESS_YEARS), STRESS_YEARS)
        keep = t["flow"] > 0
        tables[d]["drought"] = {
            k: (v[keep] if isinstance(v, np.ndarray) else v) for k, v in t.items()
        }
        base = POP.baseline_fields(d)
        base["dist_km"] = POP.distance_to_stream_km(base["streams"], base["active"])
        bpaths = POP._paths(POP.DROUGHT_ENSEMBLE, POP.BASE_MEMBER, d)
        rate = MATCHED[d]
        print(f"Overland matched {d} {_rate_label(rate)}…", flush=True)
        pp = POP._paths(POP.PUMP_ENSEMBLE, _member(rate), d)
        pers = POP.persist_map(pp, bpaths)
        temp = POP.temp_map(pp, bpaths)
        tables[d]["matched"] = POP.cell_vectors(base, pers, temp)

    domain_color = {
        "potomac2": OVERLAND_POTOMAC_COLOR,
        "wolf2": OVERLAND_WOLF_COLOR,
    }

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 5.0), constrained_layout=True)
    fig.set_constrained_layout_pads(w_pad=0.08, wspace=0.08, h_pad=0.06)
    ax_cum, ax_flow = axes
    shares = {}

    for d in DOMAINS:
        color = domain_color[d]
        for key in ("drought", "matched"):
            t = tables[d][key]
            log_flow = np.asarray(t["log_flow"])
            pers = np.asarray(t["persistent"])
            ls = "-" if key == "drought" else MATCHED_LS
            lw = 2.0 if key == "drought" else 1.8
            frac, cum, share = _cum_at_fifth(log_flow, pers)
            shares[(d, key)] = share
            # Left: lines only (no markers).
            ax_cum.plot(
                frac, cum, color=color, lw=lw, ls=ls,
                zorder=3 if key == "drought" else 2,
            )
            xc, yc, _ = WT.binned_curve(log_flow, pers, 12)
            # Right: all circles.
            ax_flow.plot(
                xc, yc, marker="o", color=color, lw=lw, ls=ls, ms=5.5, zorder=3,
            )

    ax_cum.axvline(0.20, color="0.4", ls=":", lw=1.0, zorder=1)
    for d, y_off in (("potomac2", 0.12), ("wolf2", -0.12)):
        share = shares[(d, "drought")]
        color = domain_color[d]
        ax_cum.plot([0.20], [share], marker="o", color=color, ms=7, zorder=5)
        ax_cum.annotate(
            f"{DOMAIN_LABELS[d]} drought: {share * 100:.0f}%",
            xy=(0.20, share),
            xytext=(0.34, share + y_off),
            color=color, fontsize=10, fontweight="semibold",
            arrowprops=dict(arrowstyle="->", color=color, lw=1.0, shrinkA=2, shrinkB=2),
        )
    for d, y_off in (("potomac2", 0.02), ("wolf2", -0.22)):
        share = shares[(d, "matched")]
        color = domain_color[d]
        ax_cum.plot(
            [0.20], [share], marker="o", color=color,
            ms=6.5, zorder=4, fillstyle="none", markeredgewidth=1.4,
        )
        ax_cum.annotate(
            f"{DOMAIN_LABELS[d]} matched: {share * 100:.0f}%",
            xy=(0.20, share),
            xytext=(0.42, share + y_off),
            color=color, fontsize=9.5,
            arrowprops=dict(arrowstyle="->", color=color, lw=0.9, shrinkA=2, shrinkB=2),
        )

    ax_cum.plot([0, 1], [0, 1], color="0.55", ls=":", lw=1.1, zorder=0)
    ax_cum.set_xlim(0, 1)
    ax_cum.set_ylim(0, 1.02)
    ax_cum.set_xlabel("Fraction of cells (low → high overland flow)", fontsize=LABEL_FS)
    ax_cum.set_ylabel(
        "Cumulative fraction of\npersistent storage deficit", fontsize=LABEL_FS
    )
    ax_cum.set_title("Lowest-flow fifth holds most of the deficit", fontsize=TITLE_FS)
    ax_cum.grid(True, alpha=0.28)

    ax_flow.set_xlabel(r"log$_{10}$ overland flow (m$^3$/h)", fontsize=LABEL_FS)
    ax_flow.set_ylabel("Mean persistent deficit (m)", fontsize=LABEL_FS)
    ax_flow.set_ylim(bottom=0.0)
    ax_flow.set_title("Less overland flow, more persistent loss", fontsize=TITLE_FS)
    ax_flow.grid(True, alpha=0.28)

    handles = [
        Line2D(
            [0], [0], color=domain_color[d], lw=2.0, label=DOMAIN_LABELS[d],
        )
        for d in DOMAINS
    ] + [
        Line2D([0], [0], color="0.35", lw=2.0, ls="-", label="10-yr drought"),
        Line2D([0], [0], color="0.35", lw=1.8, ls=MATCHED_LS, label="matched pumping"),
        Line2D([0], [0], color="0.55", ls=":", lw=1.1, label="Uniform"),
    ]
    fig.legend(
        handles=handles, loc="outside lower center", ncol=5,
        fontsize=LEGEND_FS, frameon=False,
    )
    out = FIG_DIR / "compare_drought_pump_overland_controls.png"
    R.despine_axes(fig)
    fig.savefig(out, dpi=160, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print("wrote", out)
    return out


def fig_temp_persist_bars() -> Path:
    """Temp/persist totals: same end-of-stress magnitude, different rebound."""
    from analysis.pumping_vs_drought_deficits import _col_storage_m, _paths

    rows = []
    for d in DOMAINS:
        matched = MATCHED[d]
        bpaths = _paths("droughts", "short_baseline", d)
        i0 = SPINUP + STRESS_YEARS - 1
        i1 = SPINUP + STRESS_YEARS
        cases = [
            ("drought", "10-yr drought", _paths("droughts", DROUGHT_MEMBER, d), DOMAIN_DROUGHT_COLORS[d]),
            ("matched", "Matched pumping", _paths(PUMP_ENSEMBLE, _member(matched), d), MATCH_COLOR),
        ]
        for kind, label, paths, color in cases:
            d0, b0 = _col_storage_m(paths[i0]), _col_storage_m(bpaths[i0])
            d1, b1 = _col_storage_m(paths[i1]), _col_storage_m(bpaths[i1])
            deficit0 = np.asarray(np.maximum((b0 - d0).values, 0.0))
            deficit1 = np.asarray(np.maximum((b1 - d1).values, 0.0))
            temp = float(np.nansum(np.maximum(deficit0 - deficit1, 0.0)))
            pers = float(np.nansum(deficit1))
            rows.append((d, kind, label, temp, pers, color))

    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.6), sharey=True, constrained_layout=True)
    fig.set_constrained_layout_pads(w_pad=0.06, wspace=0.05, h_pad=0.08)
    width = 0.62

    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        subset = [r for r in rows if r[0] == d]
        for i, (_, kind, label, temp, pers, color) in enumerate(subset):
            total = temp + pers
            f_temp = 100.0 * temp / total if total > 0 else 0.0
            # Persistent (bottom, solid) then temporary (top, hatch).
            ax.bar(i, pers, width, color=color, alpha=0.90, edgecolor="none", zorder=2)
            ax.bar(
                i, temp, width, bottom=pers, color=color, alpha=0.38,
                hatch="///", edgecolor=color, linewidth=0.9, zorder=2,
            )
            # Total above bar.
            ax.text(
                i, total, f"{total:.0f}", ha="center", va="bottom",
                fontsize=10, fontweight="semibold", color="0.15",
            )
            # Fraction labels inside segments when tall enough.
            if pers / max(total, 1) > 0.18:
                ax.text(
                    i, pers * 0.5, f"P {100 - f_temp:.0f}%",
                    ha="center", va="center", fontsize=9, color="white", fontweight="semibold",
                )
            if temp / max(total, 1) > 0.12:
                ax.text(
                    i, pers + temp * 0.5, f"T {f_temp:.0f}%",
                    ha="center", va="center", fontsize=9, color="0.15", fontweight="semibold",
                )
        ax.set_xticks(np.arange(len(subset)))
        ax.set_xticklabels([r[2] for r in subset], fontsize=11)
        rate = MATCHED[d]
        ax.set_title(
            f"{DOMAIN_LABELS[d]}  ·  matched {_rate_pretty(rate)} m/h",
            fontsize=TITLE_FS,
        )
        if col == 0:
            ax.set_ylabel(r"Storage deficit ($10^6$ m$^3$)", fontsize=LABEL_FS)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.grid(True, axis="y", alpha=0.28, zorder=0)
        ax.set_xlim(-0.55, len(subset) - 0.45)

    # Shared y with headroom for total labels.
    ymax = max(r[3] + r[4] for r in rows)
    for ax in axes:
        ax.set_ylim(0, ymax * 1.14)

    handles = [
        Patch(facecolor="0.40", alpha=0.90, label="persistent (after yr 1)"),
        Patch(
            facecolor="0.40", alpha=0.38, hatch="///", edgecolor="0.40",
            label="temporary (recovered in yr 1)",
        ),
    ]
    fig.legend(
        handles=handles, loc="outside lower center", ncol=2,
        fontsize=LEGEND_FS, frameon=False,
    )
    out = FIG_DIR / "compare_drought_pump_temp_persist_bars.png"
    R.despine_axes(fig)
    fig.savefig(out, dpi=160, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print("wrote", out)
    return out


def main():
    reload_categories()
    R.log_figure_fidelity()
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    series = load_series()
    fig_recovery_flow(series)
    fig_overland()
    fig_temp_persist_bars()

    print("\nDone. comparison/ → flow anomaly, overland, temp/persist bars.")


if __name__ == "__main__":
    main()
