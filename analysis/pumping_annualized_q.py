#!/usr/bin/env python3
"""Annualized outlet Q through 3-year pumping + 10-year recovery.

Uses native 219 h products (53 years). Annualized Q = yearly-mean outlet
overland flow, reported as 10⁶ m³/yr (mean m³/h × 8760).
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
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis import outlet_flow as OF  # noqa: E402
from analysis.paper_figures import utils  # noqa: E402

PUMP_ENSEMBLE = "3_year_pumping_tests"
BASE_ENSEMBLE = "droughts"
DOMAINS = ["potomac2", "wolf2"]
DOMAIN_LABELS = {"potomac2": "Potomac", "wolf2": "Wolf"}
RATES = [1e-7, 1e-6, 1e-5, 1e-4]
RATE_LABELS = {r: f"{r:.0e}" for r in RATES}
SPINUP_YEARS = 40
PUMP_YEARS = 3
RECOVERY_YEARS = 10
N_YEARS = SPINUP_YEARS + PUMP_YEARS + RECOVERY_YEARS
INTERVAL = 219
HOURS_PER_YEAR = 8760
Q_SCALE = 1e6  # plot as 10⁶ m³/yr

from analysis.figure_paths import FIG_DIR, FIG_ROOT, fig_path, resolve_figure  # noqa: E402
SUMMARY_MD = ROOT / "analysis" / "pumping_annualized_q_summary.md"
OUT_JSON = FIG_DIR / "pumping_annualized_q.json"
FIG_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {1e-7: "#E8C39E", 1e-6: "#B86B2B", 1e-5: "#4A2410", 1e-4: "#140A05"}
LABEL_FS, LEGEND_FS, TITLE_FS = 12, 11, 13
PRE_YEARS = 3  # last spinup years on the course plot

OUTLETS = {_d: OF.analysis_outlet(_d) for _d in DOMAINS}
for _d in DOMAINS:
    print(_d, "outlet", OUTLETS[_d], flush=True)


def _resolve_member(rate: float) -> str:
    return {
        1e-7: "pumping_1e-7",
        1e-6: "pumping_1e-6",
        1e-5: "pumping_1e-5",
        1e-4: "pumping_1e-4",
    }[rate]


def _paths(ensemble: str, member: str, domain: str) -> list[Path]:
    files = utils._file_locations(ensemble, member, domain, 0, interval=INTERVAL)
    return [Path(p) for p in files[:N_YEARS]]


def read_outlet(domain_name: str, paths: list[Path]) -> np.ndarray:
    """Yearly-mean outlet flow (m³/h), one value per year file."""
    ox, oy = OUTLETS[domain_name]
    q = np.empty(len(paths), dtype=np.float64)
    for i, path in enumerate(paths):
        q[i] = float(np.mean(OF.window_mean_outlet_flow(path, ox, oy)))
    return q


def annual_m3e6(q_m3h: np.ndarray) -> np.ndarray:
    return q_m3h * HOURS_PER_YEAR / Q_SCALE


def load_all() -> dict:
    data = {}
    for d in DOMAINS:
        data[d] = {}
        print(f"Loading baseline {d}/short_baseline…", flush=True)
        data[d]["_baseline"] = read_outlet(d, _paths(BASE_ENSEMBLE, "short_baseline", d))
        for rate in RATES:
            print(f"Loading {d}/{_resolve_member(rate)}…", flush=True)
            q = read_outlet(d, _paths(PUMP_ENSEMBLE, _resolve_member(rate), d))
            data[d][rate] = q
            print(f"  n={q.size}", flush=True)
    return data


def year_from_pump(i: np.ndarray | int) -> np.ndarray:
    return np.asarray(i, dtype=float) - SPINUP_YEARS + 0.5


def summarize(data: dict) -> dict:
    """Annualized Q / baseline at pump and recovery milestones."""
    i_end_pump = SPINUP_YEARS + PUMP_YEARS - 1
    keys = {
        "spinup_last": SPINUP_YEARS - 1,
        "pump_yr1": SPINUP_YEARS,
        "pump_yr2": min(SPINUP_YEARS + 1, i_end_pump),
        "pump_end": i_end_pump,
        "rec_yr1": SPINUP_YEARS + PUMP_YEARS,
    }
    if PUMP_YEARS >= 3:
        keys["pump_yr3"] = SPINUP_YEARS + 2
    if RECOVERY_YEARS >= 5:
        keys["rec_yr5"] = SPINUP_YEARS + PUMP_YEARS + 4
    if RECOVERY_YEARS >= 10:
        keys["rec_yr10"] = SPINUP_YEARS + PUMP_YEARS + 9
    out = {"by_domain": {}}
    for d in DOMAINS:
        out["by_domain"][d] = {}
        qb = data[d]["_baseline"]
        for rate in RATES:
            q = data[d][rate]
            rec = {}
            for name, i in keys.items():
                if i >= len(q) or i >= len(qb):
                    continue
                rec[name] = {
                    "Q_1e6m3yr": float(annual_m3e6(q[i])),
                    "Qb_1e6m3yr": float(annual_m3e6(qb[i])),
                    "ratio": float(q[i] / qb[i]) if qb[i] > 0 else float("nan"),
                }
            rec["pump_years"] = [
                float(q[SPINUP_YEARS + k] / qb[SPINUP_YEARS + k])
                for k in range(PUMP_YEARS)
            ]
            rec["recovery_years"] = [
                float(q[SPINUP_YEARS + PUMP_YEARS + k] / qb[SPINUP_YEARS + PUMP_YEARS + k])
                for k in range(RECOVERY_YEARS)
            ]
            out["by_domain"][d][f"{rate:.0e}"] = rec
    return out


def fig_course(data: dict):
    """Annualized Q and Q/baseline from last spinup years through recovery."""
    i0 = SPINUP_YEARS - PRE_YEARS
    i1 = N_YEARS
    idx = np.arange(i0, i1)
    t = year_from_pump(idx)

    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5), sharex="col", constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.04, hspace=0.08, wspace=0.04)
    for col, d in enumerate(DOMAINS):
        ax_q, ax_r = axes[0, col], axes[1, col]
        qb = annual_m3e6(data[d]["_baseline"][idx])
        ax_q.plot(t, qb, color="0.65", lw=1.2, label="baseline")
        for rate in RATES:
            q = annual_m3e6(data[d][rate][idx])
            r = data[d][rate][idx] / data[d]["_baseline"][idx]
            ax_q.plot(t, q, color=COLORS[rate], lw=1.6, marker="o", markersize=3.5, label=RATE_LABELS[rate])
            ax_r.plot(t, r, color=COLORS[rate], lw=1.6, marker="o", markersize=3.5, label=RATE_LABELS[rate])
        ax_r.axhline(1.0, color="k", lw=0.7)
        for ax in (ax_q, ax_r):
            ax.axvline(0, color="k", ls="--", lw=0.8)
            ax.axvline(PUMP_YEARS, color="k", ls=":", lw=0.8)
            ax.axvspan(0, PUMP_YEARS, color="C3", alpha=0.08)
            ax.axvspan(PUMP_YEARS, PUMP_YEARS + RECOVERY_YEARS, color="C0", alpha=0.05)
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_locator(MultipleLocator(2))
            ax.xaxis.set_minor_locator(MultipleLocator(1))
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax_q.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        _, q_hi = ax_q.get_ylim()
        ax_q.set_ylim(0.0, max(q_hi, 0.0))
        if col == 1:
            axes[1, 1].sharey(axes[1, 0])
    lo, hi = axes[1, 0].get_ylim()
    axes[1, 0].set_ylim(0.0, max(hi, 1.0))
    axes[0, 0].set_ylabel("Annualized outlet Q (10⁶ m³/yr)", fontsize=LABEL_FS)
    axes[1, 0].set_ylabel("Annualized Q / baseline", fontsize=LABEL_FS)
    fig.supxlabel("Year (from pumping start)", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=COLORS[r], lw=1.6, marker="o", markersize=3.5, label=RATE_LABELS[r]) for r in RATES]
    handles += [
        Line2D([0], [0], color="0.65", lw=1.2, label="baseline"),
        Patch(facecolor="C3", alpha=0.25, edgecolor="none", label="pumping"),
        Patch(facecolor="C0", alpha=0.18, edgecolor="none", label="recovery"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=7, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_annualized_q_course.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_ratio_recovery(data: dict):
    """Annualized Q/baseline with origin at recovery start; last pump year at −0.5."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True, constrained_layout=True)
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        qb = data[d]["_baseline"]
        t_pump = np.arange(PUMP_YEARS) + 0.5 - PUMP_YEARS  # −2.5, −1.5, −0.5
        t_rec = np.arange(RECOVERY_YEARS) + 0.5
        for rate in RATES:
            q = data[d][rate]
            r_pump = q[SPINUP_YEARS : SPINUP_YEARS + PUMP_YEARS] / qb[SPINUP_YEARS : SPINUP_YEARS + PUMP_YEARS]
            r_rec = (
                q[SPINUP_YEARS + PUMP_YEARS : SPINUP_YEARS + PUMP_YEARS + RECOVERY_YEARS]
                / qb[SPINUP_YEARS + PUMP_YEARS : SPINUP_YEARS + PUMP_YEARS + RECOVERY_YEARS]
            )
            ax.plot(t_pump, r_pump, color=COLORS[rate], lw=1.6, marker="o", markersize=4, ls="--")
            ax.plot(t_rec, r_rec, color=COLORS[rate], lw=1.6, marker="o", markersize=4, label=RATE_LABELS[rate])
        ax.axhline(1.0, color="k", lw=0.7)
        ax.axvline(0, color="k", ls="--", lw=0.8)
        ax.axvspan(-PUMP_YEARS, 0, color="C3", alpha=0.08)
        ax.axvspan(0, RECOVERY_YEARS, color="C0", alpha=0.05)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(MultipleLocator(2))
        ax.xaxis.set_minor_locator(MultipleLocator(1))
        if col == 0:
            ax.set_ylabel("Annualized Q / baseline", fontsize=LABEL_FS)
    lo, hi = axes[0].get_ylim()
    axes[0].set_ylim(0.0, max(hi, 1.0))
    fig.supxlabel("Year (from recovery start)", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=COLORS[r], lw=1.6, marker="o", label=RATE_LABELS[r]) for r in RATES]
    handles += [
        Patch(facecolor="C3", alpha=0.25, edgecolor="none", label="pumping"),
        Patch(facecolor="C0", alpha=0.18, edgecolor="none", label="recovery"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=6, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_annualized_q_ratio_recovery.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_milestones(summary: dict):
    """Annualized Q/baseline at pump start/end and available recovery milestones."""
    labels = ["pump yr1", f"pump yr{PUMP_YEARS}", "rec yr1"]
    keys = ["pump_yr1", "pump_end", "rec_yr1"]
    if RECOVERY_YEARS >= 5:
        labels.append("rec yr5")
        keys.append("rec_yr5")
    if RECOVERY_YEARS >= 10:
        labels.append("rec yr10")
        keys.append("rec_yr10")
    x = np.arange(len(labels))
    width = 0.18
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True, constrained_layout=True)
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        for i, rate in enumerate(RATES):
            rec = summary["by_domain"][d][f"{rate:.0e}"]
            vals = []
            for k in keys:
                if k in rec:
                    vals.append(rec[k]["ratio"])
                elif k == "pump_end" and "pump_yr3" in rec:
                    vals.append(rec["pump_yr3"]["ratio"])
                else:
                    vals.append(float("nan"))
            ax.bar(
                x + (i - 1.5) * width,
                vals,
                width=width,
                color=COLORS[rate],
                edgecolor="0.2",
                linewidth=0.4,
                label=RATE_LABELS[rate],
            )
        ax.axhline(1.0, color="k", lw=0.7)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.grid(True, axis="y", alpha=0.3)
        if col == 0:
            ax.set_ylabel("Annualized Q / baseline", fontsize=LABEL_FS)
    lo, hi = axes[0].get_ylim()
    axes[0].set_ylim(0.0, max(hi, 1.05))
    handles = [Patch(facecolor=COLORS[r], edgecolor="0.2", label=RATE_LABELS[r]) for r in RATES]
    fig.legend(handles=handles, loc="outside upper center", ncol=4, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_annualized_q_milestones.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def write_summary(summary: dict):
    def _name(stem: str) -> str:
        try:
            from analysis.pumping_stress_settings import out_name

            return out_name(stem)
        except Exception:
            return stem

    rec_keys = ["rec_yr1"]
    if RECOVERY_YEARS >= 5:
        rec_keys.append("rec_yr5")
    if RECOVERY_YEARS >= 10:
        rec_keys.append("rec_yr10")
    header = (
        "| Domain | Rate | Pump yr1 | "
        + f"Pump yr{PUMP_YEARS} | "
        + " | ".join(k.replace("_", " ").title() for k in rec_keys)
        + " |"
    )
    lines = [
        "# Annualized outlet Q through pumping and recovery",
        "",
        f"**Script:** [`pumping_annualized_q.py`](pumping_annualized_q.py)  ",
        "Annualized Q = yearly-mean outlet overland flow × 8760 h, as 10⁶ m³/yr.  ",
        f"Sequence: 40 yr average spinup + **{PUMP_YEARS} yr pumping** + "
        f"**{RECOVERY_YEARS} yr recovery** (average forcing).",
        "",
        "## Figures",
        "",
        f"- [{_name('pumping_annualized_q_course.png')}](figures/{_name('pumping_annualized_q_course.png')})",
        f"- [{_name('pumping_annualized_q_ratio_recovery.png')}](figures/{_name('pumping_annualized_q_ratio_recovery.png')})",
        f"- [{_name('pumping_annualized_q_milestones.png')}](figures/{_name('pumping_annualized_q_milestones.png')})",
        "",
        "## Annualized Q / baseline",
        "",
        header,
        "|--------|------|---------:|" + "---------:|" * (1 + len(rec_keys)),
    ]
    for d in DOMAINS:
        for rate in RATES:
            rec = summary["by_domain"][d][f"{rate:.0e}"]
            end_r = rec.get("pump_end", rec.get("pump_yr3", {})).get("ratio", float("nan"))
            cols = [f"{rec['pump_yr1']['ratio']:.3f}", f"{end_r:.3f}"]
            for k in rec_keys:
                cols.append(f"{rec[k]['ratio']:.3f}" if k in rec else "—")
            lines.append(
                f"| {DOMAIN_LABELS[d]} | {rate:.0e} | " + " | ".join(cols) + " |"
            )

    lines += ["", "## Takeaways", ""]
    for d in DOMAINS:
        r = summary["by_domain"][d]["1e-05"]
        end_r = r.get("pump_end", r.get("pump_yr3", {})).get("ratio", float("nan"))
        bits = [
            f"pump yr1={r['pump_yr1']['ratio']:.2f}",
            f"yr{PUMP_YEARS}={end_r:.2f}",
            f"rec yr1={r['rec_yr1']['ratio']:.2f}",
        ]
        if "rec_yr5" in r:
            bits.append(f"yr5={r['rec_yr5']['ratio']:.2f}")
        if "rec_yr10" in r:
            bits.append(f"yr10={r['rec_yr10']['ratio']:.2f}")
        lines.append(f"- **{DOMAIN_LABELS[d]}** 1e-5: " + ", ".join(bits) + ".")
    lines += [
        "- Low rates (1e-7 / 1e-6) stay near baseline through pumping and recovery.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "conda activate /glade/work/bwest/conda-envs/droughts",
        "cd /glade/derecho/scratch/bwest/drought-ensemble",
        "PUMPING_STRESS_YEARS=10 python analysis/run_10yr_pumping_analyses.py annualized_q",
        "```",
        "",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n")
    print("wrote", SUMMARY_MD)


def main():
    data = load_all()
    summary = summarize(data)
    OUT_JSON.write_text(json.dumps(summary, indent=2))
    print("wrote", OUT_JSON)
    fig_course(data)
    fig_ratio_recovery(data)
    fig_milestones(summary)
    write_summary(summary)


if __name__ == "__main__":
    main()
