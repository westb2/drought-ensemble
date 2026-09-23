#!/usr/bin/env python3
"""Pumping rate that matches the 10-yr drought storage deficit (10-yr stress).

Both stresses now run 10 years, so the match is on magnitude *and* duration.
Deficit is end-of-stress (year index 49) column storage vs `droughts/short_baseline`,
summed over active cells with per-cell clipping at zero, in 10^6 m^3.

The bracket members carry no recovery years, so temporary/persistent splits are
not available here — see `pumping_vs_drought_deficits.py` for that decomposition
on the 3-yr ensemble.
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

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

DOMAINS = ["potomac2", "wolf2"]
DOMAIN_LABELS = {"potomac2": "Potomac", "wolf2": "Wolf"}
PUMP_ENSEMBLE = "10_year_pumping_tests"
DROUGHT_ENSEMBLE = "droughts"
DROUGHT_MEMBER = "10_year_drought"
BASE_MEMBER = "short_baseline"
# The 1e-7…1e-4 members still owe their recovery tail, but year 49 (end of
# stress) is already on disk, so they can join the rate curve.
RATES = [1e-7, 5e-7, 1e-6, 2e-6, 3e-6, 5e-6, 1e-5, 1e-4]
SPINUP_YEARS = 40
STRESS_YEARS = 10
END_STRESS_IDX = SPINUP_YEARS + STRESS_YEARS - 1
INTERVAL = 219
CELL_AREA_M2 = 1_000_000.0
DS_SCALE = 1e6
# CONUS2 layer thicknesses (fractions x 200 m), same as classes/RunOutputReader.py
DZ = np.array([1.0, 0.5, 0.25, 0.125, 0.05, 0.025, 0.005, 0.003, 0.0015, 0.0005]) * 200

from analysis.figure_paths import FIG_DIR, FIG_ROOT, fig_path, resolve_figure  # noqa: E402
OUT_JSON = FIG_DIR / "matched_deficit_10yr.json"
SUMMARY_MD = ROOT / "analysis" / "matched_deficit_10yr_summary.md"

DROUGHT_COLOR = "#B86B2B"
PUMP_COLOR = "#2C5F8A"
MATCH_COLOR = "#7A4C9B"
LABEL_FS, LEGEND_FS, TITLE_FS = 12, 11, 13


def _rate_label(rate: float) -> str:
    return f"{rate:.0e}".replace("e-0", "e-")


def _member_dir(ensemble: str, member: str, domain: str) -> Path:
    return ROOT / "domains" / domain / "processed_full_runs" / ensemble / member


def _col_storage_consolidated(path: Path) -> np.ndarray:
    """Column-integrated storage (m) at end of year, active cells only."""
    with xr.open_dataset(path) as ds:
        stor = ds["subsurface_storage"].isel(time=-1).sum(dim="z")
        mask = ds["mask"]
        active = mask.any(dim="z") > 0 if "z" in mask.dims else mask > 0
        return (stor / CELL_AREA_M2).where(active).values


def _col_storage_raw(run_dir: Path) -> np.ndarray:
    """Same quantity straight from ParFlow output, for un-post-processed members."""
    from parflow.tools.hydrology import calculate_subsurface_storage

    with xr.open_dataset(run_dir / "run.out.00000.nc") as st:
        # Raw statics carry a leading singleton time dimension.
        porosity = st["porosity"].squeeze("time", drop=True).values
        specific_storage = st["specific_storage"].squeeze("time", drop=True).values
        mask = st["mask"].squeeze("time", drop=True).values
    with xr.open_dataset(run_dir / "run.out.00001.nc") as tr:
        pressure = tr["pressure"].isel(time=-1).values
        saturation = tr["saturation"].isel(time=-1).values
    stor = calculate_subsurface_storage(
        porosity, pressure, saturation, specific_storage, 1000, 1000, DZ, mask=mask
    )
    active = mask.any(axis=0) > 0
    return np.where(active, stor.sum(axis=0) / CELL_AREA_M2, np.nan)


def end_stress_storage(ensemble: str, member: str, domain: str) -> np.ndarray:
    """Prefer the 219 h product; fall back to raw when the index was never written."""
    mdir = _member_dir(ensemble, member, domain)
    idx = mdir / f"file_locations_{INTERVAL}h.json"
    if idx.exists():
        files = json.loads(idx.read_text())
        return _col_storage_consolidated(Path(files[END_STRESS_IDX]))
    run_dir = _raw_year_dir(ensemble, member, domain, END_STRESS_IDX)
    print(f"  {domain}/{member}: no {INTERVAL}h index, reading raw {run_dir.name[:12]}", flush=True)
    return _col_storage_raw(run_dir)


def _raw_year_dir(ensemble: str, member: str, domain: str, year_idx: int) -> Path:
    import hashlib

    seq = json.loads((ROOT / "run_sequences" / ensemble / f"{member}.json").read_text())["years"]
    key = "_".join(
        f"{y['wetness']}_{y['pumping_rate_fraction']}_{y['irrigation']}"
        for y in seq[: year_idx + 1]
    )
    h = hashlib.sha256(key.encode()).hexdigest()
    return ROOT / "domains" / domain / "raw_runs" / h


def deficit(base: np.ndarray, stressed: np.ndarray) -> dict:
    d = base - stressed
    return {
        "total_1e6": float(np.nansum(np.maximum(d, 0.0))) * CELL_AREA_M2 / DS_SCALE,
        "net_1e6": float(np.nansum(d)) * CELL_AREA_M2 / DS_SCALE,
    }


def matched_rate(rates: list[float], totals: list[float], target: float) -> dict:
    """Log-log interpolate the rate reproducing `target` deficit."""
    order = np.argsort(totals)
    d = np.asarray(totals, dtype=float)[order]
    r = np.asarray(rates, dtype=float)[order]
    inside = d[0] <= target <= d[-1]
    rate = float(10 ** np.interp(np.log10(target), np.log10(d), np.log10(r)))
    return {"rate": rate, "bracketed": bool(inside)}


def load_all() -> dict:
    out = {}
    for domain in DOMAINS:
        print(f"Loading {DOMAIN_LABELS[domain]}…", flush=True)
        base = end_stress_storage(DROUGHT_ENSEMBLE, BASE_MEMBER, domain)
        rec = {"drought": deficit(base, end_stress_storage(DROUGHT_ENSEMBLE, DROUGHT_MEMBER, domain))}
        rec["pump"] = {
            _rate_label(rate): deficit(
                base, end_stress_storage(PUMP_ENSEMBLE, f"pumping_{_rate_label(rate)}", domain)
            )
            for rate in RATES
        }
        totals = [rec["pump"][_rate_label(r)]["total_1e6"] for r in RATES]
        rec["match"] = matched_rate(RATES, totals, rec["drought"]["total_1e6"])
        print(
            f"  drought {rec['drought']['total_1e6']:.0f}e6 m3; "
            f"pumping {[f'{t:.0f}' for t in totals]}; "
            f"match {rec['match']['rate']:.2e} m/h"
            + ("" if rec["match"]["bracketed"] else "  [EXTRAPOLATED]"),
            flush=True,
        )
        out[domain] = rec
    return out


def fig_deficit_vs_rate(data: dict):
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.2), constrained_layout=True)
    for col, domain in enumerate(DOMAINS):
        ax = axes[col]
        rec = data[domain]
        totals = [rec["pump"][_rate_label(r)]["total_1e6"] for r in RATES]
        target = rec["drought"]["total_1e6"]
        m = rec["match"]["rate"]
        ax.plot(RATES, totals, "o-", color=PUMP_COLOR, lw=1.8, ms=6)
        ax.axhline(target, color=DROUGHT_COLOR, lw=1.8, ls="--")
        ax.plot([m], [target], marker="*", ms=16, color=MATCH_COLOR, ls="none", zorder=5)
        ax.annotate(
            f"{m:.1e} m/h",
            xy=(m, target),
            xytext=(6, -16),
            textcoords="offset points",
            fontsize=LEGEND_FS,
            color=MATCH_COLOR,
        )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(DOMAIN_LABELS[domain], fontsize=TITLE_FS)
        ax.grid(True, which="both", alpha=0.25)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        if col == 0:
            ax.set_ylabel("End-of-stress storage deficit (10⁶ m³)", fontsize=LABEL_FS)
    fig.supxlabel("Domain-average pumping rate (m h⁻¹)", fontsize=LABEL_FS)
    handles = [
        Line2D([0], [0], color=PUMP_COLOR, marker="o", lw=1.8, label="10-yr pumping"),
        Line2D([0], [0], color=DROUGHT_COLOR, lw=1.8, ls="--", label="10-yr drought deficit"),
        Line2D([0], [0], color=MATCH_COLOR, marker="*", ms=12, ls="none", label="Matched rate"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=3, fontsize=LEGEND_FS, frameon=False)
    out = FIG_DIR / "matched_deficit_10yr_rate_curve.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def write_summary(data: dict):
    lines = [
        "# Matched-deficit pumping rate (10-yr stress)",
        "",
        "**Script:** [`matched_deficit_10yr.py`](matched_deficit_10yr.py)  ",
        "**Figure:** [matched_deficit_10yr_rate_curve.png](figures/matched_deficit_10yr_rate_curve.png)",
        "",
        f"Deficit = `short_baseline` − member column storage at year index {END_STRESS_IDX} "
        f"({SPINUP_YEARS} spinup + {STRESS_YEARS} stress), per-cell clipped at zero, summed over "
        "active cells. Drought and pumping now share a 10-year stress length.",
        "",
        "The `5e-7`–`5e-6` bracket members end at year 49 and are complete. The `1e-7`–`1e-4` "
        "members carry a 10-yr recovery tail that is still running, but their year-49 state is "
        "final, so they contribute to the rate curve.",
        "",
        "## End-of-stress deficits (10⁶ m³)",
        "",
        "| Domain | Case | Total | Net |",
        "|--------|------|------:|----:|",
    ]
    for domain in DOMAINS:
        rec = data[domain]
        lines.append(
            f"| {DOMAIN_LABELS[domain]} | 10-yr drought | {rec['drought']['total_1e6']:.0f} | "
            f"{rec['drought']['net_1e6']:.0f} |"
        )
        for rate in RATES:
            r = rec["pump"][_rate_label(rate)]
            lines.append(
                f"| {DOMAIN_LABELS[domain]} | pumping {_rate_label(rate)} | "
                f"{r['total_1e6']:.0f} | {r['net_1e6']:.0f} |"
            )

    lines += [
        "",
        "## Matched rates",
        "",
        "| Domain | 10-yr drought target | Matched rate (m/h) | Bracketed by runs |",
        "|--------|---------------------:|-------------------:|-------------------|",
    ]
    for domain in DOMAINS:
        rec = data[domain]
        lines.append(
            f"| {DOMAIN_LABELS[domain]} | {rec['drought']['total_1e6']:.0f} | "
            f"{rec['match']['rate']:.2e} | {'yes' if rec['match']['bracketed'] else '**no — extrapolated**'} |"
        )

    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "conda activate /glade/work/bwest/conda-envs/droughts",
        "cd /glade/derecho/scratch/bwest/drought-ensemble",
        "python analysis/matched_deficit_10yr.py",
        "```",
        "",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n")
    print("wrote", SUMMARY_MD)


def main():
    data = load_all()
    OUT_JSON.write_text(json.dumps(data, indent=2))
    print("wrote", OUT_JSON)
    fig_deficit_vs_rate(data)
    write_summary(data)


if __name__ == "__main__":
    main()
