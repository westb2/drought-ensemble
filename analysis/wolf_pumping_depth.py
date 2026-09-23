#!/usr/bin/env python3
"""Where Wolf pumping (layer 2) storage losses sit vs a 3-year drought.

Intended L4 vs L2 comparison is not possible yet: layer-4 jobs hashed as
layer 2 and skipped/collided with ``3_year_pumping_tests`` years. This script
uses Wolf L2 ``pumping_1e-5`` (with 10-yr recovery) vs ``3_year_drought``.

CONUS2 z=0 is deepest. Layer 2 ≈ 42–92 m below land surface; near-surface
(top 2 m) is z≥6. Layer 4 (not yet run uniquely) would be ≈ 7–17 m.
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
from analysis.shallow_deep_shielding import DEEP_COLOR, DZ_M, SHALLOW_COLOR, SHALLOW_Z0  # noqa: E402
from analysis.wolf_pumping_recovery import (  # noqa: E402
    BASE_ENSEMBLE,
    BASE_MEMBER,
    CELL_AREA_M2,
    DOMAIN,
    DS_SCALE,
    FIG_DIR,
    INTERVAL,
    LABEL_FS,
    LEGEND_FS,
    PERSIST_COLOR,
    PUMP_ENSEMBLE,
    PUMP_YEARS,
    SPINUP_YEARS,
    STEPS_PER_YEAR,
    TEMP_COLOR,
    TITLE_FS,
    baseline_paths,
    pumping_paths,
)

DROUGHT_ENSEMBLE = "droughts"
DROUGHT_MEMBER = "3_year_drought"
DROUGHT_YEARS = 3
FOCUS_RATE = 1e-5
SUMMARY_MD = ROOT / "analysis/wolf_pumping_depth_summary.md"

# Midpoint depth of each layer below land surface (z=9 at surface)
DEPTH_MID = np.cumsum(DZ_M[::-1])[::-1] - 0.5 * DZ_M
LAYER2_TOP, LAYER2_BOT = 42.0, 92.0
LAYER4_TOP, LAYER4_BOT = 7.0, 17.0


def drought_paths() -> list[Path]:
    files = utils._file_locations(DROUGHT_ENSEMBLE, DROUGHT_MEMBER, DOMAIN, 0, interval=INTERVAL)
    return [Path(p) for p in files]


def read_layer_end(path: Path) -> xr.DataArray:
    with xr.open_dataset(path) as ds:
        stor = ds["subsurface_storage"].isel(time=-1)
        mask = ds["mask"]
        active = mask.any(dim="z") > 0 if "z" in mask.dims else mask > 0
        return stor.where(active).load()


def zone_series(paths: list[Path], base_paths: list[Path], t0: int, n_years: int) -> dict:
    """Near-surface / deep ΔS (10⁶ m³) from t0 for n_years (219 h)."""
    t_all, sh_all, de_all = [], [], []
    for k in range(n_years):
        yi = t0 + k
        with xr.open_dataset(paths[yi]) as ds:
            stor = ds["subsurface_storage"]
            mask = ds["mask"]
            active = mask.any(dim="z") > 0 if "z" in mask.dims else mask > 0
            stor = stor.where(active)
            sh = stor.isel(z=slice(SHALLOW_Z0, None)).sum(dim=("z", "y", "x")).values
            de = stor.isel(z=slice(0, SHALLOW_Z0)).sum(dim=("z", "y", "x")).values
        with xr.open_dataset(base_paths[yi]) as ds:
            stor = ds["subsurface_storage"]
            mask = ds["mask"]
            active = mask.any(dim="z") > 0 if "z" in mask.dims else mask > 0
            stor = stor.where(active)
            shb = stor.isel(z=slice(SHALLOW_Z0, None)).sum(dim=("z", "y", "x")).values
            deb = stor.isel(z=slice(0, SHALLOW_Z0)).sum(dim=("z", "y", "x")).values
        n = min(len(sh), len(shb))
        t_all.append(k + np.arange(n, dtype=np.float64) / STEPS_PER_YEAR)
        sh_all.append((sh[:n] - shb[:n]) / DS_SCALE)
        de_all.append((de[:n] - deb[:n]) / DS_SCALE)
    return {"t": np.concatenate(t_all), "shallow": np.concatenate(sh_all), "deep": np.concatenate(de_all)}


def layer_deficit_pair(stress_paths, base_paths, stress_years: int) -> dict:
    i0 = SPINUP_YEARS + stress_years - 1
    i1 = SPINUP_YEARS + stress_years
    d0 = read_layer_end(stress_paths[i0])
    b0 = read_layer_end(base_paths[i0])
    d1 = read_layer_end(stress_paths[i1])
    b1 = read_layer_end(base_paths[i1])
    def0 = b0 - d0
    rec = def0 - (b1 - d1)
    to_e6 = lambda da: float(np.maximum(da.sum(), 0.0) / DS_SCALE)
    layer_end = def0.sum(dim=("y", "x")).values / DS_SCALE
    layer_rec = rec.sum(dim=("y", "x")).values / DS_SCALE
    sh0 = to_e6(def0.isel(z=slice(SHALLOW_Z0, None)))
    de0 = to_e6(def0.isel(z=slice(0, SHALLOW_Z0)))
    temp = to_e6(rec)
    persist = to_e6(b1 - d1)
    temp_sh = to_e6(rec.isel(z=slice(SHALLOW_Z0, None)))
    temp_de = to_e6(rec.isel(z=slice(0, SHALLOW_Z0)))
    pers_sh = to_e6((b1 - d1).isel(z=slice(SHALLOW_Z0, None)))
    pers_de = to_e6((b1 - d1).isel(z=slice(0, SHALLOW_Z0)))
    return {
        "layer_end": layer_end,
        "layer_rec": layer_rec,
        "end_shallow": sh0,
        "end_deep": de0,
        "temp": temp,
        "persist": persist,
        "temp_sh": temp_sh,
        "temp_de": temp_de,
        "pers_sh": pers_sh,
        "pers_de": pers_de,
    }


def fig_layer_profile(pump: dict, drought: dict):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.8), sharey=True, constrained_layout=True)
    cases = [
        (axes[0], drought, "3-year drought"),
        (axes[1], pump, "Pumping 1e-5 (layer 2)"),
    ]
    for ax, data, title in cases:
        ax2 = ax.twiny()
        end = np.maximum(data["layer_end"], 0.0)
        rec = np.maximum(data["layer_rec"], 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            frac = np.where(end > 1e-6, rec / end, np.nan)
        ax.barh(DEPTH_MID, end, height=DZ_M * 0.85, color="0.75", edgecolor="0.3", label="End-stress deficit")
        ax2.plot(frac, DEPTH_MID, "o-", color="#C51B7D", lw=1.5, ms=5, label="Recovered in yr 1")
        ax.axhspan(LAYER2_TOP, LAYER2_BOT, color="#4A2410", alpha=0.12, zorder=0)
        ax.axhline(2.0, color=SHALLOW_COLOR, ls="--", lw=1.2)
        ax.set_ylim(DEPTH_MID.max() * 1.02, 0)
        ax.set_xlabel(r"Deficit ($10^6$ m$^3$)", fontsize=LABEL_FS)
        ax2.set_xlabel("Fraction recovered in year 1", fontsize=LABEL_FS, color="#C51B7D")
        ax2.set_xlim(-0.05, 1.05)
        ax2.tick_params(axis="x", colors="#C51B7D")
        ax.set_title(title, fontsize=TITLE_FS)
    axes[0].set_ylabel("Depth below land surface (m)", fontsize=LABEL_FS)
    axes[1].text(
        0.98,
        0.5 * (LAYER2_TOP + LAYER2_BOT),
        "layer 2 extraction",
        transform=axes[1].get_yaxis_transform(),
        ha="right",
        va="center",
        fontsize=9,
        color="#4A2410",
    )
    axes[0].text(0.98, 0.02, "← near-surface (top 2 m)", transform=axes[0].transAxes,
                 ha="right", va="bottom", fontsize=9, color=SHALLOW_COLOR)
    out = FIG_DIR / "wolf_pumping_depth_layer_profile.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_partition_bars(pump: dict, drought: dict):
    labels = ["End-stress\nnear-surface", "End-stress\ndeep", "Temporary\nnear-surface", "Temporary\ndeep",
              "Persistent\nnear-surface", "Persistent\ndeep"]
    dvals = [drought["end_shallow"], drought["end_deep"], drought["temp_sh"], drought["temp_de"],
             drought["pers_sh"], drought["pers_de"]]
    pvals = [pump["end_shallow"], pump["end_deep"], pump["temp_sh"], pump["temp_de"],
             pump["pers_sh"], pump["pers_de"]]
    x = np.arange(len(labels), dtype=float)
    width = 0.38
    fig, ax = plt.subplots(figsize=(10.5, 4.4), constrained_layout=True)
    ax.bar(x - width / 2, dvals, width, color="#B86B2B", edgecolor="0.25", linewidth=0.6, label="3-year drought")
    ax.bar(x + width / 2, pvals, width, color="#4A2410", edgecolor="0.25", linewidth=0.6, label="Pumping 1e-5 (L2)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Storage deficit (10⁶ m³)", fontsize=LABEL_FS)
    ax.set_ylim(bottom=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.legend(loc="outside upper center", ncol=2, frameon=False, fontsize=LEGEND_FS)
    out = FIG_DIR / "wolf_pumping_depth_shallow_deep_partition.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_zone_course(pump_s: dict, drought_s: dict):
    fig, axes = plt.subplots(2, 1, figsize=(8.5, 6.2), sharex=True, constrained_layout=True)
    for ax, series, title, span in [
        (axes[0], drought_s, "3-year drought", DROUGHT_YEARS),
        (axes[1], pump_s, "Pumping 1e-5 (layer 2)", PUMP_YEARS),
    ]:
        ax.plot(series["t"], series["shallow"], color=SHALLOW_COLOR, lw=1.5, label="Near-surface (top 2 m)")
        ax.plot(series["t"], series["deep"], color=DEEP_COLOR, lw=1.5, label="Deep (>2 m)")
        ax.axhline(0, color="k", lw=0.6)
        ax.axvline(0, color="k", ls="--", lw=0.8)
        ax.axvline(span, color="k", ls=":", lw=0.8)
        ax.axvspan(0, span, color="C3", alpha=0.08)
        ax.axvspan(span, span + 5, color="C0", alpha=0.06)
        ax.set_ylabel(r"$\Delta$ storage ($10^6$ m$^3$)", fontsize=LABEL_FS)
        ax.set_title(title, fontsize=TITLE_FS)
        ax.grid(True, alpha=0.3)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.xaxis.set_major_locator(MultipleLocator(1))
    axes[1].set_xlabel("Years from stress onset (red = stress; blue = first 5 yr recovery)", fontsize=LABEL_FS)
    handles = [
        Line2D([0], [0], color=SHALLOW_COLOR, lw=1.5, label="Near-surface (top 2 m)"),
        Line2D([0], [0], color=DEEP_COLOR, lw=1.5, label="Deep (>2 m)"),
        Patch(facecolor="C3", alpha=0.25, edgecolor="none", label="stress"),
        Patch(facecolor="C0", alpha=0.2, edgecolor="none", label="recovery"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=4, frameon=False, fontsize=LEGEND_FS)
    out = FIG_DIR / "wolf_pumping_depth_zone_course.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def write_summary(pump: dict, drought: dict):
    def fdeep(d):
        tot = d["end_shallow"] + d["end_deep"]
        return d["end_deep"] / tot if tot else float("nan")

    def fpers(d):
        tot = d["temp"] + d["persist"]
        return d["persist"] / tot if tot else float("nan")

    lines = [
        "# Wolf pumping depth — layer 2 vs 3-year drought",
        "",
        "Layer-4 vs layer-2 comparison is **not available**. `run_full_sequence` dropped",
        "`pumping_layer` on sub-year hashes, so `3_year_pumping_tests_layer4` skipped",
        "existing layer-2 years (Wolf) or collided with them (Potomac). Hashing is now",
        "fixed in `classes/Run.py`; unique L4 years still need to be submitted.",
        "",
        "Layer 2 extraction ≈ **42–92 m** below land surface. Near-surface = top **2 m** (z≥6).",
        "Intended layer 4 would be ≈ **7–17 m** (still below the 2 m skin).",
        "",
        "## End-of-stress deficit (Wolf)",
        "",
        "| Case | Near-surface (10⁶ m³) | Deep (10⁶ m³) | Deep fraction | Persistent fraction |",
        "|------|----------------------|---------------|---------------|---------------------|",
        f"| 3-year drought | {drought['end_shallow']:.1f} | {drought['end_deep']:.1f} | {fdeep(drought):.2f} | {fpers(drought):.2f} |",
        f"| Pumping 1e-5 (L2) | {pump['end_shallow']:.1f} | {pump['end_deep']:.1f} | {fdeep(pump):.2f} | {fpers(pump):.2f} |",
        "",
        "## Temporary vs persistent by zone",
        "",
        "| Case | Temp NS | Temp deep | Persist NS | Persist deep |",
        "|------|---------|-----------|------------|--------------|",
        f"| 3-year drought | {drought['temp_sh']:.1f} | {drought['temp_de']:.1f} | {drought['pers_sh']:.1f} | {drought['pers_de']:.1f} |",
        f"| Pumping 1e-5 (L2) | {pump['temp_sh']:.1f} | {pump['temp_de']:.1f} | {pump['pers_sh']:.1f} | {pump['pers_de']:.1f} |",
        "",
        "## Figures",
        "",
        "- `wolf_pumping_depth_layer_profile.png` — deficit by layer + yr-1 recovery fraction",
        "- `wolf_pumping_depth_shallow_deep_partition.png` — NS/deep × temp/persist bars",
        "- `wolf_pumping_depth_zone_course.png` — NS vs deep ΔS through stress + recovery",
        "",
        f"*Generated by `{Path(__file__).name}`.*",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n")
    print("wrote", SUMMARY_MD)


def main():
    print("Loading Wolf L2 pumping 1e-5 and 3-year drought…", flush=True)
    pump_paths = pumping_paths(FOCUS_RATE)
    dr_paths = drought_paths()
    n = SPINUP_YEARS + max(PUMP_YEARS, DROUGHT_YEARS) + 6
    base = baseline_paths(n)
    pump = layer_deficit_pair(pump_paths, base, PUMP_YEARS)
    drought = layer_deficit_pair(dr_paths, base, DROUGHT_YEARS)
    fig_layer_profile(pump, drought)
    fig_partition_bars(pump, drought)
    pump_s = zone_series(pump_paths, base, SPINUP_YEARS, PUMP_YEARS + 5)
    drought_s = zone_series(dr_paths, base, SPINUP_YEARS, DROUGHT_YEARS + 5)
    fig_zone_course(pump_s, drought_s)
    write_summary(pump, drought)


if __name__ == "__main__":
    main()
