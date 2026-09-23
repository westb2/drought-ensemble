#!/usr/bin/env python3
"""How pumping storage deficits differ from drought (same 3-year stress length).

Temporary = recovered in recovery year 1 (end-stress deficit − remaining).
Persistent = remaining after recovery year 1.
Near-surface = CONUS2 z≥6 (top 2 m); deep = z<6.
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

from analysis.paper_figures import utils  # noqa: E402
from analysis.shallow_deep_shielding import DEEP_COLOR, SHALLOW_COLOR, SHALLOW_Z0  # noqa: E402

DOMAINS = ["potomac2", "wolf2"]
DOMAIN_LABELS = {"potomac2": "Potomac", "wolf2": "Wolf"}
PUMP_ENSEMBLE = "3_year_pumping_tests"
DROUGHT_ENSEMBLE = "droughts"
DROUGHT_MEMBER = "3_year_drought"
BASE_MEMBER = "short_baseline"
RATES = [1e-7, 1e-6, 1e-5, 1e-4]
RATE_LABELS = {r: f"{r:.0e}" for r in RATES}
SPINUP_YEARS = 40
STRESS_YEARS = 3
PUMP_RECOVERY = 10
DROUGHT_RECOVERY = 5
COMPARE_RECOVERY = 5
INTERVAL = 219
STEPS_PER_YEAR = utils.ONE_YEAR // INTERVAL
DS_SCALE = 1e6
CELL_AREA_M2 = 1_000_000.0
FOCUS_RATE = 1e-5

from analysis.figure_paths import FIG_DIR, FIG_ROOT, fig_path, resolve_figure  # noqa: E402
SUMMARY_MD = ROOT / "analysis" / "pumping_vs_drought_deficits_summary.md"
OUT_JSON = FIG_DIR / "pumping_vs_drought_deficits.json"

TEMP_COLOR = "#D4A574"
PERSIST_COLOR = "#5C3317"
DROUGHT_COLOR = "#B86B2B"
PUMP_COLORS = {1e-7: "#E8C39E", 1e-6: "#B86B2B", 1e-5: "#4A2410", 1e-4: "#140A05"}
LABEL_FS, LEGEND_FS, TITLE_FS = 12, 11, 13
TEMP_NS = "#6BAED6"
TEMP_DE = "#C6DBEF"
PERS_NS = "#9E9AC8"
PERS_DE = "#542788"


def _resolve_pump(rate: float) -> str:
    return {1e-7: "pumping_1e-7", 1e-6: "pumping_1e-6", 1e-5: "pumping_1e-5", 1e-4: "pumping_1e-4"}[rate]


def _paths(ensemble: str, member: str, domain: str) -> list[Path]:
    files = utils._file_locations(ensemble, member, domain, 0, interval=INTERVAL)
    return [Path(p) for p in files]


def _end_storage(path: Path) -> float:
    with xr.open_dataset(path) as ds:
        if "total_storage" in ds:
            return float(ds["total_storage"].values[-1])
        return float(ds["subsurface_storage"].isel(time=-1).sum(skipna=True).values)


def _col_storage_m(path: Path) -> xr.DataArray:
    with xr.open_dataset(path) as ds:
        stor = ds["subsurface_storage"].isel(time=-1).sum(dim="z")
        mask = ds["mask"]
        active = mask.any(dim="z") > 0 if "z" in mask.dims else mask > 0
        return (stor / CELL_AREA_M2).where(active).load()


def _year_storage_series(path: Path) -> np.ndarray:
    with xr.open_dataset(path) as ds:
        if "total_storage" in ds:
            return np.asarray(ds["total_storage"].values, dtype=np.float64)
        return ds["subsurface_storage"].sum(dim=("x", "y", "z"), skipna=True).values.astype(np.float64)


def _layer_end(path: Path) -> xr.DataArray:
    with xr.open_dataset(path) as ds:
        stor = ds["subsurface_storage"].isel(time=-1)
        mask = ds["mask"]
        active = mask.any(dim="z") > 0 if "z" in mask.dims else mask > 0
        return stor.where(active).load()


def temp_persist_domain(member_paths: list[Path], base_paths: list[Path], stress_years: int) -> dict:
    """Map-based yr-1 split (per-cell clip), same as drought recovery figures."""
    i0 = SPINUP_YEARS + stress_years - 1
    i1 = SPINUP_YEARS + stress_years
    d0, b0 = _col_storage_m(member_paths[i0]), _col_storage_m(base_paths[i0])
    d1, b1 = _col_storage_m(member_paths[i1]), _col_storage_m(base_paths[i1])
    deficit0, deficit1 = b0 - d0, b1 - d1
    temporary = xr.apply_ufunc(np.maximum, deficit0 - deficit1, 0.0)
    persistent = xr.apply_ufunc(np.maximum, deficit1, 0.0)
    temp = float(np.nansum(temporary.values)) * CELL_AREA_M2 / DS_SCALE
    persist = float(np.nansum(persistent.values)) * CELL_AREA_M2 / DS_SCALE
    tot = temp + persist
    return {
        "temp_1e6": temp,
        "persist_1e6": persist,
        "end_1e6": float(np.nansum(np.maximum(deficit0.values, 0.0))) * CELL_AREA_M2 / DS_SCALE,
        "f_temp": temp / tot if tot > 0 else float("nan"),
        "f_persist": persist / tot if tot > 0 else float("nan"),
    }


def recovery_ds_series(member_paths: list[Path], base_paths: list[Path], stress_years: int, n_rec: int):
    """ΔS (10⁶ m³) from recovery onset for n_rec years (219 h)."""
    t0 = SPINUP_YEARS + stress_years
    t_all, ds_all = [], []
    for k in range(n_rec):
        s = _year_storage_series(member_paths[t0 + k])
        b = _year_storage_series(base_paths[t0 + k])
        n = min(len(s), len(b))
        t_all.append(k + np.arange(n, dtype=np.float64) / STEPS_PER_YEAR)
        ds_all.append((s[:n] - b[:n]) / DS_SCALE)
    t = np.concatenate(t_all)
    dS = np.concatenate(ds_all)
    # initial deficit from last stress year
    d_end = _end_storage(member_paths[t0 - 1])
    b_end = _end_storage(base_paths[t0 - 1])
    d0 = (d_end - b_end) / DS_SCALE  # negative if drier
    return {"t": t, "dS": dS, "dS0": d0}


def depth_split(member_paths: list[Path], base_paths: list[Path], stress_years: int) -> dict:
    i0 = SPINUP_YEARS + stress_years - 1
    i1 = SPINUP_YEARS + stress_years
    d0 = _layer_end(member_paths[i0])
    b0 = _layer_end(base_paths[i0])
    d1 = _layer_end(member_paths[i1])
    b1 = _layer_end(base_paths[i1])
    def0 = b0 - d0
    rec = def0 - (b1 - d1)
    persist = b1 - d1

    def to_e6(da):
        return float(np.maximum(da.sum(), 0.0) / DS_SCALE)

    return {
        "temp_sh": to_e6(rec.isel(z=slice(SHALLOW_Z0, None))),
        "temp_de": to_e6(rec.isel(z=slice(0, SHALLOW_Z0))),
        "pers_sh": to_e6(persist.isel(z=slice(SHALLOW_Z0, None))),
        "pers_de": to_e6(persist.isel(z=slice(0, SHALLOW_Z0))),
        "end_sh": to_e6(def0.isel(z=slice(SHALLOW_Z0, None))),
        "end_de": to_e6(def0.isel(z=slice(0, SHALLOW_Z0))),
    }


def load_all() -> dict:
    out = {}
    for d in DOMAINS:
        print(f"Loading {d}…", flush=True)
        base = _paths(DROUGHT_ENSEMBLE, BASE_MEMBER, d)
        drought = _paths(DROUGHT_ENSEMBLE, DROUGHT_MEMBER, d)
        rec = {"drought": temp_persist_domain(drought, base, STRESS_YEARS), "pump": {}}
        rec["drought_series"] = recovery_ds_series(drought, base, STRESS_YEARS, DROUGHT_RECOVERY)
        rec["drought_depth"] = depth_split(drought, base, STRESS_YEARS)
        rec["pump_series"] = {}
        rec["pump_depth"] = {}
        for rate in RATES:
            pp = _paths(PUMP_ENSEMBLE, _resolve_pump(rate), d)
            rec["pump"][f"{rate:.0e}"] = temp_persist_domain(pp, base, STRESS_YEARS)
            rec["pump_series"][f"{rate:.0e}"] = recovery_ds_series(pp, base, STRESS_YEARS, COMPARE_RECOVERY)
        rec["pump_depth"]["1e-05"] = depth_split(
            _paths(PUMP_ENSEMBLE, _resolve_pump(FOCUS_RATE), d), base, STRESS_YEARS
        )
        dr = rec["drought"]
        print(
            f"  drought temp/persist {dr['temp_1e6']:.1f}/{dr['persist_1e6']:.1f}  "
            f"f_temp={dr['f_temp']:.2f}",
            flush=True,
        )
        out[d] = rec
    return out


def fig_temp_persist_bars(data: dict):
    """Volumes: 3-yr drought vs 1e-5 (same duration). f_temp: drought + all rates."""
    vol_labels = ["3-yr drought", "Pumping 1e-5"]
    frac_labels = ["3-yr\ndrought", "1e-7", "1e-6", "1e-5", "1e-4"]
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.6), constrained_layout=True)
    fig.set_constrained_layout_pads(h_pad=0.08, w_pad=0.04, hspace=0.12, wspace=0.04)
    axes[1, 1].sharey(axes[1, 0])
    x_vol = np.arange(2)
    x_frac = np.arange(len(frac_labels))
    for col, d in enumerate(DOMAINS):
        ax_v, ax_f = axes[0, col], axes[1, col]
        rec = data[d]
        p = rec["pump"]["1e-05"]
        temps = [rec["drought"]["temp_1e6"], p["temp_1e6"]]
        pers = [rec["drought"]["persist_1e6"], p["persist_1e6"]]
        ft = [rec["drought"]["f_temp"]] + [rec["pump"][f"{r:.0e}"]["f_temp"] for r in RATES]
        ax_v.bar(x_vol, temps, color=TEMP_COLOR, edgecolor="0.25", linewidth=0.5, width=0.55)
        ax_v.bar(x_vol, pers, bottom=temps, color=PERSIST_COLOR, edgecolor="0.25", linewidth=0.5, width=0.55)
        colors = [DROUGHT_COLOR] + [PUMP_COLORS[r] for r in RATES]
        ax_f.bar(x_frac, ft, color=colors, edgecolor="0.25", linewidth=0.5)
        ax_v.set_ylim(0, None)
        ax_f.set_ylim(0, 1.05)
        ax_v.set_xticks(x_vol)
        ax_v.set_xticklabels(vol_labels)
        ax_f.set_xticks(x_frac)
        ax_f.set_xticklabels(frac_labels, fontsize=10)
        for ax in (ax_v, ax_f):
            ax.grid(True, axis="y", alpha=0.3)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax_v.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        if col == 0:
            ax_v.set_ylabel("Storage deficit (10⁶ m³)", fontsize=LABEL_FS)
            ax_f.set_ylabel("Temporary fraction", fontsize=LABEL_FS)
    handles = [
        Patch(facecolor=TEMP_COLOR, edgecolor="0.25", label="Temporary (recovered in yr 1)"),
        Patch(facecolor=PERSIST_COLOR, edgecolor="0.25", label="Persistent (remaining)"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=2, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_vs_drought_temp_persist_bars.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_fractional_recovery(data: dict):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True, constrained_layout=True)
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        rec = data[d]
        dw = rec["drought_series"]
        d0 = abs(dw["dS0"]) if dw["dS0"] != 0 else np.nan
        ax.plot(dw["t"], np.abs(dw["dS"]) / d0, color=DROUGHT_COLOR, lw=2.0, label="3-yr drought")
        for rate in RATES:
            w = rec["pump_series"][f"{rate:.0e}"]
            d_init = abs(w["dS0"])
            if d_init == 0:
                continue
            ax.plot(
                w["t"],
                np.abs(w["dS"]) / d_init,
                color=PUMP_COLORS[rate],
                lw=1.5,
                label=RATE_LABELS[rate],
            )
        ax.axhline(1.0, color="k", lw=0.6, ls=":")
        ax.axhline(0.0, color="k", lw=0.6)
        ax.axvline(0, color="k", ls="--", lw=0.8)
        ax.axvline(1, color="k", ls=":", lw=0.7)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        if col == 0:
            ax.set_ylabel("Fraction of end-stress deficit remaining", fontsize=LABEL_FS)
    axes[0].set_ylim(0.0, 1.15)
    fig.supxlabel("Years into recovery", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color=DROUGHT_COLOR, lw=2.0, label="3-yr drought")]
    handles += [Line2D([0], [0], color=PUMP_COLORS[r], lw=1.5, label=RATE_LABELS[r]) for r in RATES]
    fig.legend(handles=handles, loc="outside upper center", ncol=5, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_vs_drought_fractional_recovery.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_ds_recovery(data: dict):
    """Absolute ΔS through recovery: drought 3-yr vs pumping 1e-5."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        rec = data[d]
        dw = rec["drought_series"]
        pw = rec["pump_series"]["1e-05"]
        ax.plot(dw["t"], dw["dS"], color=DROUGHT_COLOR, lw=1.8, label="3-yr drought")
        ax.plot(pw["t"], pw["dS"], color=PUMP_COLORS[FOCUS_RATE], lw=1.8, label="Pumping 1e-5")
        ax.axhline(0, color="k", lw=0.7)
        ax.axvline(0, color="k", ls="--", lw=0.8)
        ax.axvline(1, color="k", ls=":", lw=0.7)
        ax.axvspan(0, 1, color=TEMP_COLOR, alpha=0.18)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        lo, hi = ax.get_ylim()
        ax.set_ylim(min(lo, 0.0), max(hi, 0.0))
        if col == 0:
            ax.set_ylabel("Δ storage (10⁶ m³)", fontsize=LABEL_FS)
    fig.supxlabel("Years into recovery", fontsize=LABEL_FS)
    handles = [
        Line2D([0], [0], color=DROUGHT_COLOR, lw=1.8, label="3-yr drought"),
        Line2D([0], [0], color=PUMP_COLORS[FOCUS_RATE], lw=1.8, label="Pumping 1e-5"),
        Patch(facecolor=TEMP_COLOR, alpha=0.35, edgecolor="none", label="recovery year 1"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=3, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_vs_drought_ds_recovery.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_depth_partition(data: dict):
    """Stacked temp/persist × near-surface/deep for 3-yr drought vs pumping 1e-5."""
    keys = ["temp_sh", "temp_de", "pers_sh", "pers_de"]
    colors = [TEMP_NS, TEMP_DE, PERS_NS, PERS_DE]
    labels = [
        "Temporary, near-surface",
        "Temporary, deep",
        "Persistent, near-surface",
        "Persistent, deep",
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), constrained_layout=True)
    x = np.array([0, 1])
    xticklabels = ["3-yr drought", "Pumping 1e-5"]
    for col, d in enumerate(DOMAINS):
        ax = axes[col]
        drought = data[d]["drought_depth"]
        pump = data[d]["pump_depth"]["1e-05"]
        bottom_d = 0.0
        bottom_p = 0.0
        for key, color in zip(keys, colors):
            ax.bar(0, drought[key], bottom=bottom_d, color=color, edgecolor="0.2", linewidth=0.5, width=0.55)
            ax.bar(1, pump[key], bottom=bottom_p, color=color, edgecolor="0.2", linewidth=0.5, width=0.55)
            bottom_d += drought[key]
            bottom_p += pump[key]
        ax.set_xticks(x)
        ax.set_xticklabels(xticklabels)
        ax.set_ylim(0, None)
        ax.set_title(DOMAIN_LABELS[d], fontsize=TITLE_FS)
        ax.grid(True, axis="y", alpha=0.3)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        if col == 0:
            ax.set_ylabel("Storage deficit (10⁶ m³)", fontsize=LABEL_FS)
    handles = [Patch(facecolor=c, edgecolor="0.2", label=lab) for c, lab in zip(colors, labels)]
    fig.legend(handles=handles, loc="outside upper center", ncol=2, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "pumping_vs_drought_depth_partition.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def write_summary(data: dict):
    lines = [
        "# Pumping vs drought storage deficits",
        "",
        "**Date:** August 2026  ",
        "**Script:** [`pumping_vs_drought_deficits.py`](pumping_vs_drought_deficits.py)  ",
        "Same 3-year stress length. Temporary = recovered in recovery year 1; "
        "persistent = remaining. Near-surface = top 2 m (z≥6).",
        "",
        "## Figures",
        "",
        "- [pumping_vs_drought_temp_persist_bars.png](figures/pumping_vs_drought_temp_persist_bars.png)",
        "- [pumping_vs_drought_fractional_recovery.png](figures/pumping_vs_drought_fractional_recovery.png)",
        "- [pumping_vs_drought_ds_recovery.png](figures/pumping_vs_drought_ds_recovery.png)",
        "- [pumping_vs_drought_depth_partition.png](figures/pumping_vs_drought_depth_partition.png)",
        "",
        "## Domain totals (10⁶ m³)",
        "",
        "| Domain | Case | Temporary | Persistent | f_temp |",
        "|--------|------|----------:|-----------:|-------:|",
    ]
    for d in DOMAINS:
        rec = data[d]["drought"]
        lines.append(
            f"| {DOMAIN_LABELS[d]} | 3-yr drought | {rec['temp_1e6']:.1f} | "
            f"{rec['persist_1e6']:.1f} | {rec['f_temp']:.2f} |"
        )
        for rate in RATES:
            r = data[d]["pump"][f"{rate:.0e}"]
            lines.append(
                f"| {DOMAIN_LABELS[d]} | pumping {rate:.0e} | {r['temp_1e6']:.1f} | "
                f"{r['persist_1e6']:.1f} | {r['f_temp']:.2f} |"
            )

    lines += [
        "",
        "## Depth split (3-yr drought vs pumping 1e-5)",
        "",
        "| Domain | Case | Temp NS | Temp deep | Persist NS | Persist deep |",
        "|--------|------|--------:|----------:|-----------:|-------------:|",
    ]
    for d in DOMAINS:
        for name, key in (("3-yr drought", "drought_depth"),):
            z = data[d][key]
            lines.append(
                f"| {DOMAIN_LABELS[d]} | {name} | {z['temp_sh']:.1f} | {z['temp_de']:.1f} | "
                f"{z['pers_sh']:.1f} | {z['pers_de']:.1f} |"
            )
        z = data[d]["pump_depth"]["1e-05"]
        lines.append(
            f"| {DOMAIN_LABELS[d]} | pumping 1e-5 | {z['temp_sh']:.1f} | {z['temp_de']:.1f} | "
            f"{z['pers_sh']:.1f} | {z['pers_de']:.1f} |"
        )

    lines += ["", "## Takeaways", ""]
    for d in DOMAINS:
        dr = data[d]["drought"]
        p = data[d]["pump"]["1e-05"]
        lines.append(
            f"- **{DOMAIN_LABELS[d]}** 3-yr drought: f_temp={dr['f_temp']:.2f} "
            f"({dr['temp_1e6']:.0f} / {dr['persist_1e6']:.0f} ×10⁶ m³ temp/persist)."
        )
        lines.append(
            f"- **{DOMAIN_LABELS[d]}** pumping 1e-5: f_temp={p['f_temp']:.2f} "
            f"({p['temp_1e6']:.0f} / {p['persist_1e6']:.0f}) — little drought-style temporary pool."
        )
    lines += [
        "- Drought deficit falls sharply in recovery year 1 then plateaus; pumping deficit stays.",
        "- Drought temporary mass is near-surface; pumping leftover is deep (layer-2 extraction).",
        "",
        "## Reproduce",
        "",
        "```bash",
        "conda activate /glade/work/bwest/conda-envs/droughts",
        "cd /glade/derecho/scratch/bwest/drought-ensemble",
        "python analysis/pumping_vs_drought_deficits.py",
        "```",
        "",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n")
    print("wrote", SUMMARY_MD)


def main():
    data = load_all()
    serial = {
        d: {
            "drought": data[d]["drought"],
            "pump": data[d]["pump"],
            "drought_depth": data[d]["drought_depth"],
            "pump_depth": data[d]["pump_depth"],
        }
        for d in DOMAINS
    }
    OUT_JSON.write_text(json.dumps(serial, indent=2))
    print("wrote", OUT_JSON)
    fig_temp_persist_bars(data)
    fig_fractional_recovery(data)
    fig_ds_recovery(data)
    fig_depth_partition(data)
    write_summary(data)


if __name__ == "__main__":
    main()
