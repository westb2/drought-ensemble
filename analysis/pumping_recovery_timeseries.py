#!/usr/bin/env python3
"""Drought-parity pumping timeseries through 3-yr pumping + 10-yr recovery.

Replaces the truncated ``pumping_course_streamflow_storage.png`` (spinup → pump
only; recovery was not finished). Wolf-only versions remain under
``wolf_pumping_*``.

Uses native 219 h products (53 years). Baseline: ``droughts/short_baseline``.
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
from analysis.paper_figures import utils  # noqa: E402

PUMP_ENSEMBLE = "3_year_pumping_tests"
BASE_ENSEMBLE = "droughts"
BASE_MEMBER = "short_baseline"
DOMAINS = ["potomac2", "wolf2"]
DOMAIN_LABELS = {"potomac2": "Potomac", "wolf2": "Wolf"}
RATES = [1e-7, 1e-6, 1e-5, 1e-4]
RATE_LABELS = {r: f"{r:.0e}" for r in RATES}
SPINUP_YEARS = 40
PUMP_YEARS = 3
RECOVERY_YEARS = 10
N_YEARS = SPINUP_YEARS + PUMP_YEARS + RECOVERY_YEARS
INTERVAL = 219
STEPS_PER_YEAR = utils.ONE_YEAR // INTERVAL
FOCUS_RATE = 1e-5

from analysis.figure_paths import FIG_DIR, FIG_ROOT, fig_path, resolve_figure  # noqa: E402
SUMMARY_MD = ROOT / "analysis" / "pumping_recovery_timeseries_summary.md"
FIG_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {1e-7: "#E8C39E", 1e-6: "#B86B2B", 1e-5: "#4A2410", 1e-4: "#140A05"}
TEMP_COLOR = "#D4A574"
PERSIST_COLOR = "#5C3317"
LABEL_FS, LEGEND_FS, TITLE_FS = 12, 11, 13
S_SCALE = 1e9
DS_SCALE = 1e6

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
    paths = [Path(p) for p in files[:N_YEARS]]
    if len(paths) < N_YEARS:
        raise RuntimeError(
            f"{domain}/{member}: expected {N_YEARS} years, got {len(paths)}"
        )
    return paths


def read_series(domain_name: str, paths: list[Path]) -> xr.Dataset:
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
        flow = OF.window_mean_outlet_flow(path, ox, oy)
        n = stor.shape[0]
        times.append(year_offset + np.arange(n, dtype=np.float64) / STEPS_PER_YEAR)
        storage.append(stor)
        outlet.append(flow)
    return xr.Dataset(
        {
            "storage": ("time", np.concatenate(storage)),
            "outlet_flow": ("time", np.concatenate(outlet)),
        },
        coords={"time": np.concatenate(times)},
    )


def recovery_window(ds: xr.Dataset, baseline: xr.Dataset, *, years: int) -> dict:
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


def load_all() -> dict:
    series = {}
    for d in DOMAINS:
        series[d] = {}
        print(f"Loading baseline {d}/{BASE_MEMBER}…", flush=True)
        series[d]["_baseline"] = read_series(d, _paths(BASE_ENSEMBLE, BASE_MEMBER, d))
        for rate in RATES:
            print(f"Loading {d}/{_resolve_member(rate)}…", flush=True)
            ds = read_series(d, _paths(PUMP_ENSEMBLE, _resolve_member(rate), d))
            series[d][rate] = ds
            print(f"  t={float(ds.time.min()):.2f}→{float(ds.time.max()):.2f}", flush=True)
    return series


def _shade_pump_recovery(ax):
    ax.axvline(0, color="k", ls="--", lw=0.9)
    ax.axvline(PUMP_YEARS, color="k", ls=":", lw=0.9)
    ax.axvspan(0, PUMP_YEARS, color="C3", alpha=0.08)
    ax.axvspan(PUMP_YEARS, PUMP_YEARS + RECOVERY_YEARS, color="C0", alpha=0.05)


def fig_course(series: dict):
    """Q + S: last 3 spinup years through 3-yr pump + 10-yr recovery."""
    plot_start = SPINUP_YEARS - 3
    plot_end = SPINUP_YEARS + PUMP_YEARS + RECOVERY_YEARS
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5), sharex="col", constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.06, w_pad=0.04, hspace=0.08, wspace=0.04)
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
            _shade_pump_recovery(ax)
            ax.grid(True, alpha=0.3)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax.xaxis.set_major_locator(MultipleLocator(2))
            ax.xaxis.set_minor_locator(MultipleLocator(1))
        ax_q.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        if col == 0:
            ax_q.set_ylabel("Outlet flow (m³/h)", fontsize=LABEL_FS)
            ax_s.set_ylabel("Total storage (10⁹ m³)", fontsize=LABEL_FS)
    fig.supxlabel("Year (from pumping start)", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=COLORS[r], lw=1.3, label=RATE_LABELS[r]) for r in RATES]
    handles += [
        Line2D([0], [0], color="0.65", lw=1.0, label="baseline"),
        Patch(facecolor="C3", alpha=0.25, edgecolor="none", label="pumping"),
        Patch(facecolor="C0", alpha=0.18, edgecolor="none", label="recovery"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=7, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_course_streamflow_storage.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_recovery_totals(series: dict):
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
            w = recovery_window(series[d][rate], bl, years=RECOVERY_YEARS)
            ax_S.plot(w["t"], w["Sb"], color="0.75", lw=0.9, alpha=0.7)
            ax_Q.plot(w["t"], w["Qb"], color="0.75", lw=0.9, alpha=0.7)
            lab = RATE_LABELS[rate]
            ax_S.plot(w["t"], w["S"], color=COLORS[rate], lw=1.5, label=lab)
            ax_dS.plot(w["t"], w["dS"], color=COLORS[rate], lw=1.5, label=lab)
            ax_Q.plot(w["t"], w["Q"], color=COLORS[rate], lw=1.5, label=lab)
            ax_dQ.plot(w["t"], w["dQ"], color=COLORS[rate], lw=1.5, label=lab)
        for ax in (ax_dS, ax_dQ):
            ax.axhline(0, color="k", lw=0.6)
        for ax in axes[:, col]:
            ax.axvline(0, color="k", ls="--", lw=0.8)
            ax.grid(True, alpha=0.3)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax.xaxis.set_major_locator(MultipleLocator(1))
        ax_S.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
    axes[1, 1].sharey(axes[1, 0])
    for ax in (axes[1, 0], axes[3, 0], axes[3, 1]):
        lo, hi = ax.get_ylim()
        ax.set_ylim(min(lo, 0.0), max(hi, 0.0))
    for ax, label in zip(axes[:, 0], ylabels):
        ax.set_ylabel(label, fontsize=LABEL_FS)
    fig.supxlabel("Years into recovery (after 3-yr pumping)", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=COLORS[r], lw=1.5, label=RATE_LABELS[r]) for r in RATES]
    handles.append(Line2D([0], [0], color="0.65", lw=1.2, label="baseline"))
    fig.legend(handles=handles, loc="outside upper center", ncol=5, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_recovery_totals_and_anomalies.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_recovery_fractional(series: dict):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        bl = series[d]["_baseline"]
        for rate in RATES:
            w = recovery_window(series[d][rate], bl, years=RECOVERY_YEARS)
            d0 = w["dS"][0]
            if d0 == 0:
                continue
            ax.plot(w["t"], w["dS"] / d0, color=COLORS[rate], lw=1.5, label=RATE_LABELS[rate])
        ax.axhline(0, color="k", lw=0.6)
        ax.axhline(1.0, color="k", lw=0.6, ls=":")
        ax.axvline(0, color="k", ls="--", lw=0.8)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        if col == 0:
            ax.set_ylabel("Fraction of initial storage deficit", fontsize=LABEL_FS)
    fig.supxlabel("Years into recovery", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=COLORS[r], lw=1.5, label=RATE_LABELS[r]) for r in RATES]
    fig.legend(handles=handles, loc="outside upper center", ncol=4, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_recovery_fractional_storage.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_temp_persist_definition(series: dict):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), constrained_layout=True)
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        bl = series[d]["_baseline"]
        for rate in RATES:
            w = recovery_window(series[d][rate], bl, years=5)
            lw = 2.2 if rate == FOCUS_RATE else 1.0
            alpha = 1.0 if rate == FOCUS_RATE else 0.35
            ax.plot(w["t"], w["dS"], color=COLORS[rate], lw=lw, alpha=alpha, label=RATE_LABELS[rate])
        w = recovery_window(series[d][FOCUS_RATE], bl, years=5)
        t, dS = w["t"], w["dS"]
        i0 = int(np.argmin(np.abs(t - 0.0)))
        i1 = int(np.argmin(np.abs(t - 1.0)))
        d1 = float(dS[i1])
        ax.axvspan(0.0, 1.0, color=TEMP_COLOR, alpha=0.22, zorder=0)
        t_tail = t[t >= 1.0]
        if t_tail.size:
            ax.fill_between(t_tail, d1, 0.0, color=PERSIST_COLOR, alpha=0.18, zorder=0)
        ax.axhline(0.0, color="0.45", lw=0.7)
        ax.axvline(0.0, color="k", ls="--", lw=0.8)
        ax.set_xlim(-0.15, 5.05)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        if col == 0:
            ax.set_ylabel(r"$\Delta$ storage ($10^6$ m$^3$)", fontsize=LABEL_FS)
    fig.supxlabel("Years into recovery", fontsize=LABEL_FS)
    handles = [
        Line2D(
            [0],
            [0],
            color=COLORS[r],
            lw=2.0 if r == FOCUS_RATE else 1.0,
            label=RATE_LABELS[r],
        )
        for r in RATES
    ]
    handles += [
        Patch(facecolor=TEMP_COLOR, alpha=0.35, edgecolor="none", label="Temporary (yr 1)"),
        Patch(facecolor=PERSIST_COLOR, alpha=0.25, edgecolor="none", label="Persistent"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=3, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_temp_persist_definition.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def write_summary():
    lines = [
        "# Pumping recovery timeseries (drought-parity)",
        "",
        "**Script:** [`pumping_recovery_timeseries.py`](pumping_recovery_timeseries.py)  ",
        "Sequence: 40 yr average spinup + **3 yr pumping** + **10 yr recovery**.  ",
        "Rates: `1e-7` … `1e-4` m/h domain-average. Baseline: `droughts/short_baseline`.",
        "",
        "These are the pumping analogues of the basic drought courses / recovery",
        "timeseries. The earlier [`pumping_course_streamflow_storage.png`](figures/pumping_course_streamflow_storage.png)",
        "stopped at the end of pumping; this script overwrites it with the full recovery.",
        "Wolf-only copies (`wolf_pumping_course_*`, etc.) are unchanged.",
        "",
        "## Figures",
        "",
        "- [pumping_course_streamflow_storage.png](figures/pumping_course_streamflow_storage.png) — Q + S (last 3 spinup yr → pump → 10-yr recovery)",
        "- [pumping_recovery_totals_and_anomalies.png](figures/pumping_recovery_totals_and_anomalies.png) — recovery S, ΔS, Q, ΔQ by rate",
        "- [pumping_recovery_fractional_storage.png](figures/pumping_recovery_fractional_storage.png) — fraction of end-pump deficit remaining",
        "- [pumping_temp_persist_definition.png](figures/pumping_temp_persist_definition.png) — ΔS schematic: yr-1 = temporary",
        "",
        "Related (already complete, not remade here):",
        "[pumping_annualized_q_course.png](figures/pumping_annualized_q_course.png),",
        "[pumping_during_totals_and_anomalies.png](figures/pumping_during_totals_and_anomalies.png),",
        "[pumping_vs_drought_fractional_recovery.png](figures/pumping_vs_drought_fractional_recovery.png).",
        "",
        "## Reproduce",
        "",
        "```bash",
        "conda activate /glade/work/bwest/conda-envs/droughts",
        "cd /glade/derecho/scratch/bwest/drought-ensemble",
        "python analysis/pumping_recovery_timeseries.py",
        "```",
        "",
        f"*Generated by `{Path(__file__).name}`.*",
        "",
    ]
    SUMMARY_MD.write_text("\n".join(lines))
    print("wrote", SUMMARY_MD)


def main():
    series = load_all()
    fig_course(series)
    fig_recovery_totals(series)
    fig_recovery_fractional(series)
    fig_temp_persist_definition(series)
    write_summary()


if __name__ == "__main__":
    main()
