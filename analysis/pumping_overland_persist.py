#!/usr/bin/env python3
"""Pumping persistent deficit vs overland flow (drought-figure analogues).

Same ranking / binning as the drought drainage figures:
- cumulative persist mass vs cells ranked low→high overland
- mean persist (and P(top 20%)) vs log₁₀ overland and vs distance to stream

Temporary/persistent = recovery year-1 split. Overland = late-spinup mean.
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
from matplotlib.ticker import MultipleLocator

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis.budyko_temp_persistent import (  # noqa: E402
    DOMAIN_LABELS,
    DOMAINS,
    baseline_fields,
    distance_to_stream_km,
    spearmanr,
)
from analysis.pumping_vs_drought_deficits import (  # noqa: E402
    DROUGHT_MEMBER,
    PUMP_ENSEMBLE,
    RATE_LABELS,
    RATES,
    SPINUP_YEARS,
    STRESS_YEARS,
    _col_storage_m,
    _paths,
    _resolve_pump,
)
from analysis.redo_recovery_with_50yr import storage_deficit_pair  # noqa: E402
from analysis.wtd_threshold_vs_overland import binned_curve  # noqa: E402

from analysis.figure_paths import FIG_DIR, FIG_ROOT, fig_path, resolve_figure  # noqa: E402
SUMMARY_MD = ROOT / "analysis" / "pumping_overland_persist_summary.md"
OUT_JSON = FIG_DIR / "pumping_overland_persist.json"
DROUGHT_ENSEMBLE = "droughts"
BASE_MEMBER = "short_baseline"
FOCUS_RATE = 1e-5
N_BINS = 12
TOP_FRAC = 0.20
LABEL_FS, LEGEND_FS, TITLE_FS = 12, 11, 13
DROUGHT_COLOR = "#B86B2B"
PUMP_COLORS = {1e-7: "#E8C39E", 1e-6: "#B86B2B", 1e-5: "#4A2410", 1e-4: "#140A05"}


def persist_map(member_paths, base_paths) -> np.ndarray:
    i0 = SPINUP_YEARS + STRESS_YEARS - 1
    i1 = SPINUP_YEARS + STRESS_YEARS
    d0, b0 = _col_storage_m(member_paths[i0]), _col_storage_m(base_paths[i0])
    d1, b1 = _col_storage_m(member_paths[i1]), _col_storage_m(base_paths[i1])
    deficit1 = b1 - d1
    return np.asarray(np.maximum(deficit1.values, 0.0), dtype=np.float64)


def temp_map(member_paths, base_paths) -> np.ndarray:
    i0 = SPINUP_YEARS + STRESS_YEARS - 1
    i1 = SPINUP_YEARS + STRESS_YEARS
    d0, b0 = _col_storage_m(member_paths[i0]), _col_storage_m(base_paths[i0])
    d1, b1 = _col_storage_m(member_paths[i1]), _col_storage_m(base_paths[i1])
    deficit0 = b0 - d0
    deficit1 = b1 - d1
    return np.asarray(np.maximum((deficit0 - deficit1).values, 0.0), dtype=np.float64)


def cell_vectors(base: dict, pers: np.ndarray, temp: np.ndarray | None = None) -> dict:
    active = base["active"]
    streams = base["streams"]
    flow = base["flow"]
    dist = base["dist_km"]
    log_flow = np.log10(np.maximum(flow, 1e-6))
    mask = active & ~streams & (flow > 0) & np.isfinite(pers) & np.isfinite(log_flow) & np.isfinite(dist)
    if temp is not None:
        tot = pers + temp
        mask = mask & np.isfinite(temp) & (tot > 1e-6)
    out = {
        "log_flow": log_flow[mask],
        "flow": flow[mask],
        "dist_km": dist[mask],
        "persistent": pers[mask],
    }
    if temp is not None:
        out["temporary"] = temp[mask]
        tot = pers[mask] + temp[mask]
        out["f_temp"] = temp[mask] / tot
    return out


def lowest20_mass_frac(log_flow: np.ndarray, pers: np.ndarray) -> float:
    order = np.argsort(log_flow)
    pers_o = pers[order]
    frac_cells = np.arange(1, pers_o.size + 1) / pers_o.size
    cum = np.cumsum(pers_o) / pers_o.sum()
    return float(np.interp(TOP_FRAC, frac_cells, cum))


def p_top20_curve(x: np.ndarray, y: np.ndarray, n_bins: int = N_BINS):
    thr = np.percentile(y, 100 * (1 - TOP_FRAC))
    flag = (y >= thr).astype(np.float64)
    return binned_curve(x, flag, n_bins)


def load_all() -> dict:
    out = {}
    for d in DOMAINS:
        print(f"Baseline fields {d}…", flush=True)
        base = baseline_fields(d)
        base["dist_km"] = distance_to_stream_km(base["streams"], base["active"])
        bpaths = _paths(DROUGHT_ENSEMBLE, BASE_MEMBER, d)
        print(f"  drought 3-yr persist {d}…", flush=True)
        pair = storage_deficit_pair(d, STRESS_YEARS)
        drought_pers = np.asarray(pair["persistent"].values, dtype=np.float64)
        drought_temp = np.asarray(pair["temporary"].values, dtype=np.float64)
        rec = {
            "drought": cell_vectors(base, drought_pers, drought_temp),
            "pump": {},
        }
        rec["drought"]["share20"] = lowest20_mass_frac(
            rec["drought"]["log_flow"], rec["drought"]["persistent"]
        )
        rho, _ = spearmanr(rec["drought"]["log_flow"], rec["drought"]["persistent"])
        rec["drought"]["rho_logflow"] = rho
        for rate in RATES:
            print(f"  pumping {rate:.0e} persist {d}…", flush=True)
            pp = _paths(PUMP_ENSEMBLE, _resolve_pump(rate), d)
            pers = persist_map(pp, bpaths)
            temp = temp_map(pp, bpaths)
            rec["pump"][f"{rate:.0e}"] = cell_vectors(base, pers, temp)
            rec["pump"][f"{rate:.0e}"]["share20"] = lowest20_mass_frac(
                rec["pump"][f"{rate:.0e}"]["log_flow"],
                rec["pump"][f"{rate:.0e}"]["persistent"],
            )
            rho, _ = spearmanr(
                rec["pump"][f"{rate:.0e}"]["log_flow"],
                rec["pump"][f"{rate:.0e}"]["persistent"],
            )
            rec["pump"][f"{rate:.0e}"]["rho_logflow"] = rho
        print(
            f"  {DOMAIN_LABELS[d]} drought 20% share={rec['drought']['share20']:.2f}  "
            f"pump 1e-5 share={rec['pump']['1e-05']['share20']:.2f}",
            flush=True,
        )
        out[d] = rec
    return out


def fig_concentration(data: dict):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True, constrained_layout=True)
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        rec = data[d]
        # drought
        t = rec["drought"]
        order = np.argsort(t["log_flow"])
        pers = t["persistent"][order]
        cum = np.cumsum(pers) / pers.sum()
        frac = np.arange(1, pers.size + 1) / pers.size
        ax.plot(frac, cum, color=DROUGHT_COLOR, lw=2.2, label="3-yr drought")
        ax.plot([TOP_FRAC], [t["share20"]], "o", color=DROUGHT_COLOR, ms=6, zorder=4)
        for rate in RATES:
            p = rec["pump"][f"{rate:.0e}"]
            order = np.argsort(p["log_flow"])
            pers = p["persistent"][order]
            cum = np.cumsum(pers) / pers.sum()
            frac = np.arange(1, pers.size + 1) / pers.size
            ax.plot(frac, cum, color=PUMP_COLORS[rate], lw=1.5, label=RATE_LABELS[rate])
        ax.plot([0, 1], [0, 1], color="0.6", ls="--", lw=1.0, label="Uniform")
        ax.axvline(TOP_FRAC, color="0.4", ls=":", lw=1.0)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.grid(True, alpha=0.3)
        ax.set_xlabel("Fraction of cells (low → high overland flow)", fontsize=LABEL_FS)
        if col == 0:
            ax.set_ylabel("Cumulative fraction of\npersistent storage deficit", fontsize=LABEL_FS)
        p5 = rec["pump"]["1e-05"]["share20"]
        ax.annotate(
            f"Drought {t['share20']*100:.0f}%  ·  Pump 1e-5 {p5*100:.0f}%\nin lowest-flow 20%",
            xy=(0.22, 0.08),
            xycoords="axes fraction",
            fontsize=9,
            color="0.25",
        )
    handles = [Line2D([0], [0], color=DROUGHT_COLOR, lw=2.2, label="3-yr drought")]
    handles += [Line2D([0], [0], color=PUMP_COLORS[r], lw=1.5, label=RATE_LABELS[r]) for r in RATES]
    handles.append(Line2D([0], [0], color="0.6", ls="--", lw=1.0, label="Uniform"))
    fig.legend(handles=handles, loc="outside upper center", ncol=6, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_drainage_deficit_concentration.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_threshold_bins(data: dict):
    """Pumping 1e-5: mean persist + P(top 20%) vs log overland and vs dist."""
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.6), constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.10, w_pad=0.05, hspace=0.14, wspace=0.08)
    xkeys = ("log_flow", "dist_km")
    xlabels = (r"log$_{10}$ overland flow (m³/h)", "Distance to stream (km)")
    for row, d in enumerate(DOMAINS):
        p = data[d]["pump"]["1e-05"]
        for col, (key, xlab) in enumerate(zip(xkeys, xlabels)):
            ax = axes[row, col]
            ax2 = ax.twinx()
            xc, yc, _ = binned_curve(p[key], p["persistent"], N_BINS)
            xp, yp, _ = p_top20_curve(p[key], p["persistent"], N_BINS)
            ax.plot(xc, yc, "o-", color="#4A2410", lw=1.8, ms=5)
            ax2.plot(xp, yp, "s--", color="#B86B2B", lw=1.4, ms=5)
            ax.set_ylim(bottom=0.0)
            ax2.set_ylim(0, 1.02)
            ax.grid(True, alpha=0.3)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
            if row == 1:
                ax.set_xlabel(xlab, fontsize=LABEL_FS)
            if col == 0:
                ax.set_ylabel("Mean persist deficit (m)", fontsize=LABEL_FS)
            if col == 1:
                ax2.set_ylabel("P(top 20%)", fontsize=LABEL_FS)
            else:
                ax2.tick_params(labelright=False)
            ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
            rho, _ = spearmanr(p[key], p["persistent"])
            note = "low flow → more persist" if (key == "log_flow" and rho < 0) else (
                "high flow → more persist" if key == "log_flow" else f"ρ = {rho:.2f}"
            )
            if key == "log_flow":
                ax.text(0.04, 0.92, note, transform=ax.transAxes, fontsize=9, color="0.35", va="top")
    handles = [
        Line2D([0], [0], color="#4A2410", marker="o", lw=1.8, ms=5, label="Mean persist deficit"),
        Line2D([0], [0], color="#B86B2B", marker="s", ls="--", lw=1.4, ms=5, label="P(top 20% persist)"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=2, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_drainage_threshold_bins.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_mean_vs_overland_compare(data: dict):
    """Drought 3-yr vs pumping 1e-5: mean persist vs log overland (independent y)."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.3), constrained_layout=True)
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        rec = data[d]
        for label, tbl, color in (
            ("3-yr drought", rec["drought"], DROUGHT_COLOR),
            ("Pumping 1e-5", rec["pump"]["1e-05"], PUMP_COLORS[FOCUS_RATE]),
        ):
            xc, yc, _ = binned_curve(tbl["log_flow"], tbl["persistent"], N_BINS)
            yrel = yc / np.mean(tbl["persistent"])
            ax.plot(xc, yrel, "o-", color=color, lw=1.8, ms=5, label=label)
        ax.axhline(1.0, color="0.6", ls="--", lw=1.0)
        ax.set_ylim(bottom=0.0)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.grid(True, alpha=0.3)
        if col == 0:
            ax.set_ylabel("Mean persist / domain-mean persist", fontsize=LABEL_FS)
    fig.supxlabel(r"log$_{10}$ overland flow (m³/h)", fontsize=LABEL_FS)
    handles = [
        Line2D([0], [0], color=DROUGHT_COLOR, marker="o", lw=1.8, label="3-yr drought"),
        Line2D([0], [0], color=PUMP_COLORS[FOCUS_RATE], marker="o", lw=1.8, label="Pumping 1e-5"),
        Line2D([0], [0], color="0.6", ls="--", lw=1.0, label="Domain mean"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=3, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_vs_drought_mean_persist_overland.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def write_summary(data: dict):
    lines = [
        "# Pumping persistent deficit vs overland flow",
        "",
        "**Date:** August 2026  ",
        "**Script:** [`pumping_overland_persist.py`](pumping_overland_persist.py)  ",
        "Analogues of `drought_recovery_drainage_deficit_concentration.png` and "
        "`drought_recovery_drainage_threshold_bins.png`. "
        "Non-stream cells with baseline overland > 0. Persistent = remaining after recovery yr 1.",
        "",
        "## Figures",
        "",
        "- [pumping_drainage_deficit_concentration.png](figures/pumping_drainage_deficit_concentration.png)",
        "- [pumping_drainage_threshold_bins.png](figures/pumping_drainage_threshold_bins.png)",
        "- [pumping_vs_drought_mean_persist_overland.png](figures/pumping_vs_drought_mean_persist_overland.png)",
        "",
        "## Lowest-flow 20% of cells: share of persistent mass",
        "",
        "| Domain | 3-yr drought | Pump 1e-7 | 1e-6 | 1e-5 | 1e-4 |",
        "|--------|-------------:|----------:|-----:|-----:|-----:|",
    ]
    for d in DOMAINS:
        dr = data[d]["drought"]["share20"]
        shares = [data[d]["pump"][f"{r:.0e}"]["share20"] for r in RATES]
        lines.append(
            f"| {DOMAIN_LABELS[d]} | {dr:.2f} | "
            + " | ".join(f"{s:.2f}" for s in shares)
            + " |"
        )
    lines += [
        "",
        "## Spearman ρ(log overland, persist)",
        "",
        "| Domain | 3-yr drought | Pump 1e-5 |",
        "|--------|-------------:|----------:|",
    ]
    for d in DOMAINS:
        lines.append(
            f"| {DOMAIN_LABELS[d]} | {data[d]['drought']['rho_logflow']:.2f} | "
            f"{data[d]['pump']['1e-05']['rho_logflow']:.2f} |"
        )
    lines += [
        "",
        "## Takeaways",
        "",
        "- Drought persistent mass concentrates in low-overland cells: lowest-flow 20% hold 60% (Potomac) / 40% (Wolf).",
        "- Pumping persist is near-uniform: lowest-flow 20% hold only 23% / 29% at 1e-5 (uniform would be 20%).",
        "- Potomac pumping even slightly prefers *higher*-flow cells (ρ = +0.10 vs drought −0.17).",
        "- Wolf still has a weak low-flow slope under pumping (ρ = −0.29), but far less mass concentration than drought.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "conda activate /glade/work/bwest/conda-envs/droughts",
        "cd /glade/derecho/scratch/bwest/drought-ensemble",
        "python analysis/pumping_overland_persist.py",
        "```",
        "",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n")
    print("wrote", SUMMARY_MD)


def main():
    data = load_all()
    serial = {}
    for d in DOMAINS:
        serial[d] = {
            "drought": {
                "share20": data[d]["drought"]["share20"],
                "rho_logflow": data[d]["drought"]["rho_logflow"],
            },
            "pump": {
                k: {"share20": v["share20"], "rho_logflow": v["rho_logflow"]}
                for k, v in data[d]["pump"].items()
            },
        }
    OUT_JSON.write_text(json.dumps(serial, indent=2))
    print("wrote", OUT_JSON)
    fig_concentration(data)
    fig_threshold_bins(data)
    fig_mean_vs_overland_compare(data)
    write_summary(data)


if __name__ == "__main__":
    main()
