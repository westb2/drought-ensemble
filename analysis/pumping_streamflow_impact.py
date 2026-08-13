#!/usr/bin/env python3
"""Pumping impact on outlet streamflow (preliminary; no recovery years).

Questions
---------
1. How much does outlet Q drop vs average-year baseline, by rate and pump year?
2. Does Q keep declining as deep storage builds (yr2–3), or plateau like mid-drought?
3. Contrast: drought deep storage was largely decoupled from Q — does deep pumping couple?

Uses slim 219 h pumping cache + short_baseline via redo_pumping_recovery_analogues.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT / "analysis"))

from redo_pumping_recovery_analogues import (  # noqa: E402
    COLORS,
    DOMAIN_LABELS,
    DOMAINS,
    FIG_DIR,
    LABEL_FS,
    LEGEND_FS,
    PUMP_YEARS,
    RATE_LABELS,
    RATES,
    TITLE_FS,
    load_all,
    pumping_window,
)

DS_SCALE = 1e6
OUT_JSON = FIG_DIR / "pumping_streamflow_impact.json"
SUMMARY_MD = ROOT / "analysis" / "pumping_streamflow_impact_summary.md"


def _year_slices(t: np.ndarray):
    """Indices for pump years 1, 2, 3 (t in years from onset)."""
    out = {}
    for y in range(1, PUMP_YEARS + 1):
        mask = (t >= y - 1) & (t < y)
        out[y] = np.where(mask)[0]
    return out


def _safe_ratio(q, qb):
    """Q / Qb with zeros in baseline → nan."""
    qb = np.asarray(qb, dtype=float)
    q = np.asarray(q, dtype=float)
    out = np.full_like(q, np.nan, dtype=float)
    ok = np.isfinite(q) & np.isfinite(qb) & (qb > 0)
    out[ok] = q[ok] / qb[ok]
    return out


def _pct(a, p):
    a = np.asarray(a, dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return float("nan")
    return float(np.percentile(a, p))


def summarize(series) -> dict:
    """Per domain/rate/year: mean/p50/p90 Q ratios, mean ΔQ, mean ΔS."""
    rows = []
    by_domain = {}
    for d in DOMAINS:
        by_domain[d] = {}
        bl = series[d]["_baseline"]
        for rate in RATES:
            w = pumping_window(series[d][rate], bl)
            slices = _year_slices(w["t"])
            rate_key = f"{rate:.0e}"
            by_domain[d][rate_key] = {"by_year": {}, "full": {}}
            # full 3-yr window
            r_full = _safe_ratio(w["Q"], w["Qb"])
            full = {
                "r_mean": float(np.nanmean(r_full)),
                "r_p50": _pct(r_full, 50),
                "r_p90": _pct(r_full, 90),
                "r_max": _pct(r_full, 100),
                "dQ_mean": float(np.nanmean(w["dQ"])),
                "dS_mean_1e6": float(np.nanmean(w["dS"])),
                "dS_end_1e6": float(w["dS"][-1]),
                "dQ_end": float(w["dQ"][-1]),
            }
            by_domain[d][rate_key]["full"] = full
            for y, idx in slices.items():
                if idx.size == 0:
                    continue
                r = _safe_ratio(w["Q"][idx], w["Qb"][idx])
                rec = {
                    "year": y,
                    "r_mean": float(np.nanmean(r)),
                    "r_p50": _pct(r, 50),
                    "r_p90": _pct(r, 90),
                    "r_max": _pct(r, 100),
                    "dQ_mean": float(np.nanmean(w["dQ"][idx])),
                    "dS_mean_1e6": float(np.nanmean(w["dS"][idx])),
                    "dS_end_1e6": float(w["dS"][idx[-1]]),
                }
                by_domain[d][rate_key]["by_year"][str(y)] = rec
                rows.append(
                    {
                        "domain": d,
                        "rate": rate_key,
                        "year": y,
                        **{k: rec[k] for k in rec if k != "year"},
                    }
                )
    return {"by_domain": by_domain, "rows": rows}


def fig_q_ratio_timeseries(series):
    """Outlet Q / baseline through pumping, by rate."""
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5), sharex="col", constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.04, hspace=0.08, wspace=0.04)
    for col, d in enumerate(DOMAINS):
        bl = series[d]["_baseline"]
        ax_r, ax_dq = axes[0, col], axes[1, col]
        for rate in RATES:
            w = pumping_window(series[d][rate], bl)
            r = _safe_ratio(w["Q"], w["Qb"])
            ax_r.plot(w["t"], r, color=COLORS[rate], lw=1.4, label=RATE_LABELS[rate])
            ax_dq.plot(w["t"], w["dQ"], color=COLORS[rate], lw=1.4, label=RATE_LABELS[rate])
        ax_r.axhline(1.0, color="k", lw=0.7)
        ax_dq.axhline(0.0, color="k", lw=0.7)
        for ax in (ax_r, ax_dq):
            ax.axvline(0, color="k", ls="--", lw=0.8)
            ax.axvspan(0, PUMP_YEARS, color="C3", alpha=0.08)
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_locator(MultipleLocator(1))
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax_r.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        # sharey on ratio row only (absolute ΔQ scales differ by domain)
        if col == 1:
            axes[0, 1].sharey(axes[0, 0])
    axes[0, 0].set_ylabel("Outlet Q / baseline", fontsize=LABEL_FS)
    axes[1, 0].set_ylabel("Δ outlet flow (m³/h)", fontsize=LABEL_FS)
    # keep 1 in view on ratio row
    lo, hi = axes[0, 0].get_ylim()
    axes[0, 0].set_ylim(min(lo, 1.0), max(hi, 1.0))
    for col in range(2):
        lo, hi = axes[1, col].get_ylim()
        axes[1, col].set_ylim(min(lo, 0.0), max(hi, 0.0))
    fig.supxlabel("Years into pumping", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=COLORS[r], lw=1.4, label=RATE_LABELS[r]) for r in RATES]
    handles.append(Patch(facecolor="C3", alpha=0.25, edgecolor="none", label="pumping"))
    fig.legend(handles=handles, loc="outside upper center", ncol=5, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_streamflow_q_ratio.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_q_ratio_bars(summary: dict):
    """Mean / p50 / p90 Q ratio by rate for pump year 3 (and year 1 for contrast)."""
    metrics = [("r_mean", "Mean"), ("r_p50", "p50"), ("r_p90", "p90")]
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.2), sharey="row", constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.08, w_pad=0.04, hspace=0.12, wspace=0.04)
    x = np.arange(len(RATES))
    width = 0.28
    metric_colors = ["#E8C39E", "#B86B2B", "#4A2410"]
    for col, d in enumerate(DOMAINS):
        for row, year in enumerate((1, 3)):
            ax = axes[row, col]
            for i, (key, lab) in enumerate(metrics):
                vals = []
                for rate in RATES:
                    rec = summary["by_domain"][d][f"{rate:.0e}"]["by_year"][str(year)]
                    vals.append(rec[key])
                ax.bar(
                    x + (i - 1) * width,
                    vals,
                    width=width,
                    color=metric_colors[i],
                    edgecolor="0.2",
                    linewidth=0.6,
                    label=lab if col == 0 and row == 0 else None,
                )
            ax.axhline(1.0, color="k", lw=0.7)
            ax.set_xticks(x)
            ax.set_xticklabels([RATE_LABELS[r] for r in RATES])
            ax.grid(True, axis="y", alpha=0.3)
            if row == 0:
                ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
            if col == 0:
                ax.set_ylabel(f"Pump yr {year}: Q / baseline", fontsize=LABEL_FS)
    handles = [
        Patch(facecolor="#E8C39E", edgecolor="0.2", label="Mean"),
        Patch(facecolor="#B86B2B", edgecolor="0.2", label="p50"),
        Patch(facecolor="#4A2410", edgecolor="0.2", label="p90"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=3, fontsize=LEGEND_FS, frameon=False)
    fig.supxlabel("Pumping rate (m/h domain-avg)", fontsize=LABEL_FS)
    out = FIG_DIR / "pumping_streamflow_q_ratio_bars.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_dq_vs_ds(series):
    """ΔQ vs ΔS through pumping — does flow track storage loss?"""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        bl = series[d]["_baseline"]
        for rate in RATES:
            w = pumping_window(series[d][rate], bl)
            # downsample for clarity
            step = max(1, len(w["t"]) // 80)
            ax.plot(
                w["dS"][::step],
                w["dQ"][::step],
                color=COLORS[rate],
                lw=1.5,
                label=RATE_LABELS[rate],
            )
            ax.scatter(
                [w["dS"][-1]],
                [w["dQ"][-1]],
                color=COLORS[rate],
                s=36,
                zorder=3,
                edgecolors="0.15",
                linewidths=0.5,
            )
        ax.axhline(0, color="k", lw=0.6)
        ax.axvline(0, color="k", lw=0.6)
        ax.grid(True, alpha=0.3)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.ticklabel_format(axis="both", style="plain", useOffset=False)
        if col == 0:
            ax.set_ylabel("Δ outlet flow (m³/h)", fontsize=LABEL_FS)
    fig.supxlabel("Δ storage (10⁶ m³)", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=COLORS[r], lw=1.5, label=RATE_LABELS[r]) for r in RATES]
    handles.append(
        Line2D(
            [0],
            [0],
            marker="o",
            color="0.3",
            lw=0,
            markersize=6,
            label="end of pump yr 3",
        )
    )
    fig.legend(handles=handles, loc="outside upper center", ncol=5, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_streamflow_dq_vs_ds.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_year_progression(summary: dict):
    """Mean Q ratio across pump years 1→3 — plateau vs continued decline."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.0), sharey=True, constrained_layout=True)
    years = [1, 2, 3]
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        for rate in RATES:
            vals = [
                summary["by_domain"][d][f"{rate:.0e}"]["by_year"][str(y)]["r_mean"]
                for y in years
            ]
            ax.plot(
                years,
                vals,
                color=COLORS[rate],
                lw=1.8,
                marker="o",
                markersize=5,
                label=RATE_LABELS[rate],
            )
        ax.axhline(1.0, color="k", lw=0.7)
        ax.set_xticks(years)
        ax.set_xlabel("Pump year", fontsize=LABEL_FS)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.grid(True, alpha=0.3)
        if col == 0:
            ax.set_ylabel("Mean outlet Q / baseline", fontsize=LABEL_FS)
    lo, hi = axes[0].get_ylim()
    axes[0].set_ylim(min(lo, 1.0), max(hi, 1.0))
    handles = [Line2D([0], [0], color=COLORS[r], lw=1.8, marker="o", label=RATE_LABELS[r]) for r in RATES]
    fig.legend(handles=handles, loc="outside upper center", ncol=4, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_streamflow_q_ratio_by_year.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def write_summary(summary: dict):
    lines = [
        "# Pumping impact on streamflow (preliminary)",
        "",
        "**Date:** August 2026  ",
        "**Script:** [`pumping_streamflow_impact.py`](pumping_streamflow_impact.py)  ",
        "**Question:** How does 3-year pumping change outlet streamflow vs average-year baseline, "
        "and does Q track deep storage loss the way drought Q did not?",
        "",
        "No recovery years on disk yet — metrics are **during pumping** only.",
        "",
        "## Figures",
        "",
        "- [pumping_streamflow_q_ratio.png](figures/pumping_streamflow_q_ratio.png)",
        "- [pumping_streamflow_q_ratio_bars.png](figures/pumping_streamflow_q_ratio_bars.png)",
        "- [pumping_streamflow_q_ratio_by_year.png](figures/pumping_streamflow_q_ratio_by_year.png)",
        "- [pumping_streamflow_dq_vs_ds.png](figures/pumping_streamflow_dq_vs_ds.png)",
        "- Existing context: [pumping_during_totals_and_anomalies.png](figures/pumping_during_totals_and_anomalies.png), "
        "[pumping_course_streamflow_storage.png](figures/pumping_course_streamflow_storage.png)",
        "",
        "## Mean outlet Q / baseline by pump year",
        "",
        "| Domain | Rate | Yr1 | Yr2 | Yr3 |",
        "|--------|------|----:|----:|----:|",
    ]
    for d in DOMAINS:
        for rate in RATES:
            ys = [
                summary["by_domain"][d][f"{rate:.0e}"]["by_year"][str(y)]["r_mean"]
                for y in (1, 2, 3)
            ]
            lines.append(
                f"| {DOMAIN_LABELS[d]} | {rate:.0e} | "
                f"{ys[0]:.3f} | {ys[1]:.3f} | {ys[2]:.3f} |"
            )

    lines += [
        "",
        "## Pump year 3 percentiles (Q / baseline)",
        "",
        "| Domain | Rate | Mean | p50 | p90 | End ΔS (10⁶ m³) |",
        "|--------|------|-----:|----:|----:|----------------:|",
    ]
    for d in DOMAINS:
        for rate in RATES:
            rec = summary["by_domain"][d][f"{rate:.0e}"]["by_year"]["3"]
            dS = summary["by_domain"][d][f"{rate:.0e}"]["full"]["dS_end_1e6"]
            lines.append(
                f"| {DOMAIN_LABELS[d]} | {rate:.0e} | "
                f"{rec['r_mean']:.3f} | {rec['r_p50']:.3f} | {rec['r_p90']:.3f} | "
                f"{dS:.0f} |"
            )

    # takeaways from numbers
    takeaways = []
    for d in DOMAINS:
        r_hi = summary["by_domain"][d]["1e-05"]["by_year"]["3"]["r_mean"]
        r_lo = summary["by_domain"][d]["1e-07"]["by_year"]["3"]["r_mean"]
        r1 = summary["by_domain"][d]["1e-05"]["by_year"]["1"]["r_mean"]
        r3 = summary["by_domain"][d]["1e-05"]["by_year"]["3"]["r_mean"]
        takeaways.append(
            f"- **{DOMAIN_LABELS[d]}** at 1e-5: mean Q/baseline yr1={r1:.2f}, yr3={r3:.2f} "
            f"(1e-7 yr3={r_lo:.2f})."
        )
        # continued decline?
        if r3 < r1 - 0.02:
            takeaways.append(
                f"- **{DOMAIN_LABELS[d]}** (1e-5): mean Q keeps falling from yr1→yr3 "
                f"(not a pure mid-drought plateau)."
            )
        else:
            takeaways.append(
                f"- **{DOMAIN_LABELS[d]}** (1e-5): mean Q is roughly flat yr1→yr3 "
                f"despite growing ΔS — drought-like decoupling."
            )

    lines += [
        "",
        "## Takeaways (early)",
        "",
        *takeaways,
        "- Low rates (1e-7) leave outlet Q near baseline; high rates (1e-4) strongly suppress flow.",
        "- Contrast with 50-yr drought: there, deep storage grew for decades while Q plateaued. "
        "Under pumping, check whether ΔQ tracks ΔS in `pumping_streamflow_dq_vs_ds.png` — "
        "capture-style coupling can appear even without drying the precip forcing.",
        "- Outlet p10≈0 on baseline still limits classical baseflow ratios (same caveat as drought).",
        "- Recovery years will show whether Q rebounds with the near-surface skin or stays suppressed "
        "with deep memory.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "conda activate /glade/work/bwest/conda-envs/droughts",
        "cd /glade/derecho/scratch/bwest/drought-ensemble",
        "python analysis/pumping_streamflow_impact.py",
        "```",
        "",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n")
    print("wrote", SUMMARY_MD)


def main():
    print("Loading pumping + baseline series…", flush=True)
    series, _paths = load_all()
    summary = summarize(series)
    OUT_JSON.write_text(json.dumps(summary, indent=2))
    print("wrote", OUT_JSON)

    fig_q_ratio_timeseries(series)
    fig_q_ratio_bars(summary)
    fig_year_progression(summary)
    fig_dq_vs_ds(series)
    write_summary(summary)


if __name__ == "__main__":
    main()
