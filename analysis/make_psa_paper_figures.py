#!/usr/bin/env python3
"""Manuscript figures for the Potomac sensitivity attribution (psa) story.

Condenses the exploratory ``psa_*`` set into captioned panels:

1. ``psa_paper_flow_normalization.png`` — recovery-window mainstem flow
   anomalies, recovery-yr-2–5 residuals, and temp/persist storage bars
   (drought + pumping matched to 10-yr drought); domains as columns.
1b. ``psa_paper_flow_per_deficit.png`` — same residual bar layout as (c,d)
   of the flow-normalization figure, but ΔQ / recovery-start storage deficit.
1c. ``psa_paper_flow_high_low.png`` — recovery mainstem % anomaly by flow
   regime: all windows (top), high baseline-flow tercile, low tercile.
1d. ``psa_paper_flow_high_low_abs.png`` — same layout with absolute ΔQ
   (domain-mm/yr equivalent of mean outlet m³/h difference).
2. ``psa_paper_perched_maps.png`` — regional vs shallowest (perched) water
   table and near-surface deficit (mm) left after recovery year 2, with the
   perched-threshold class (``swt_joint_class == 4``) outlined.
3. ``psa_paper_recovery_budgets.png`` — class column budgets in recovery:
   Potomac perched-threshold cells vs Wolf intermediate cells, and the
   whole-domain partition of the long-term deficit (near-surface vs deep refill).
4. ``psa_paper_volume_normalized.png`` — streamflow loss as % of baseline Q
   vs as a fraction of water lost (storage deficit / volume pumped).
5. ``psa_paper_pumping_loss_frac.png`` — cumulative streamflow and subsurface
   (storage) losses as a fraction of total pumped volume through pumping +
   recovery, both domains.
6. ``psa_paper_drought_loss_frac.png`` — same for the 10-yr drought, as a
   fraction of the total precipitation deficit vs baseline.
7. ``psa_paper_drought_sf_per_storage.png`` — drought cumulative streamflow
   loss divided by end-of-drought storage loss.
8. ``psa_paper_recovery_mass_balance.png`` — recovery-only: streamflow, ET,
   and recharge anomalies / storage deficit at recovery start (recharge ≈ −ET);
   drought and matched pumping, both domains.
9. ``psa_paper_pumping_rates_recovery_flux.png`` — pumping recovery only:
   streamflow / ET / recharge anomalies ÷ start-of-recovery storage deficit for
   catalog rates ``1e-7``…``1e-4``; hue = flux, saturation = rate.
10. ``psa_paper_storage_recovered.png`` — % of end-of-stress storage deficit
    recovered through recovery for all drought lengths and all
    ``10_year_pumping_tests`` rates.

Numbers come from ``potomac_sensitivity_attribution`` (caches) and
``_data/psa_summary.json``; run that module's ``main()`` first.
Catalog-rate panel also needs ``psa_extract`` caches for those members.

    conda activate /glade/work/bwest/conda-envs/droughts
    cd /glade/derecho/scratch/bwest/drought-ensemble
    python analysis/make_psa_paper_figures.py
"""
from __future__ import annotations

import colorsys
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.collections import LineCollection
from matplotlib.colors import LogNorm, Normalize, to_rgb
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator
import matplotlib.patheffects as pe

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis import potomac_sensitivity_attribution as P  # noqa: E402
from analysis import redo_recovery_with_50yr as R  # noqa: E402
from analysis.figure_paths import FIG_DIR  # noqa: E402

DOMAINS = P.DOMAINS
LABEL = P.LABEL
LABEL_FS, LEGEND_FS, TITLE_FS = 13, 12, 14
PANEL_FS = 14
DOMAIN_COLORS = {"potomac2": "#009E73", "wolf2": "#56B4E9"}
KEY_CLASS = 4  # shallowest WT 1–5 m · threshold ET
DPI = 200


def _panel_letter(ax, letter, x=-0.02, y=1.02):
    ax.text(x, y, f"({letter})", transform=ax.transAxes, fontsize=PANEL_FS,
            fontweight="bold", ha="right", va="bottom")


def _summary() -> dict:
    return json.loads(P.SUMMARY_JSON.read_text())


# ---------------------------------------------------------------------------
# Figure 1: flow + storage normalization (domains as columns)
# ---------------------------------------------------------------------------

# Encoding: one channel (color). Drought lengths share sequential browns;
# pumping is a categorical hue. Same marker / linestyle for all series.
# 10-yr is lighter than COLORS[10] so 50-yr can sit darker while still reading brown.
DROUGHT_10_COLOR = R.COLORS[3]
DROUGHT_50_COLOR = R.COLORS[10]
PUMP_COLOR = "#7B3294"
REC_SERIES = [
    ("d10", "10-yr drought", DROUGHT_10_COLOR, "-", "o"),
    ("d50", "50-yr drought", DROUGHT_50_COLOR, "-", "o"),
    ("pump", "Pumping matched to 10 year drought", PUMP_COLOR, "-", "o"),
]
REC_X_MAX = 10  # years into recovery shown (pumping length)
RESIDUAL_CASES = [
    ("d10", "10-yr\ndrought", DROUGHT_10_COLOR),
    ("d50", "50-yr\ndrought", DROUGHT_50_COLOR),
    ("pump", "Pumping matched\nto 10 year drought", PUMP_COLOR),
]
TP_CASES = [
    ("d10", "10-yr\ndrought", DROUGHT_10_COLOR),
    ("pump", "Pumping matched\nto 10 year drought", PUMP_COLOR),
]


def recovery_mainstem_pct(summary: dict, domain: str, case: str) -> tuple[np.ndarray, np.ndarray]:
    """Years into recovery (1-based) and mainstem annual % anomaly."""
    s1 = P.CASES[case]["stress"][1]
    yp = summary["step0_normalization"][domain]["cases"][case]["yearly_pct"]["main"]
    years = sorted(int(y) for y in yp if int(y) >= s1)
    return (np.asarray(years) - s1 + 1.0, np.asarray([yp[str(y)] for y in years], dtype=float))


def temp_persist_totals(domain: str) -> list[tuple[str, str, float, float, str]]:
    """End-of-stress temp / persist storage totals (10⁶ m³) for 10-yr drought and matched pumping."""
    from analysis.make_comparison_figures import MATCHED, _member
    from analysis.pumping_vs_drought_deficits import _col_storage_m, _paths

    spinup, stress = 40, 10
    i0, i1 = spinup + stress - 1, spinup + stress
    bpaths = _paths("droughts", "short_baseline", domain)
    cases = [
        ("d10", "10-yr\ndrought", _paths("droughts", "10_year_drought", domain), DROUGHT_10_COLOR),
        ("pump", "Pumping matched\nto 10 year drought",
         _paths("10_year_pumping_tests", _member(MATCHED[domain]), domain), PUMP_COLOR),
    ]
    out = []
    for key, label, paths, color in cases:
        d0, b0 = _col_storage_m(paths[i0]), _col_storage_m(bpaths[i0])
        d1, b1 = _col_storage_m(paths[i1]), _col_storage_m(bpaths[i1])
        deficit0 = np.asarray(np.maximum((b0 - d0).values, 0.0))
        deficit1 = np.asarray(np.maximum((b1 - d1).values, 0.0))
        temp = float(np.nansum(np.maximum(deficit0 - deficit1, 0.0)))
        pers = float(np.nansum(deficit1))
        out.append((key, label, temp, pers, color))
    return out


def fig_flow_normalization(summary: dict) -> Path:
    """Domains as columns: recovery Q courses, residual ΔQ, temp/persist bars."""
    tp = {d: temp_persist_totals(d) for d in DOMAINS}
    fig = plt.figure(figsize=(11.5, 11.2), constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.04, hspace=0.08, wspace=0.04)
    gs = fig.add_gridspec(3, 2, height_ratios=[1.2, 0.95, 1.05])

    # Row 0 — recovery flow courses
    lo = 0.0
    flow_axes = [fig.add_subplot(gs[0, 0])]
    flow_axes.append(fig.add_subplot(gs[0, 1], sharey=flow_axes[0]))
    for ax, d, letter in zip(flow_axes, DOMAINS, "ab"):
        ax.axvspan(0, REC_X_MAX, color=R.PERIOD_RECOVERY_FACE, alpha=R.PERIOD_RECOVERY_ALPHA, lw=0)
        for case, _lab, col, ls, mk in REC_SERIES:
            yrs, pct = recovery_mainstem_pct(summary, d, case)
            ax.plot(yrs, pct, color=col, ls=ls, marker=mk, ms=5, lw=1.8)
            lo = min(lo, float(np.min(pct)))
        ax.axhline(0, color="0.3", lw=0.8)
        ax.set_xlim(0, REC_X_MAX)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        ax.set_title(LABEL[d], fontsize=TITLE_FS)
        _panel_letter(ax, letter)
    flow_axes[0].set_ylim(1.08 * lo, 0.4)
    flow_axes[0].set_ylabel("Annual flow anomaly\n(% of baseline)", fontsize=LABEL_FS)
    plt.setp(flow_axes[1].get_yticklabels(), visible=False)
    for ax in flow_axes:
        ax.set_xlabel("Years into recovery", fontsize=LABEL_FS)

    # Row 1 — residual ΔQ (recovery yrs 2–5); case colors; % bars with mm annotation
    res_axes = [fig.add_subplot(gs[1, 0])]
    res_axes.append(fig.add_subplot(gs[1, 1], sharey=res_axes[0]))
    vmin = 0.0
    for ax, d, letter in zip(res_axes, DOMAINS, "cd"):
        norm = summary["step0_normalization"][d]["cases"]
        for i, (case, lab, col) in enumerate(RESIDUAL_CASES):
            pct = norm[case]["periods"]["rec2_5"]["main"]["pct_of_Q"]
            mm = norm[case]["periods"]["rec2_5"]["main"]["dQ_mm_yr"]
            ax.bar(i, pct, width=0.72, color=col, edgecolor="none")
            ax.text(i, pct, f"{pct:.2f}%\n({mm:.1f} mm/yr)", ha="center", va="top", fontsize=9)
            vmin = min(vmin, pct)
        ax.axhline(0, color="0.3", lw=0.8)
        ax.set_xticks(range(len(RESIDUAL_CASES)))
        ax.set_xticklabels([c[1] for c in RESIDUAL_CASES], fontsize=LABEL_FS - 2)
        _panel_letter(ax, letter)
    for ax in res_axes:
        ax.set_ylim(1.35 * vmin, 0)
    res_axes[0].set_ylabel("Δ mainstem flow,\nrecovery yrs 2–5 (% of baseline)", fontsize=LABEL_FS)
    plt.setp(res_axes[1].get_yticklabels(), visible=False)

    # Row 2 — temp / persist storage totals (10-yr drought + matched pumping)
    tp_axes = [fig.add_subplot(gs[2, 0])]
    tp_axes.append(fig.add_subplot(gs[2, 1], sharey=tp_axes[0]))
    ymax = max(t + p for rows in tp.values() for *_, t, p, _c in rows)
    for ax, d, letter in zip(tp_axes, DOMAINS, "ef"):
        rows = tp[d]
        for i, (_key, lab, temp, pers, color) in enumerate(rows):
            total = temp + pers
            f_temp = 100.0 * temp / total if total > 0 else 0.0
            ax.bar(i, pers, width=0.62, color=color, alpha=0.90, edgecolor="none", zorder=2)
            ax.bar(i, temp, width=0.62, bottom=pers, color=color, alpha=0.38,
                   hatch="///", edgecolor=color, linewidth=0.9, zorder=2)
            ax.text(i, total, f"{total:.0f}", ha="center", va="bottom", fontsize=10,
                    fontweight="semibold", color="0.15")
            if pers / max(total, 1) > 0.18:
                ax.text(i, pers * 0.5, f"P {100 - f_temp:.0f}%", ha="center", va="center",
                        fontsize=9, color="white", fontweight="semibold")
            if temp / max(total, 1) > 0.12:
                ax.text(i, pers + temp * 0.5, f"T {f_temp:.0f}%", ha="center", va="center",
                        fontsize=9, color="0.15", fontweight="semibold")
        ax.set_xticks(range(len(rows)))
        ax.set_xticklabels([r[1] for r in rows], fontsize=LABEL_FS - 2)
        ax.set_xlim(-0.55, len(rows) - 0.45)
        ax.set_ylim(0, ymax * 1.14)
        ax.grid(True, axis="y", alpha=0.28, zorder=0)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        _panel_letter(ax, letter)
    tp_axes[0].set_ylabel(r"Storage deficit ($10^6$ m$^3$)", fontsize=LABEL_FS)
    plt.setp(tp_axes[1].get_yticklabels(), visible=False)

    series_handles = [Line2D([0], [0], color=c, ls=ls, marker=mk, lw=1.8, label=lab)
                      for _, lab, c, ls, mk in REC_SERIES]
    tp_handles = [
        Patch(facecolor="0.40", alpha=0.90, label="persistent (after yr 1)"),
        Patch(facecolor="0.40", alpha=0.38, hatch="///", edgecolor="0.40",
              label="temporary (recovered in yr 1)"),
    ]
    fig.legend(handles=series_handles + tp_handles, loc="outside upper center", ncol=5,
               fontsize=LEGEND_FS - 1, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_paper_flow_normalization.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


def fig_flow_per_deficit(summary: dict) -> Path:
    """Like flow-normalization (c,d): rec yrs 2–5 ΔQ ÷ recovery-start storage deficit."""
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.4), sharey=True, constrained_layout=True)
    vmin = 0.0
    for ax, d, letter in zip(axes, DOMAINS, "ab"):
        norm = summary["step0_normalization"][d]["cases"]
        for i, (case, lab, col) in enumerate(RESIDUAL_CASES):
            frac = norm[case]["periods"]["rec2_5"]["main"]["cum_frac_deficit"]
            ax.bar(i, frac, width=0.72, color=col, edgecolor="none")
            ax.text(i, frac, f"{frac:.2f}", ha="center", va="top", fontsize=11)
            vmin = min(vmin, frac)
        ax.axhline(0, color="0.3", lw=0.8)
        ax.set_xticks(range(len(RESIDUAL_CASES)))
        ax.set_xticklabels([c[1] for c in RESIDUAL_CASES], fontsize=LABEL_FS - 1)
        ax.set_title(LABEL[d], fontsize=TITLE_FS)
        ax.yaxis.grid(True, alpha=0.28)
        ax.set_axisbelow(True)
        _panel_letter(ax, letter)
    axes[0].set_ylim(1.28 * vmin, 0)
    axes[0].set_ylabel(
        "Cumulative Δ mainstem flow /\nrecovery-start storage deficit (−)",
        fontsize=LABEL_FS,
    )
    handles = [Patch(facecolor=col, edgecolor="none", label=lab.replace("\n", " "))
               for _, lab, col in RESIDUAL_CASES]
    fig.legend(handles=handles, loc="outside upper center", ncol=3, fontsize=LEGEND_FS, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_paper_flow_per_deficit.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


def _flow_regime_masks(qb: np.ndarray) -> dict[str, np.ndarray]:
    """Masks for all / high / low windows from baseline outlet Q.

    High/low = upper/lower tercile among wet (Qb > 0) windows — same wet-tercile
    split used in the 50-yr baseflow partition analysis.
    """
    wet = qb > 0
    if wet.sum() < 6:
        # Fall back to all windows if almost everything is dry
        return {"all": np.ones_like(qb, dtype=bool),
                "high": np.ones_like(qb, dtype=bool),
                "low": np.ones_like(qb, dtype=bool)}
    lo_thr, hi_thr = np.quantile(qb[wet], [1.0 / 3.0, 2.0 / 3.0])
    return {
        "all": np.ones_like(qb, dtype=bool),
        "high": wet & (qb >= hi_thr),
        "low": wet & (qb <= lo_thr),
    }


def recovery_mainstem_by_regime(
    domain: str, case: str, regime: str, *, absolute: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Years into recovery and mainstem anomaly for a flow regime.

    Percent mode: 100 × (Qm − Qb) / Qb among regime windows.
    Absolute mode: domain-mm/yr equivalent of mean (Qm − Qb) in m³/h.
    """
    mem = P.case_member(domain, case)
    s1 = P.CASES[case]["stress"][1]
    rec_end = min(P.CASES[case]["rec_end"], s1 + REC_X_MAX)
    st = P.statics(domain)
    mx, my = st["main_outlet"]
    area = st["area_m2"]
    years, vals = [], []
    for y in range(s1, rec_end):
        qm = np.asarray(P.year_ds(domain, mem, y)["q"].values[:, my, mx], dtype=float)
        qb = np.asarray(P.year_ds(domain, "BASE", y)["q"].values[:, my, mx], dtype=float)
        m = _flow_regime_masks(qb)[regime]
        if m.sum() == 0 or not np.isfinite(qb[m].mean()):
            val = np.nan
        elif absolute:
            val = float(P.to_mm_yr(qm[m].mean() - qb[m].mean(), area))
        elif qb[m].mean() == 0:
            val = np.nan
        else:
            val = 100.0 * (qm[m].mean() - qb[m].mean()) / qb[m].mean()
        years.append(y - s1 + 1.0)
        vals.append(val)
    return np.asarray(years), np.asarray(vals, dtype=float)


def recovery_mainstem_pct_by_regime(
    domain: str, case: str, regime: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Years into recovery and mainstem % anomaly for a flow regime."""
    return recovery_mainstem_by_regime(domain, case, regime, absolute=False)


def _fig_flow_high_low(*, absolute: bool) -> Path:
    """Recovery flow courses: all / high / low baseline-flow terciles."""
    series_spec = [s for s in REC_SERIES if s[0] != "d50"]
    regimes = [
        ("all", "All windows"),
        ("high", "High flows\n(upper tercile of baseline wet windows)"),
        ("low", "Low flows\n(lower tercile of baseline wet windows)"),
    ]
    y_metric = (
        "Annual flow anomaly (mm/yr)"
        if absolute else
        "Annual flow anomaly (% of baseline)"
    )
    fig = plt.figure(figsize=(11.0, 9.6), constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.04, hspace=0.10, wspace=0.04)
    gs = fig.add_gridspec(3, 2)
    letters = iter("abcdef")
    series = {
        (d, case, reg): recovery_mainstem_by_regime(d, case, reg, absolute=absolute)
        for d in DOMAINS
        for case, *_ in series_spec
        for reg, _ in regimes
    }
    axes = np.empty((3, 2), dtype=object)
    for r, (reg, ylab) in enumerate(regimes):
        for c, d in enumerate(DOMAINS):
            if r == 0 and c == 0:
                ax = fig.add_subplot(gs[r, c])
            elif absolute:
                # Per-domain y: share within column only (outlet scale differs).
                ax = fig.add_subplot(gs[r, c], sharey=axes[0, c]) if r > 0 else fig.add_subplot(gs[r, c])
            else:
                ax = fig.add_subplot(gs[r, c], sharey=axes[0, 0])
            axes[r, c] = ax
            ax.axvspan(0, REC_X_MAX, color=R.PERIOD_RECOVERY_FACE, alpha=R.PERIOD_RECOVERY_ALPHA, lw=0)
            for case, _lab, col, ls, mk in series_spec:
                yrs, yv = series[(d, case, reg)]
                ax.plot(yrs, yv, color=col, ls=ls, marker=mk, ms=5, lw=1.8)
            ax.axhline(0, color="0.3", lw=0.8)
            ax.set_xlim(0, REC_X_MAX)
            ax.xaxis.set_major_locator(MultipleLocator(1))
            if r == 0:
                ax.set_title(LABEL[d], fontsize=TITLE_FS)
            if c == 0:
                ax.set_ylabel(f"{ylab}\n{y_metric}", fontsize=LABEL_FS - 1)
            if absolute:
                # Independent domain scales: hide redundant Wolf ticks under the top panel.
                if c == 1 and r > 0:
                    plt.setp(ax.get_yticklabels(), visible=False)
            elif c != 0:
                plt.setp(ax.get_yticklabels(), visible=False)
            if r == 2:
                ax.set_xlabel("Years into recovery", fontsize=LABEL_FS)
            _panel_letter(ax, next(letters))
    if absolute:
        for c in range(2):
            vals = np.concatenate([
                series[(DOMAINS[c], case, reg)][1]
                for case, *_ in series_spec
                for reg, _ in regimes
            ])
            vals = vals[np.isfinite(vals)]
            lo, hi = float(vals.min()), float(vals.max())
            pad = 0.08 * max(hi - lo, 1.0)
            axes[0, c].set_ylim(lo - pad, hi + pad)
    else:
        axes[0, 0].set_ylim(-15.0, 5.0)
    handles = [Line2D([0], [0], color=col, ls=ls, marker=mk, lw=1.8, label=lab)
               for _, lab, col, ls, mk in series_spec]
    handles.append(Patch(facecolor=R.PERIOD_RECOVERY_FACE, alpha=0.4, edgecolor="none", label="recovery"))
    fig.legend(handles=handles, loc="outside upper center", ncol=3, fontsize=LEGEND_FS, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / ("psa_paper_flow_high_low_abs.png" if absolute else "psa_paper_flow_high_low.png")
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


def fig_flow_high_low(summary: dict) -> Path:
    """Recovery % anomaly: all windows, then high- and low-flow terciles."""
    _ = summary
    return _fig_flow_high_low(absolute=False)


def fig_flow_high_low_abs(summary: dict) -> Path:
    """Recovery absolute ΔQ (mm/yr): all windows, then high- and low-flow terciles."""
    _ = summary
    return _fig_flow_high_low(absolute=True)


# ---------------------------------------------------------------------------
# Figure 2: perched-lens maps
# ---------------------------------------------------------------------------

_FILL = -9999.0


def _prep(z, mask, active):
    """Rotate/crop like ``R._prepare_map`` but keep NaN cells inside the domain.

    Cropping keys on finite values, so NaNs in active cells (e.g. R₂ where the
    deficit is tiny) are filled first to give every panel the same frame.
    """
    zf = np.where(active & ~np.isfinite(z), _FILL, z)
    zz, mm = R._prepare_map(zf, mask, active)
    return np.where(zz == _FILL, np.nan, zz), mm


def _outline(ax, mask, color="k"):
    """Pixel-edge outline of a boolean mask (imshow cell coordinates)."""
    m = np.pad(mask, 1)
    segs = []
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys + 1, xs + 1):
        cx, cy = x - 1, y - 1
        if not m[y - 1, x]:
            segs.append([(cx - 0.5, cy - 0.5), (cx + 0.5, cy - 0.5)])
        if not m[y + 1, x]:
            segs.append([(cx - 0.5, cy + 0.5), (cx + 0.5, cy + 0.5)])
        if not m[y, x - 1]:
            segs.append([(cx - 0.5, cy - 0.5), (cx - 0.5, cy + 0.5)])
        if not m[y, x + 1]:
            segs.append([(cx + 0.5, cy - 0.5), (cx + 0.5, cy + 0.5)])
    lc = LineCollection(segs, colors=color, linewidths=0.8,
                        path_effects=[pe.Stroke(linewidth=1.7, foreground="white"), pe.Normal()])
    ax.add_collection(lc)


def load_traits(domain: str) -> dict[str, np.ndarray]:
    with xr.open_dataset(P.DATA_DIR / f"cell_traits_{domain}.nc") as ds:
        return {k: np.asarray(ds[k].values) for k in
                ("active", "wtd_mean", "swt_mean", "swt_joint_class")}


def fig_perched_maps() -> Path:
    cols = [("wtd_mean", "Regional water table"), ("swt_mean", "Shallowest water table\n(incl. perched)"),
            ("ns_rec2", "Near-surface deficit left\nafter recovery yr 2")]
    wt_norm = LogNorm(0.1, 100)
    def_norm = Normalize(0, 150)
    prepared = {}
    for d in DOMAINS:
        t = load_traits(d)
        act = t["active"] == 1
        key = t["swt_joint_class"] == KEY_CLASS
        ns = P.ns_persistence(d, "d10")
        fields = {"wtd_mean": np.maximum(t["wtd_mean"], 0.1), "swt_mean": np.maximum(t["swt_mean"], 0.1),
                  "ns_rec2": np.where(act, 1000.0 * np.maximum(ns["ns_rec2"], 0.0), np.nan)}
        prepared[d] = {k: _prep(v, key, act) for k, v in fields.items()}
    shapes = {d: prepared[d]["ns_rec2"][0].shape for d in DOMAINS}
    height_ratios = [shapes[d][0] / shapes[d][1] for d in DOMAINS]

    fig = plt.figure(figsize=(13.5, 2.0 + 4.3 * sum(height_ratios)), constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.05, w_pad=0.04, hspace=0.04, wspace=0.03)
    gs = fig.add_gridspec(len(DOMAINS), len(cols), height_ratios=height_ratios)
    letters = iter("abcdef")
    ims = {}
    axes = np.empty((len(DOMAINS), len(cols)), dtype=object)
    for r, d in enumerate(DOMAINS):
        for c, (key, title) in enumerate(cols):
            ax = fig.add_subplot(gs[r, c])
            axes[r, c] = ax
            zz, mm = prepared[d][key]
            if key == "ns_rec2":
                ims["def"] = ax.imshow(zz, cmap="YlOrBr", norm=def_norm, interpolation="nearest")
            else:
                ims["wt"] = ax.imshow(zz, cmap="YlGnBu_r", norm=wt_norm, interpolation="nearest")
                _outline(ax, mm)
            ax.set_xticks([])
            ax.set_yticks([])
            for s in ax.spines.values():
                s.set_visible(False)
            if r == 0:
                ax.set_title(title, fontsize=TITLE_FS)
            _panel_letter(ax, next(letters), x=0.0, y=1.0)
            ax.texts[-1].set_ha("left")
    for r, d in enumerate(DOMAINS):
        axes[r, 0].text(-0.03, 0.5, LABEL[d], transform=axes[r, 0].transAxes, fontsize=TITLE_FS + 1,
                        fontweight="semibold", rotation=90, ha="right", va="center")
    cb = fig.colorbar(ims["wt"], ax=list(axes[:, :2].ravel()), location="bottom", shrink=0.6,
                      aspect=35, pad=0.02, extend="both")
    cb.set_label("Baseline depth to water table (m)", fontsize=LABEL_FS)
    cb.ax.tick_params(labelsize=12)
    cb2 = fig.colorbar(ims["def"], ax=list(axes[:, 2]), location="bottom", shrink=0.9, aspect=17, pad=0.02,
                       extend="max")
    cb2.set_label("Near-surface deficit (mm)", fontsize=LABEL_FS)
    cb2.ax.tick_params(labelsize=12)
    handle = Line2D([0], [0], color="k", lw=1.2,
                    path_effects=[pe.Stroke(linewidth=3, foreground="white"), pe.Normal()],
                    label="Perched-threshold cells (shallowest WT 1–5 m, ET crosses threshold in drought)")
    fig.legend(handles=[handle], loc="outside upper center", fontsize=LEGEND_FS + 1, frameon=False)
    out = FIG_DIR / "psa_paper_perched_maps.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------
# Figure 3: recovery column budgets
# ---------------------------------------------------------------------------

BUDGET_TERMS = [
    ("et", "ET", "#009E73", "-", "o"),
    ("dS_ns", "ΔS near-surface (top 2 m)", "#56B4E9", "-", "o"),
    ("dS_deep", "ΔS deep (below 2 m)", "#542788", "-", "o"),
    ("export", "local surface export", "#D55E00", "-", "o"),
    ("lateral", "lateral subsurface outflow (residual)", "0.55", "--", "s"),
]


def _budget(summary: dict, domain: str, key: str) -> dict[str, np.ndarray]:
    b = {k: np.asarray(v) for k, v in summary["step6_budgets"][domain]["d10"][key].items()}
    # 0 = ΔP − ΔET − Δexport − ΔS_ns − ΔS_deep − Δlateral_out
    b["lateral"] = b["precip"] - b["et"] - b["export"] - b["dS_ns"] - b["dS_deep"]
    return b


def fig_recovery_budgets(summary: dict) -> Path:
    s1 = P.CASES["d10"]["stress"][1] - P.CASES["d10"]["stress"][0]
    classes = [("potomac2", str(KEY_CLASS), "Potomac: perched-threshold cells\n(shallowest WT 1–5 m, 4.7% of area)"),
               ("wolf2", "3", "Wolf: intermediate cells\n(shallowest WT 1–5 m, 36% of area)")]
    fig = plt.figure(figsize=(14.5, 4.9), constrained_layout=True)
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.05])
    ax0 = fig.add_subplot(gs[0])
    ax1 = fig.add_subplot(gs[1], sharey=ax0)
    ax2 = fig.add_subplot(gs[2])
    for ax, (d, key, title), letter in zip((ax0, ax1), classes, "ab"):
        b = _budget(summary, d, key)
        rec = (b["years"] >= s1) & (b["years"] < s1 + 5)
        yrs = b["years"][rec] - s1 + 1
        for term, lab, col, ls, mk in BUDGET_TERMS:
            ax.plot(yrs, b[term][rec], color=col, ls=ls, marker=mk, ms=5, lw=1.9, label=lab)
        ax.axhline(0, color="0.3", lw=0.8)
        ax.set_title(title, fontsize=LABEL_FS)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        ax.set_xlim(0.7, 5.3)
        ax.set_xlabel("Years into recovery", fontsize=LABEL_FS)
        _panel_letter(ax, letter)
    ax0.set_ylabel("Anomaly vs baseline (mm/yr)", fontsize=LABEL_FS)
    plt.setp(ax1.get_yticklabels(), visible=False)

    width = 0.36
    for di, d in enumerate(DOMAINS):
        b = _budget(summary, d, "domain")
        rec25 = (b["years"] >= s1 + 1) & (b["years"] < s1 + 5)
        vals = [float(np.mean(b[t][rec25])) for t, *_ in BUDGET_TERMS]
        xs = np.arange(len(BUDGET_TERMS)) + (di - 0.5) * width
        ax2.bar(xs, vals, width=width, color=[c for _, _, c, *_ in BUDGET_TERMS],
                hatch="" if di == 0 else "//", edgecolor="white", lw=0.6)
        for x, v in zip(xs, vals):
            ax2.text(x, v + (0.12 if v >= 0 else -0.12), f"{v:+.1f}", ha="center",
                     va="bottom" if v >= 0 else "top", fontsize=9.5)
    ax2.axhline(0, color="0.3", lw=0.8)
    ax2.set_xticks(range(len(BUDGET_TERMS)))
    ax2.set_xticklabels(["ET", "ΔS\nnear-surface", "ΔS\ndeep", "surface\nexport", "lateral\n(residual)"],
                        fontsize=LABEL_FS - 2)
    ax2.set_ylim(-3.6, 3.6)
    ax2.set_ylabel("Mean anomaly, recovery yrs 2–5 (mm/yr)", fontsize=LABEL_FS)
    ax2.set_title("Whole domain", fontsize=LABEL_FS)
    ax2.legend(handles=[Patch(facecolor="0.55", edgecolor="white", label="Potomac"),
                        Patch(facecolor="0.55", edgecolor="white", hatch="//", label="Wolf")],
               fontsize=LEGEND_FS, frameon=False, loc="lower left")
    _panel_letter(ax2, "c")
    handles = [Line2D([0], [0], color=c, ls=ls, marker=mk, lw=1.9, label=lab) for _, lab, c, ls, mk in BUDGET_TERMS]
    fig.legend(handles=handles, loc="outside upper center", ncol=5, fontsize=LEGEND_FS, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_paper_recovery_budgets.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------
# Figure 4: streamflow loss vs volume of water lost
# ---------------------------------------------------------------------------

# Drought: only recovery periods — “storage deficit” is the end-of-drought
# storage shortfall. Stress-year |ΔQ|/deficit ≫ 1 (most flow loss is from
# missing rain, not storage), so those periods are not shown.
# Pumping: |ΔQ| / volume pumped over the 10 pumping years.
VOLUME_PANELS = {
    "drought": {
        "title": "Drought (long-term residual)",
        "ylabel_top": "Streamflow loss\n(% of baseline Q)",
        "ylabel_bot": "Streamflow loss ÷\nend-of-drought storage deficit",
        "rows": [
            ("d10", "rec2_5", "10-yr drought\nrec. yrs 2–5"),
            ("d50", "rec2_5", "50-yr drought\nrec. yrs 2–5"),
        ],
        "bot_key": "cum_frac_deficit",
    },
    "pump": {
        "title": "Matched pumping",
        "ylabel_top": "Streamflow loss\n(% of baseline Q)",
        "ylabel_bot": "Streamflow loss ÷\nvolume pumped",
        "rows": [
            ("pump", "stress_late", "last 5\npumping yrs"),
            ("pump", "rec2_5", "rec.\nyrs 2–5"),
            ("pump", "rec6_10", "rec.\nyrs 6–10"),
        ],
        "bot_key": "cum_frac_pumped",
    },
}


def fig_volume_normalized(summary: dict) -> Path:
    """% of Q can mislead; per unit water lost, the domains look alike (esp. pumping)."""
    norm = summary["step0_normalization"]
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.0), constrained_layout=True)
    width = 0.34
    notes = {
        (0, 0): "Potomac looks ~2× more sensitive as % of Q",
        (0, 1): "Already similar as % of Q",
        (1, 0): "Closer after scaling — still a bit higher on Potomac",
        (1, 1): "Nearly identical once scaled by water removed",
    }

    for col, key in enumerate(("drought", "pump")):
        cfg = VOLUME_PANELS[key]
        n = len(cfg["rows"])
        x0 = np.arange(n)
        top_vals = {d: [] for d in DOMAINS}
        bot_vals = {d: [] for d in DOMAINS}
        for case, period, _lab in cfg["rows"]:
            for d in DOMAINS:
                main = norm[d]["cases"][case]["periods"][period]["main"]
                top_vals[d].append(abs(main["pct_of_Q"]))
                bot_vals[d].append(abs(main[cfg["bot_key"]]))

        for row, vals, ylab in (
            (0, top_vals, cfg["ylabel_top"]),
            (1, bot_vals, cfg["ylabel_bot"]),
        ):
            ax = axes[row, col]
            for di, d in enumerate(DOMAINS):
                xs = x0 + (di - 0.5) * width
                bars = ax.bar(xs, vals[d], width=width, color=DOMAIN_COLORS[d],
                              edgecolor="white", lw=0.6, label=LABEL[d])
                for bar, v in zip(bars, vals[d]):
                    ax.text(bar.get_x() + bar.get_width() / 2, v,
                            f"{v:.2f}" if row == 1 else f"{v:.2f}",
                            ha="center", va="bottom", fontsize=12, fontweight="medium")
            ax.set_xticks(x0)
            ax.set_xticklabels([lab for *_c, lab in cfg["rows"]], fontsize=LABEL_FS - 1)
            ax.set_ylabel(ylab, fontsize=LABEL_FS)
            if row == 0:
                ax.set_title(cfg["title"], fontsize=TITLE_FS)
            ax.set_xlim(-0.55, n - 0.45)
            hi = max(max(vals[d]) for d in DOMAINS)
            ax.set_ylim(0, hi * 1.32)
            ax.axhline(0, color="0.3", lw=0.7)
            ax.yaxis.grid(True, alpha=0.28)
            ax.set_axisbelow(True)
            ax.annotate(
                notes[(row, col)],
                xy=(0.5, 0.97), xycoords="axes fraction", ha="center", va="top",
                fontsize=10.5, color="0.25", style="italic",
            )
            _panel_letter(ax, "abcd"[row * 2 + col], x=-0.04, y=1.03)

    # Recovery year 1 differs even after scaling — footnote under the drought column
    y1 = {d: abs(norm[d]["cases"]["d10"]["periods"]["rec1"]["main"]["cum_frac_deficit"]) for d in DOMAINS}
    axes[1, 0].text(
        0.5, -0.28,
        f"Recovery yr 1 (not plotted): Potomac {y1['potomac2']:.2f}, Wolf {y1['wolf2']:.2f} "
        f"of storage deficit — Wolf pays more of the debt as Q",
        transform=axes[1, 0].transAxes, fontsize=10, color="0.3", ha="center", va="top",
    )

    handles = [Patch(facecolor=DOMAIN_COLORS[d], edgecolor="white", label=LABEL[d]) for d in DOMAINS]
    fig.legend(handles=handles, loc="outside upper center", ncol=2, fontsize=LEGEND_FS, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_paper_volume_normalized.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------
# Figures 5–6: cumulative streamflow / subsurface loss ÷ forcing shortfall
# ---------------------------------------------------------------------------

LOSS_FRAC_TERMS = [
    ("streamflow", "streamflow loss (reduced export)", "#D55E00", "-"),
    ("subsurface", "subsurface loss (storage depletion)", "#542788", "-"),
]


def _loss_frac_panels(series: dict[str, dict], *, n_stress: int, n_years: int,
                      ylabel: str, xlabel: str, stress_label: str, out_name: str) -> Path:
    """Two-domain cumulative loss / denominator time series (no markers)."""
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.6), sharey=True, constrained_layout=True)
    for ax, d, letter in zip(axes, DOMAINS, "ab"):
        s = series[d]
        years = s["years"]
        ax.axvspan(0, n_stress, color=R.PERIOD_DROUGHT_FACE, alpha=R.PERIOD_DROUGHT_ALPHA, lw=0)
        ax.axvspan(n_stress, n_years, color=R.PERIOD_RECOVERY_FACE, alpha=R.PERIOD_RECOVERY_ALPHA, lw=0)
        ax.axhline(0, color="0.3", lw=0.8)
        for key, _lab, col, ls in LOSS_FRAC_TERMS:
            ax.plot(years + 0.5, s[key], color=col, ls=ls, lw=1.9)
        ax.set_xlim(0, n_years)
        ax.set_title(LABEL[d], fontsize=TITLE_FS)
        ax.xaxis.set_major_locator(MultipleLocator(5))
        ax.xaxis.set_minor_locator(MultipleLocator(1))
        ax.yaxis.grid(True, alpha=0.28)
        ax.set_axisbelow(True)
        _panel_letter(ax, letter)

    axes[0].set_ylabel(ylabel, fontsize=LABEL_FS)
    fig.supxlabel(xlabel, fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=c, ls=ls, lw=1.9, label=lab)
               for _, lab, c, ls in LOSS_FRAC_TERMS]
    handles += [
        Patch(facecolor=R.PERIOD_DROUGHT_FACE, alpha=0.25, edgecolor="none", label=stress_label),
        Patch(facecolor=R.PERIOD_RECOVERY_FACE, alpha=0.4, edgecolor="none", label="recovery"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=4, fontsize=LEGEND_FS, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / out_name
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


def fig_pumping_loss_frac(summary: dict) -> Path:
    """Cumulative capture of total pumped volume by streamflow vs storage."""
    pump = summary["step7_pumping"]
    s0, s1 = P.CASES["pump"]["stress"]
    n_pump = s1 - s0
    n_years = P.CASES["pump"]["rec_end"] - s0
    series = {}
    for d in DOMAINS:
        rows = pump[d]["rows"]
        years = np.asarray([r["year"] for r in rows], dtype=float)
        total = float(sum(r["pumped"] for r in rows if 0 <= r["year"] < n_pump))
        series[d] = {
            "years": years,
            "streamflow": np.cumsum([r["from_export"] for r in rows]) / total,
            "subsurface": np.cumsum([r["from_storage"] for r in rows]) / total,
        }
    return _loss_frac_panels(
        series, n_stress=n_pump, n_years=n_years,
        ylabel="Cumulative loss / total pumped volume (−)",
        xlabel="Years since pumping onset",
        stress_label="pumping",
        out_name="psa_paper_pumping_loss_frac.png",
    )


def fig_drought_loss_frac(summary: dict) -> Path:
    """Cumulative streamflow / storage response as a fraction of precip deficit."""
    s0, s1 = P.CASES["d10"]["stress"]
    n_dry = s1 - s0
    n_years = P.CASES["d10"]["rec_end"] - s0
    series = {}
    for d in DOMAINS:
        b = summary["step6_budgets"][d]["d10"]["domain"]
        years = np.asarray(b["years"], dtype=float)
        precip = np.asarray(b["precip"], dtype=float)
        export = np.asarray(b["export"], dtype=float)
        dS = np.asarray(b["dS_ns"], dtype=float) + np.asarray(b["dS_deep"], dtype=float)
        # precip anomaly is negative in drought; deficit = −ΔP over stress years
        total = float((-precip[years < n_dry]).sum())
        series[d] = {
            "years": years,
            "streamflow": np.cumsum(-export) / total,
            "subsurface": np.cumsum(-dS) / total,
        }
    return _loss_frac_panels(
        series, n_stress=n_dry, n_years=n_years,
        ylabel="Cumulative loss / total precip deficit (−)",
        xlabel="Years since drought onset",
        stress_label="drought",
        out_name="psa_paper_drought_loss_frac.png",
    )


def fig_drought_sf_per_storage(summary: dict) -> Path:
    """Cumulative streamflow loss relative to end-of-drought storage loss."""
    s0, s1 = P.CASES["d10"]["stress"]
    n_dry = s1 - s0
    n_years = P.CASES["d10"]["rec_end"] - s0
    series = {}
    for d in DOMAINS:
        b = summary["step6_budgets"][d]["d10"]["domain"]
        years = np.asarray(b["years"], dtype=float)
        export = np.asarray(b["export"], dtype=float)
        dS = np.asarray(b["dS_ns"], dtype=float) + np.asarray(b["dS_deep"], dtype=float)
        cum_sf = np.cumsum(-export)
        # Storage shortfall at drought end (fixed denominator through recovery)
        end_st = float((-dS[years < n_dry]).sum())
        series[d] = {"years": years, "ratio": cum_sf / end_st}

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.6), sharey=True, constrained_layout=True)
    for ax, d, letter in zip(axes, DOMAINS, "ab"):
        s = series[d]
        ax.axvspan(0, n_dry, color=R.PERIOD_DROUGHT_FACE, alpha=R.PERIOD_DROUGHT_ALPHA, lw=0)
        ax.axvspan(n_dry, n_years, color=R.PERIOD_RECOVERY_FACE, alpha=R.PERIOD_RECOVERY_ALPHA, lw=0)
        ax.plot(s["years"] + 0.5, s["ratio"], color="#D55E00", ls="-", lw=1.9)
        ax.set_xlim(0, n_years)
        ax.set_title(LABEL[d], fontsize=TITLE_FS)
        ax.xaxis.set_major_locator(MultipleLocator(5))
        ax.xaxis.set_minor_locator(MultipleLocator(1))
        ax.yaxis.grid(True, alpha=0.28)
        ax.set_axisbelow(True)
        _panel_letter(ax, letter)

    hi = max(float(np.nanmax(series[d]["ratio"])) for d in DOMAINS)
    axes[0].set_ylim(0, hi * 1.08)
    axes[0].set_ylabel(
        "Cumulative streamflow loss /\nend-of-drought storage loss (−)",
        fontsize=LABEL_FS,
    )
    fig.supxlabel("Years since drought onset", fontsize=LABEL_FS)
    handles = [
        Line2D([0], [0], color="#D55E00", lw=1.9, label="streamflow ÷ end-of-drought storage"),
        Patch(facecolor=R.PERIOD_DROUGHT_FACE, alpha=0.25, edgecolor="none", label="drought"),
        Patch(facecolor=R.PERIOD_RECOVERY_FACE, alpha=0.4, edgecolor="none", label="recovery"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=3, fontsize=LEGEND_FS, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_paper_drought_sf_per_storage.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------
# Figure 8: recovery streamflow & ET anomalies ÷ start-of-recovery deficit
# ---------------------------------------------------------------------------

RECOVERY_FLUX_TERMS = [
    ("streamflow", "streamflow anomaly (Δexport)", "#D55E00", "-"),
    ("et", "ET anomaly (ΔET)", "#009E73", "-"),
    ("recharge", "recharge anomaly (Δ to top 2 m)", "#0072B2", "-"),
]


def _recovery_flux_series(summary: dict, case: str) -> dict[str, dict]:
    """Annual recovery flux anomalies / end-of-stress storage deficit."""
    n_stress = P.CASES[case]["stress"][1] - P.CASES[case]["stress"][0]
    out = {}
    for d in DOMAINS:
        b = summary["step6_budgets"][d][case]["domain"]
        years = np.asarray(b["years"], dtype=float)
        et = np.asarray(b["et"], dtype=float)
        export = np.asarray(b["export"], dtype=float)
        recharge = np.asarray(b["recharge"], dtype=float)
        dS = np.asarray(b["dS_ns"], dtype=float) + np.asarray(b["dS_deep"], dtype=float)
        stress = years < n_stress
        rec = years >= n_stress
        deficit = float((-dS[stress]).sum())
        out[d] = {
            "years_into_rec": years[rec] - n_stress + 1.0,
            "streamflow": export[rec] / deficit,
            "et": et[rec] / deficit,
            "recharge": recharge[rec] / deficit,
        }
    return out


def fig_recovery_mass_balance(summary: dict) -> Path:
    """Recovery streamflow and ET anomalies as fractions of start-of-recovery deficit."""
    cases = [("d10", "10-yr drought"), ("pump", "Matched pumping")]
    all_series = {case: _recovery_flux_series(summary, case) for case, _ in cases}
    vals = [
        v
        for series in all_series.values()
        for d in DOMAINS
        for k, *_ in RECOVERY_FLUX_TERMS
        for v in series[d][k]
    ]
    lo, hi = float(np.min(vals)), float(np.max(vals))
    pad = 0.08 * max(hi - lo, 0.05)
    ylim = (min(lo - pad, 0.0), max(hi + pad, 0.0))

    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.2), sharey=True, constrained_layout=True)
    letters = iter("abcd")
    for row, (case, case_title) in enumerate(cases):
        series = all_series[case]
        for col, d in enumerate(DOMAINS):
            ax = axes[row, col]
            s = series[d]
            x = s["years_into_rec"]
            ax.axhline(0, color="0.3", lw=0.8)
            for key, _lab, colr, ls in RECOVERY_FLUX_TERMS:
                ax.plot(x, s[key], color=colr, ls=ls, lw=1.9)
            ax.set_xlim(0.7, float(x.max()) + 0.3)
            ax.xaxis.set_major_locator(MultipleLocator(1 if case == "d10" else 2))
            ax.xaxis.set_minor_locator(MultipleLocator(1))
            ax.yaxis.grid(True, alpha=0.28)
            ax.set_axisbelow(True)
            if row == 0:
                ax.set_title(LABEL[d], fontsize=TITLE_FS)
            _panel_letter(ax, next(letters))
        axes[row, 0].set_ylabel(
            f"{case_title}\nΔ / recovery-start storage deficit (−)",
            fontsize=LABEL_FS,
        )
        plt.setp(axes[row, 1].get_yticklabels(), visible=False)

    axes[0, 0].set_ylim(*ylim)
    fig.supxlabel("Years into recovery", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=c, ls=ls, lw=1.9, label=lab)
               for _, lab, c, ls in RECOVERY_FLUX_TERMS]
    fig.legend(handles=handles, loc="outside upper center", ncol=3, fontsize=LEGEND_FS, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_paper_recovery_mass_balance.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------
# Figure 9: pumping recovery fluxes by catalog rate (saturation = rate)
# ---------------------------------------------------------------------------

CATALOG_PUMP_RATES = [1e-7, 1e-6, 1e-5, 1e-4]


def _rate_member(rate: float) -> str:
    return f"pumping_{rate:.0e}".replace("e-0", "e-")


def _sat_color(hex_color: str, frac: float) -> tuple[float, float, float]:
    """Map rate fraction in [0, 1] to lightness/saturation of a base hue."""
    r, g, b = to_rgb(hex_color)
    h, _l, _s = colorsys.rgb_to_hls(r, g, b)
    light = 0.82 - 0.52 * frac  # low rate → light; high rate → dark
    sat = 0.30 + 0.65 * frac
    return colorsys.hls_to_rgb(h, light, sat)


def _pumping_member_domain_budget(domain: str, member: str) -> dict[str, np.ndarray]:
    """Domain-mean annual anomalies for a pumping member (mm/yr), years 40–59."""
    st = P.statics(domain)
    mask = st["active"]
    s0, s1 = P.CASES["pump"]["stress"]
    years = list(range(s0, P.CASES["pump"]["rec_end"]))
    p_avg = P.forcing_219h(domain, "average")["P"].sum(0)
    keys = ("precip", "et", "recharge", "export", "dS_ns", "dS_deep")
    out = {k: [] for k in keys}
    out["years"] = []
    for y in years:
        vals = {}
        for who in ("m", "b"):
            src = member if who == "m" else "BASE"
            ds = P.year_ds(domain, src, y)
            if who == "m":
                ns_prev = P.end_state(domain, member, y - 1, "s_ns")
                dp_prev = P.end_state(domain, member, y - 1, "s_deep")
            else:
                ns_prev = P.base_prev_end(domain, y, "s_ns")
                dp_prev = P.base_prev_end(domain, y, "s_deep")
            vals[who] = {
                "precip": float(np.nanmean(p_avg[mask])),
                "et": float(np.nanmean(ds["qflx_evap_tot"].mean("time").values[mask]) * P.MM_S_TO_MM_YR),
                "recharge": float(np.nanmean(ds["pf_et_ns"].mean("time").values[mask]) * P.H_YR * 1000),
                "export": float(np.nanmean(ds["gain"].mean("time").values[mask]) * P.H_YR / P.AREA_CELL * 1000),
                "dS_ns": float(np.nanmean((ds["s_ns"].isel(time=-1).values - ns_prev)[mask]) * 1000),
                "dS_deep": float(np.nanmean((ds["s_deep"].isel(time=-1).values - dp_prev)[mask]) * 1000),
            }
        for k in keys:
            out[k].append(vals["m"][k] - vals["b"][k])
        out["years"].append(y - s0)
    return {k: np.asarray(v) for k, v in out.items()}


def _pumping_rate_recovery_series() -> dict[str, dict[float, dict]]:
    """Per domain × rate: recovery flux anomalies / end-of-pumping storage deficit."""
    P._index.cache_clear()
    P.year_ds.cache_clear()
    n_stress = P.CASES["pump"]["stress"][1] - P.CASES["pump"]["stress"][0]
    out: dict[str, dict[float, dict]] = {}
    for d in DOMAINS:
        out[d] = {}
        for rate in CATALOG_PUMP_RATES:
            mem = _rate_member(rate)
            b = _pumping_member_domain_budget(d, mem)
            years = b["years"]
            dS = b["dS_ns"] + b["dS_deep"]
            stress = years < n_stress
            rec = years >= n_stress
            deficit = float((-dS[stress]).sum())
            if deficit <= 0:
                raise RuntimeError(f"{d} {mem}: non-positive recovery-start deficit {deficit}")
            out[d][rate] = {
                "years_into_rec": years[rec] - n_stress + 1.0,
                "streamflow": b["export"][rec] / deficit,
                "et": b["et"][rec] / deficit,
                "recharge": b["recharge"][rec] / deficit,
            }
    return out


def fig_pumping_rates_recovery_flux() -> Path:
    """Catalog-rate recovery fluxes; hue = term, saturation = pumping rate."""
    series = _pumping_rate_recovery_series()
    rate_frac = {
        r: i / (len(CATALOG_PUMP_RATES) - 1)
        for i, r in enumerate(CATALOG_PUMP_RATES)
    }
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.8), sharey=True, constrained_layout=True)
    vals = [
        v
        for d in DOMAINS
        for rate in CATALOG_PUMP_RATES
        for k, *_ in RECOVERY_FLUX_TERMS
        for v in series[d][rate][k]
    ]
    lo, hi = float(np.min(vals)), float(np.max(vals))
    pad = 0.08 * max(hi - lo, 0.05)
    ylim = (min(lo - pad, 0.0), max(hi + pad, 0.0))

    for ax, d, letter in zip(axes, DOMAINS, "ab"):
        ax.axhline(0, color="0.3", lw=0.8)
        for rate in CATALOG_PUMP_RATES:
            s = series[d][rate]
            x = s["years_into_rec"]
            for key, _lab, base, ls in RECOVERY_FLUX_TERMS:
                ax.plot(x, s[key], color=_sat_color(base, rate_frac[rate]), ls=ls, lw=1.8)
        ax.set_xlim(0.7, 10.3)
        ax.set_title(LABEL[d], fontsize=TITLE_FS)
        ax.xaxis.set_major_locator(MultipleLocator(2))
        ax.xaxis.set_minor_locator(MultipleLocator(1))
        ax.yaxis.grid(True, alpha=0.28)
        ax.set_axisbelow(True)
        _panel_letter(ax, letter)

    axes[0].set_ylim(*ylim)
    axes[0].set_ylabel("Δ / recovery-start storage deficit (−)", fontsize=LABEL_FS)
    fig.supxlabel("Years into recovery", fontsize=LABEL_FS)

    flux_handles = [
        Line2D([0], [0], color=_sat_color(c, 1.0), ls=ls, lw=1.9, label=lab)
        for _, lab, c, ls in RECOVERY_FLUX_TERMS
    ]
    rate_handles = [
        Line2D(
            [0], [0], color=_sat_color("#542788", rate_frac[r]), lw=2.2,
            label=f"{r:.0e}".replace("e-0", "e-"),
        )
        for r in CATALOG_PUMP_RATES
    ]
    fig.legend(
        handles=flux_handles + rate_handles,
        loc="outside upper center",
        ncol=7,
        fontsize=LEGEND_FS,
        frameon=False,
        title="flux (hue) · rate (saturation)",
        title_fontsize=LEGEND_FS,
    )
    R.despine_axes(fig)
    out = FIG_DIR / "psa_paper_pumping_rates_recovery_flux.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------
# Figure 10: % storage recovered through recovery (all droughts + all pumps)
# ---------------------------------------------------------------------------

DROUGHT_LENGTHS = [1, 3, 10, 50]
# Members under 10_year_pumping_tests with full 10-yr recovery on both domains.
# (3e-6 / 5e-6 exist through stress only — no recovery years yet.)
ALL_PUMP_RATES = [
    1e-7, 8.64e-7, 1e-6, 2.49e-6, 1e-5, 1e-4,
]
PUMP_REC_YEARS = 5  # match drought; Potomac baseline remap jumps after yr 54
DROUGHT_REC_YEARS = 5


def _end_total_storage(path: Path) -> float:
    with xr.open_dataset(path) as ds:
        if "total_storage" in ds:
            return float(ds["total_storage"].values[-1])
        return float(ds["subsurface_storage"].isel(time=-1).sum(skipna=True).values)


def _year_path(ensemble: str, member: str, domain: str, year: int) -> Path:
    from analysis.paper_figures import utils

    files = utils._file_locations(ensemble, member, domain, 0, interval=219)
    return Path(files[year])


def _baseline_storage(domain: str, year: int) -> float:
    """End-of-year baseline storage; remap Potomac years ≥55 onto short_baseline 50–54."""
    if year <= 54:
        return _end_total_storage(_year_path("droughts", "short_baseline", domain, year))
    if domain == "wolf2":
        try:
            return _end_total_storage(_year_path("droughts", "baseline", domain, year))
        except Exception:
            yy = 90 + (year % 5) if year >= 85 else 55 + (year % 5)
            return _end_total_storage(_year_path("droughts", "baseline", domain, yy))
    yy = 50 + (year % 5)
    return _end_total_storage(_year_path("droughts", "short_baseline", domain, yy))


def _pct_storage_recovered(
    domain: str, ensemble: str, member: str, stress_years: int, n_rec: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Years into recovery (0 … n_rec) and % of end-of-stress deficit recovered."""
    y0 = 40 + stress_years - 1  # last stress year
    def0 = _baseline_storage(domain, y0) - _end_total_storage(
        _year_path(ensemble, member, domain, y0)
    )
    if def0 <= 0:
        raise RuntimeError(f"{domain}/{member}: non-positive end-stress deficit {def0}")
    years = np.arange(0, n_rec + 1, dtype=float)
    pct = []
    for k in range(n_rec + 1):
        y = y0 + k
        deficit = _baseline_storage(domain, y) - _end_total_storage(
            _year_path(ensemble, member, domain, y)
        )
        pct.append(100.0 * (1.0 - deficit / def0))
    return years, np.asarray(pct, dtype=float)


def _pump_member(rate: float) -> str:
    """Exact ``10_year_pumping_tests`` member name for ``rate``."""
    special = {
        1e-7: "pumping_1e-7",
        8.64e-7: "pumping_8.64e-7",
        1e-6: "pumping_1e-6",
        2.49e-6: "pumping_2.49e-6",
        1e-5: "pumping_1e-5",
        1e-4: "pumping_1e-4",
    }
    for k, name in special.items():
        if abs(rate - k) / k < 1e-6:
            return name
    return f"pumping_{rate:.0e}".replace("e-0", "e-")


def _pump_rate_color(rate: float) -> str:
    """Sequential purple by log10(rate); light → dark as rate increases."""
    lo, hi = np.log10(ALL_PUMP_RATES[0]), np.log10(ALL_PUMP_RATES[-1])
    frac = float(np.clip((np.log10(rate) - lo) / (hi - lo), 0.0, 1.0))
    return _sat_color("#7B3294", frac)


def _pump_rate_label(rate: float) -> str:
    if abs(rate - 8.64e-7) / 8.64e-7 < 1e-6:
        return "8.64×10⁻⁷ (Potomac match)"
    if abs(rate - 2.49e-6) / 2.49e-6 < 1e-6:
        return "2.49×10⁻⁶ (Wolf match)"
    return f"{rate:.0e}".replace("e-0", "e-").replace("e+0", "e+")


def fig_storage_recovered() -> Path:
    """% of end-of-stress storage deficit recovered; droughts + all pumping rates."""
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.4), sharex=True, sharey=True,
                             constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.04, hspace=0.08, wspace=0.04)

    # Row 0 — drought lengths (sequential browns)
    for col, d in enumerate(DOMAINS):
        ax = axes[0, col]
        for L in DROUGHT_LENGTHS:
            yrs, pct = _pct_storage_recovered(
                d, "droughts", f"{L}_year_drought", L, DROUGHT_REC_YEARS,
            )
            ax.plot(yrs, pct, color=R.COLORS[L], lw=1.8, marker="o", ms=4.5)
        ax.axhline(100, color="0.45", lw=0.8, ls=":")
        ax.axhline(0, color="0.3", lw=0.8)
        ax.set_title(LABEL[d], fontsize=TITLE_FS)
        _panel_letter(ax, "ab"[col])
        if col == 0:
            ax.set_ylabel("Drought\nStorage recovered (% of end-stress deficit)",
                          fontsize=LABEL_FS)

    # Row 1 — all 10_year_pumping_tests rates (sequential purples)
    for col, d in enumerate(DOMAINS):
        ax = axes[1, col]
        for rate in ALL_PUMP_RATES:
            yrs, pct = _pct_storage_recovered(
                d, "10_year_pumping_tests", _pump_member(rate), 10, PUMP_REC_YEARS,
            )
            ax.plot(yrs, pct, color=_pump_rate_color(rate), lw=1.8, marker="o", ms=4.5)
        ax.axhline(100, color="0.45", lw=0.8, ls=":")
        ax.axhline(0, color="0.3", lw=0.8)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        _panel_letter(ax, "cd"[col])
        if col == 0:
            ax.set_ylabel("Pumping\nStorage recovered (% of end-stress deficit)",
                          fontsize=LABEL_FS)

    axes[0, 0].set_xlim(0, PUMP_REC_YEARS)
    axes[0, 0].set_ylim(-5, 105)
    fig.supxlabel("Years into recovery", fontsize=LABEL_FS)

    drought_handles = [
        Line2D([0], [0], color=R.COLORS[L], lw=1.8, marker="o", ms=4.5, label=f"{L}-yr drought")
        for L in DROUGHT_LENGTHS
    ]
    pump_handles = [
        Line2D([0], [0], color=_pump_rate_color(r), lw=1.8, marker="o", ms=4.5,
               label=_pump_rate_label(r))
        for r in ALL_PUMP_RATES
    ]
    fig.legend(handles=drought_handles + pump_handles, loc="outside upper center",
               ncol=7, fontsize=LEGEND_FS - 1, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_paper_storage_recovered.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


def main(which: list[str] | None = None):
    summary = _summary()
    which = which or ["flow", "flow_per_deficit", "flow_high_low", "flow_high_low_abs", "maps", "budgets", "volume", "loss_frac",
                      "drought_loss_frac", "drought_sf_per_storage",
                      "recovery_mass_balance", "pumping_rates_flux",
                      "storage_recovered"]
    if "flow" in which:
        fig_flow_normalization(summary)
    if "flow_per_deficit" in which:
        fig_flow_per_deficit(summary)
    if "flow_high_low" in which:
        fig_flow_high_low(summary)
    if "flow_high_low_abs" in which:
        fig_flow_high_low_abs(summary)
    if "maps" in which:
        fig_perched_maps()
    if "budgets" in which:
        fig_recovery_budgets(summary)
    if "volume" in which:
        fig_volume_normalized(summary)
    if "loss_frac" in which:
        fig_pumping_loss_frac(summary)
    if "drought_loss_frac" in which:
        fig_drought_loss_frac(summary)
    if "drought_sf_per_storage" in which:
        fig_drought_sf_per_storage(summary)
    if "recovery_mass_balance" in which:
        fig_recovery_mass_balance(summary)
    if "pumping_rates_flux" in which:
        fig_pumping_rates_recovery_flux()
    if "storage_recovered" in which:
        fig_storage_recovered()


if __name__ == "__main__":
    main(sys.argv[1:] or None)
