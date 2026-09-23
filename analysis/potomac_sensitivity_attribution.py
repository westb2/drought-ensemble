#!/usr/bin/env python3
"""Why are Potomac streamflow and near-surface storage more drought/pumping sensitive?

Reads slim per-year caches from ``psa_extract.py`` (219 h windows: window-mean
flow grid and local surface gain, near-surface / deep storage, WTD,
root-zone saturation, ParFlow evaptrans, CLM ET / energy fluxes) and runs:

0. Normalization: long-term ΔQ at the config outlet, the mainstem cell and the
   whole-domain surface export, in mm/yr, % of baseline, fraction of P and
   fraction of storage deficit / pumped volume.
1. Per-cell trait table (WTD, ET regime, connectivity, soils, veg).
2. Spatial attribution of Δ export (local surface gain) by period and class.
3. Near-surface (top 2 m) persistence per cell.
4. Hypothesis tests H1 (intermediate WTD), H2 (ET threshold), H3 (refill from
   above) with the skill metrics from ``wtd_threshold_vs_overland.py``.
5. Composition-vs-behavior counterfactual (swap class area fractions).
6. Class column budgets (anomalies, mm/yr).
7. Matched pumping source partition (storage / streamflow / ET).

Outputs: ``psa_*.png`` (drought_exploratory), ``_data/psa_summary.json``,
``_data/cell_traits_{domain}.nc``.

Reproduce::

    conda activate /glade/work/bwest/conda-envs/droughts
    cd /glade/derecho/scratch/bwest/drought-ensemble
    python analysis/psa_extract.py --workers 16     # or qsub analysis/psa_extract.pbs
    python analysis/potomac_sensitivity_attribution.py
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import parflow as pf
import xarray as xr
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis import psa_extract as X  # noqa: E402
from analysis import redo_recovery_with_50yr as R  # noqa: E402
from analysis import shallow_deep_shielding as SDS  # noqa: E402
from analysis import wtd_threshold_vs_overland as WT  # noqa: E402
from analysis.budyko_temp_persistent import (  # noqa: E402
    annual_hamon_pet_mm,
    annual_precip_mm,
    distance_to_stream_km,
    spearmanr,
)
from analysis.figure_paths import FIG_DIR, FIG_ROOT  # noqa: E402

DOMAINS = X.DOMAINS
LABEL = {"potomac2": "Potomac", "wolf2": "Wolf"}
CFG_OUTLET = {"potomac2": (66, 135), "wolf2": (18, 21)}  # (x, y) config.ini
AREA_CELL = X.CELL_AREA_M2
H_YR = 8760.0
MM_S_TO_MM_YR = 3600.0 * H_YR
BASE_YEARS = list(range(35, 40))
GS = slice(20, 40)  # Apr–Sep windows of the Oct-start water year
DATA_DIR = FIG_ROOT / "_data"
SUMMARY_JSON = DATA_DIR / "psa_summary.json"

CASES = {
    "d10": {"member": "10_year_drought", "label": "10-yr drought", "stress": (40, 50), "rec_end": 55},
    "d50": {"member": "50_year_drought", "label": "50-yr drought", "stress": (40, 90), "rec_end": 95},
    "pump": {"member": None, "label": "matched pumping", "stress": (40, 50), "rec_end": 60},
}
WTD_CLASSES = ["shallow (<1 m)", "intermediate (1–5 m)", "deep (>5 m)"]
ET_CLASSES = ["energy-limited", "threshold", "water-limited"]
WTD_COLORS = ["#56B4E9", "#E69F00", "#542788"]
ET_COLORS = ["#009E73", "#D55E00", "#8C510A"]
CASE_COLORS = {"d10": "#4A2410", "d50": "#140A05", "pump": "#7B3294"}
LABEL_FS, LEGEND_FS, TITLE_FS = R.LABEL_FS, R.LEGEND_FS, R.TITLE_FS


def case_member(domain: str, case: str) -> str:
    return X.MATCHED[domain] if case == "pump" else CASES[case]["member"]


def periods(case: str) -> dict[str, list[int]]:
    s0, s1 = CASES[case]["stress"]
    r1 = CASES[case]["rec_end"]
    out = {
        "stress_late": list(range(s1 - 5, s1)) if case != "d50" else list(range(85, 90)),
        "rec1": [s1],
        "rec2_5": list(range(s1 + 1, s1 + 5)),
    }
    if case == "pump":
        out["rec6_10"] = list(range(s1 + 5, r1))
    return out


# ---------------------------------------------------------------------------
# Cache access
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _index(domain: str) -> dict[tuple[str, int], Path]:
    idx = {}
    for _ens, mem, y, p in X.year_jobs(domain):
        idx[(mem, y)] = X.cache_path(domain, p)
    return idx


def base_key(domain: str, y: int) -> tuple[str, int]:
    """Baseline (member, year) for year y; steady late baseline remaps when missing."""
    if y <= 54:
        return ("short_baseline", y)
    idx = _index(domain)
    if ("baseline", y) in idx:
        return ("baseline", y)
    if domain == "wolf2":
        yy = 90 + (y % 5) if y >= 85 else 55 + (y % 5)
        return ("baseline", yy)
    return ("short_baseline", 50 + (y % 5))


def member_key(domain: str, member: str, y: int) -> tuple[str, int]:
    idx = _index(domain)
    if (member, y) in idx:
        return (member, y)
    if y < 40:
        return ("short_baseline", y)
    # 50-yr years 40/41 share hashes with the 10-yr member
    if member == "50_year_drought" and ("10_year_drought", y) in idx:
        return ("10_year_drought", y)
    raise KeyError((domain, member, y))


@lru_cache(maxsize=512)
def year_ds(domain: str, member: str, y: int) -> xr.Dataset:
    """Slim year cache; ``q``/``gain`` are window means (snapshots kept as ``*_snap``).

    Snapshot flow aliases flashy upland cells: the repeated forcing year puts
    the same storm hours at the same 219 h snapshot times every year.
    """
    key = base_key(domain, y) if member == "BASE" else member_key(domain, member, y)
    path = _index(domain)[key]
    with xr.open_dataset(path) as ds, xr.open_dataset(path.with_name(path.stem + "_qwm.nc")) as wm:
        out = ds.load().rename({"q": "q_snap", "gain": "gain_snap"})
        out["q"] = wm["q_wm"].load()
        out["gain"] = wm["gain_wm"].load()
        return out


def base_prev_end(domain: str, y: int, var: str) -> np.ndarray:
    """End-of-previous-year baseline state on the same (possibly remapped) track.

    Keeps baseline ΔS continuous when late years are remapped onto an earlier
    steady year (Potomac y≥55 → short_baseline 50–54).
    """
    mem, yy = base_key(domain, y)
    idx = _index(domain)
    key = (mem, yy - 1) if (mem, yy - 1) in idx else ("short_baseline", yy - 1)
    with xr.open_dataset(idx[key]) as ds:
        return np.asarray(ds[var].isel(time=-1).values, dtype=np.float64)


def annual_mean(domain: str, member: str, y: int, var: str) -> np.ndarray:
    return np.asarray(year_ds(domain, member, y)[var].mean("time").values, dtype=np.float64)


def end_state(domain: str, member: str, y: int, var: str) -> np.ndarray:
    return np.asarray(year_ds(domain, member, y)[var].isel(time=-1).values, dtype=np.float64)


def period_mean(domain: str, member: str, years: list[int], var: str) -> np.ndarray:
    return np.mean([annual_mean(domain, member, y, var) for y in years], axis=0)


@lru_cache(maxsize=None)
def statics(domain: str) -> dict:
    ds = year_ds(domain, "short_baseline", 39)
    active = np.isfinite(np.asarray(ds["q"].isel(time=0).values))
    qb = period_mean(domain, "short_baseline", BASE_YEARS, "q")
    qb = np.where(active, qb, np.nan)
    oy, ox = np.unravel_index(np.nanargmax(qb), qb.shape)
    streams, _ = R.stream_mask(domain)
    return {
        "active": active,
        "n": int(active.sum()),
        "area_m2": float(active.sum()) * AREA_CELL,
        "main_outlet": (int(ox), int(oy)),
        "streams": streams & active,
    }


def to_mm_yr(m3_per_h, area_m2):
    return np.asarray(m3_per_h) * H_YR / area_m2 * 1000.0


# ---------------------------------------------------------------------------
# Forcing: per-window precip and Hamon PET (mm per 219 h window)
# ---------------------------------------------------------------------------

def forcing_219h(domain: str, wetness: str) -> dict[str, np.ndarray]:
    cache = FIG_ROOT / "_cache" / "psa" / f"forcing_{domain}_{wetness}.npz"
    if cache.exists():
        z = np.load(cache)
        return {"P": z["P"], "PET": z["PET"]}
    fdir = ROOT / "domains" / domain / "inputs" / f"{domain}_{wetness}" / "forcing"
    pfiles = sorted(fdir.glob("CW3E.APCP.*_to_*.pfb"))
    tfiles = sorted(fdir.glob("CW3E.Temp.*_to_*.pfb"))
    lat = np.deg2rad(39.0 if domain.startswith("potomac") else 35.0)
    p_h, pet_h = [], []
    for i, (fp, ft) in enumerate(zip(pfiles, tfiles)):
        p = pf.read_pfb(str(fp)) * 3600.0  # mm/h
        t_c = np.mean(pf.read_pfb(str(ft)), axis=0) - 273.15
        doy = ((274 - 1 + i) % 365) + 1
        decl = 0.4093 * np.sin(2 * np.pi * (doy - 81) / 365.0)
        ha = np.arccos(float(np.clip(-np.tan(lat) * np.tan(decl), -1, 1)))
        daylen = 24.0 * ha / np.pi
        es = 0.6108 * np.exp(17.27 * t_c / (t_c + 237.3))
        pet_day = np.maximum(29.8 * daylen * es / (t_c + 273.2), 0.0)
        p_h.append(p)
        pet_h.append(np.repeat(pet_day[None] / 24.0, p.shape[0], axis=0))
    p_h = np.concatenate(p_h)[: 40 * 219]
    pet_h = np.concatenate(pet_h)[: 40 * 219]
    P = p_h.reshape(40, 219, *p_h.shape[1:]).sum(1)
    PET = pet_h.reshape(40, 219, *pet_h.shape[1:]).sum(1)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, P=P, PET=PET)
    return {"P": P, "PET": PET}


def year_wetness(case: str, y: int) -> str:
    s0, s1 = CASES[case]["stress"]
    return "dry" if case in ("d10", "d50") and s0 <= y < s1 else "average"


# ---------------------------------------------------------------------------
# Step 0: normalization
# ---------------------------------------------------------------------------

def flow_measures(domain: str, member: str, y: int) -> dict[str, float]:
    ds = year_ds(domain, member, y)
    st = statics(domain)
    cx, cy = CFG_OUTLET[domain]
    mx, my = st["main_outlet"]
    q = ds["q"].values
    g = ds["gain"].values
    return {
        "cfg": float(np.mean(q[:, cy, cx])),
        "main": float(np.mean(q[:, my, mx])),
        "export": float(np.mean(np.nansum(g, axis=(1, 2)))),
    }


def total_storage_m3(domain: str, member: str, y: int) -> float:
    ds = year_ds(domain, member, y)
    s = ds["s_ns"].isel(time=-1).values + ds["s_deep"].isel(time=-1).values
    return float(np.nansum(s)) * AREA_CELL


def step0_normalization() -> dict:
    out = {}
    for d in DOMAINS:
        st = statics(d)
        area = st["area_m2"]
        p_mm = float(np.nanmean(np.where(st["active"], annual_precip_mm(d), np.nan)))
        out[d] = {"area_km2": area / 1e6, "P_mm": p_mm, "main_outlet_xy": st["main_outlet"],
                  "cfg_outlet_xy": CFG_OUTLET[d], "cases": {}}
        base = {m: np.mean([flow_measures(d, "BASE", y)[m] for y in range(40, 55)])
                for m in ("cfg", "main", "export")}
        out[d]["baseline_m3h"] = base
        out[d]["baseline_mm_yr"] = {m: float(to_mm_yr(v, area)) for m, v in base.items()}
        for case in CASES:
            mem = case_member(d, case)
            s0, s1 = CASES[case]["stress"]
            r_end = CASES[case]["rec_end"]
            years = list(range(40, r_end)) if case != "d50" else [40, 41, *range(85, 95)]
            yearly = {}
            for y in years:
                fm = flow_measures(d, mem, y)
                fb = flow_measures(d, "BASE", y)
                yearly[y] = {m: (fm[m], fb[m]) for m in fm}
            # storage deficit at end of stress
            if case == "d50":
                pair = SDS.zone_deficit_pair(d, 50)
                tot = SDS.domain_zone_totals_m3(pair)
                deficit = tot["shallow_end"] + tot["deep_end"]
            else:
                deficit = total_storage_m3(d, "BASE", s1 - 1) - total_storage_m3(d, mem, s1 - 1)
            res = {"deficit_m3": deficit, "periods": {}, "yearly_pct": {}}
            if case == "pump":
                rate = float(mem.split("_")[1])
                res["pumped_m3"] = rate * area * H_YR * (s1 - s0)
            for m in ("cfg", "main", "export"):
                res["yearly_pct"][m] = {
                    int(y): 100.0 * (v[m][0] - v[m][1]) / v[m][1] if v[m][1] else np.nan
                    for y, v in yearly.items()
                }
            for pname, yrs in periods(case).items():
                yrs = [y for y in yrs if y in yearly]
                pr = {}
                for m in ("cfg", "main", "export"):
                    dq = np.mean([yearly[y][m][0] - yearly[y][m][1] for y in yrs])
                    qb = np.mean([yearly[y][m][1] for y in yrs])
                    dq_mm = float(to_mm_yr(dq, area))
                    pr[m] = {
                        "dQ_m3h": float(dq),
                        "dQ_mm_yr": dq_mm,
                        "pct_of_Q": float(100 * dq / qb) if qb else np.nan,
                        "pct_of_P": float(100 * dq_mm / p_mm),
                        "cum_m3": float(dq * H_YR * len(yrs)),
                        "cum_frac_deficit": float(dq * H_YR * len(yrs) / deficit) if deficit else np.nan,
                    }
                    if case == "pump":
                        pr[m]["cum_frac_pumped"] = float(dq * H_YR * len(yrs) / res["pumped_m3"])
                res["periods"][pname] = pr
            out[d]["cases"][case] = res
    return out


def fig_normalization(norm: dict) -> Path:
    """Yearly % anomaly at config outlet vs mainstem vs whole-domain export."""
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.0), sharex=True, sharey="row",
                             constrained_layout=True)
    styles = {"cfg": ("config outlet", ":", "o"), "main": ("mainstem outlet", "-", "^"),
              "export": ("domain surface export", "--", "s")}
    for row, case in enumerate(("d10", "pump")):
        for col, d in enumerate(DOMAINS):
            ax = axes[row, col]
            s0, s1 = CASES[case]["stress"]
            ax.axvspan(0, s1 - s0, color=R.PERIOD_DROUGHT_FACE, alpha=R.PERIOD_DROUGHT_ALPHA, lw=0)
            ax.axvspan(s1 - s0, CASES[case]["rec_end"] - s0, color=R.PERIOD_RECOVERY_FACE,
                       alpha=R.PERIOD_RECOVERY_ALPHA, lw=0)
            for m, (lab, ls, mk) in styles.items():
                yp = norm[d]["cases"][case]["yearly_pct"][m]
                ys = sorted(yp)
                ax.plot(np.array(ys) - s0 + 0.5, [yp[y] for y in ys], ls=ls, marker=mk, ms=4.5,
                        color=CASE_COLORS[case], lw=1.6, label=lab)
            ax.axhline(0, color="0.3", lw=0.8)
            ax.grid(True, alpha=0.28)
            ax.xaxis.set_major_locator(MultipleLocator(5))
            if row == 0:
                ax.set_title(LABEL[d], fontsize=TITLE_FS)
            if col == 0:
                ax.set_ylabel(f"{CASES[case]['label']}\nannual flow anomaly (%)", fontsize=LABEL_FS)
    for ax in axes[0]:
        ax.set_ylim(-100, 60)
    fig.supxlabel("Years since stress onset", fontsize=LABEL_FS)
    handles = [Line2D([0], [0], color="0.3", ls=ls, marker=mk, label=lab) for lab, ls, mk in styles.values()]
    handles += [Patch(facecolor=R.PERIOD_DROUGHT_FACE, alpha=0.25, label="stress"),
                Patch(facecolor=R.PERIOD_RECOVERY_FACE, alpha=0.4, label="recovery")]
    fig.legend(handles=handles, loc="outside upper center", ncol=5, fontsize=LEGEND_FS, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_flow_normalization.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------
# Step 1: trait table
# ---------------------------------------------------------------------------

def _dominant_veg(domain: str, shape) -> np.ndarray:
    raw = Path(str(_index(domain)[("short_baseline", 39)])).name.replace(".nc", "")
    vegm = ROOT / "domains" / domain / "raw_runs" / raw / "drv_vegm.dat"
    arr = np.loadtxt(vegm, skiprows=2)
    ny, nx = shape
    out = np.full(shape, np.nan)
    for row in arr:
        i, j = int(row[0]) - 1, int(row[1]) - 1
        if j < ny and i < nx:
            out[j, i] = float(np.argmax(row[7:]) + 1)
    return out


DZ_TOP_DOWN = X.DZ_M[::-1]
DEPTH_CENTER_TOP_DOWN = np.cumsum(DZ_TOP_DOWN) - DZ_TOP_DOWN / 2


def shallowest_wt_depth(domain: str, member: str, years: list[int]) -> np.ndarray:
    """Time-mean depth (m) to the uppermost saturated water table, perched or regional.

    ``wtd`` is measured up from the bottom, so a saturated lens resting on an
    unsaturated interval (e.g. Potomac uplands, layer z5 at 2–7 m) is invisible
    to it. Here: first layer from the top with pressure head ≥ 0, water table at
    center depth − head, floored at 0.
    """
    acc = []
    for y in years:
        key = base_key(domain, y) if member == "BASE" else member_key(domain, member, y)
        with xr.open_dataset(_index(domain)[key]) as c:
            src = c.attrs["source_219h"]
        with xr.open_dataset(src) as raw:
            p = np.asarray(raw["pressure"].values)[:, ::-1]  # time, z top→bottom
        sat = p >= 0.0
        first = np.argmax(sat, axis=1)
        any_sat = sat.any(axis=1)
        head = np.take_along_axis(p, first[:, None], axis=1)[:, 0]
        depth = np.maximum(DEPTH_CENTER_TOP_DOWN[first] - head, 0.0)
        acc.append(np.where(any_sat, depth, DZ_TOP_DOWN.sum()))
    return np.mean(np.concatenate(acc), axis=0)


def breakpoint_fit(x: np.ndarray, y: np.ndarray) -> dict:
    """y = a + b·min(x − s_c, 0): flat above s_c, linear below."""
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    best = {"sse": np.inf}
    for sc in np.linspace(0.40, 1.0, 61):
        h = np.minimum(x - sc, 0.0)
        A = np.column_stack([np.ones_like(h), h])
        coef, res, *_ = np.linalg.lstsq(A, y, rcond=None)
        sse = float(np.sum((A @ coef - y) ** 2))
        if sse < best["sse"]:
            best = {"sse": sse, "s_c": float(sc), "a": float(coef[0]), "b": float(coef[1])}
    best["r2"] = 1 - best["sse"] / float(np.sum((y - y.mean()) ** 2))
    return best


def step1_traits() -> dict:
    traits = {}
    pooled_x, pooled_y = [], []
    for d in DOMAINS:
        st = statics(d)
        act = st["active"]
        f_avg = forcing_219h(d, "average")
        f_dry = forcing_219h(d, "dry")
        stacks = {v: np.stack([year_ds(d, "short_baseline", y)[v].values for y in BASE_YEARS])
                  for v in ("wtd", "sat_rz", "q", "gain", "qflx_evap_tot", "eflx_lh_tot",
                            "eflx_sh_tot", "pf_et_ns", "qflx_tran_veg")}
        dry_years = list(range(45, 50))
        dstk = {v: np.stack([year_ds(d, "10_year_drought", y)[v].values for y in dry_years])
                for v in ("sat_rz", "qflx_evap_tot", "eflx_lh_tot", "eflx_sh_tot", "wtd")}
        wtd = stacks["wtd"]
        wtd_mean = wtd.mean(axis=(0, 1))
        wtd_p5 = np.percentile(wtd, 5, axis=(0, 1))
        wtd_p95 = np.percentile(wtd, 95, axis=(0, 1))
        frac_lt2 = np.mean(wtd < 2.0, axis=(0, 1))
        wclass = np.where(wtd_mean < 1.0, 0, np.where(wtd_mean < 5.0, 1, 2)).astype(float)
        wclass[~act] = np.nan

        et_w = stacks["qflx_evap_tot"] * 219 * 3600  # mm per window
        et_dw = dstk["qflx_evap_tot"] * 219 * 3600
        pet_b = f_avg["PET"][None]
        pet_d = f_dry["PET"][None]
        ef_b = stacks["eflx_lh_tot"] / np.maximum(stacks["eflx_lh_tot"] + stacks["eflx_sh_tot"], 1.0)
        ef_d = dstk["eflx_lh_tot"] / np.maximum(dstk["eflx_lh_tot"] + dstk["eflx_sh_tot"], 1.0)
        sat_b_gs = stacks["sat_rz"][:, GS].mean(axis=(0, 1))
        sat_d_gs = dstk["sat_rz"][:, GS].mean(axis=(0, 1))
        # pooled breakpoint of GS evaporative fraction on root-zone saturation
        xs = np.concatenate([stacks["sat_rz"][:, GS][:, :, act].ravel(), dstk["sat_rz"][:, GS][:, :, act].ravel()])
        ys = np.concatenate([ef_b[:, GS][:, :, act].ravel(), ef_d[:, GS][:, :, act].ravel()])
        bp = breakpoint_fit(xs, ys)
        pooled_x.append(xs)
        pooled_y.append(ys)
        # per-cell slope of GS EF on sat_rz (baseline + drought windows)
        xc = np.concatenate([stacks["sat_rz"][:, GS], dstk["sat_rz"][:, GS]], axis=0).reshape(-1, *act.shape)
        yc = np.concatenate([ef_b[:, GS], ef_d[:, GS]], axis=0).reshape(-1, *act.shape)
        xm, ym = xc.mean(0), yc.mean(0)
        slope = np.sum((xc - xm) * (yc - ym), 0) / np.maximum(np.sum((xc - xm) ** 2, 0), 1e-12)
        et_ratio = (et_dw[:, GS].sum(1).mean(0) / np.maximum(pet_d[:, GS].sum(1).mean(0), 1e-6)) / np.maximum(
            et_w[:, GS].sum(1).mean(0) / np.maximum(pet_b[:, GS].sum(1).mean(0), 1e-6), 1e-6)
        p_ann = f_avg["P"].sum(0)
        pet_ann = f_avg["PET"].sum(0)
        q = stacks["q"]
        part = np.mean(q > 1.0, axis=(0, 1))
        qmean = q.mean(axis=(0, 1))
        gain_mm = stacks["gain"].mean(axis=(0, 1)) * H_YR / AREA_CELL * 1000.0
        ds0 = year_ds(d, "short_baseline", 39)
        raw219 = xr.open_dataset(ds0.attrs["source_219h"])
        perm_top = np.asarray(raw219["perm_z"].isel(z=9).values)
        perm_mid = np.asarray(raw219["perm_z"].isel(z=5).values)
        por_top = np.asarray(raw219["porosity"].isel(z=9).values)
        sx = np.asarray(raw219["slopex"].values).squeeze()
        sy = np.asarray(raw219["slopey"].values).squeeze()
        raw219.close()
        dist = distance_to_stream_km(st["streams"], act)
        swt = shallowest_wt_depth(d, "short_baseline", BASE_YEARS)
        swt_d = shallowest_wt_depth(d, "10_year_drought", dry_years)
        swt_class = np.where(swt < 1.0, 0, np.where(swt < 5.0, 1, 2)).astype(float)
        t = {
            "swt_mean": swt, "swt_drought_mean": swt_d, "swt_class": swt_class,
            "perched": ((wtd_mean - swt) > 5.0).astype(float),
            "active": act.astype(float),
            "streams": st["streams"].astype(float),
            "wtd_mean": wtd_mean, "wtd_p5": wtd_p5, "wtd_p95": wtd_p95,
            "wtd_range": wtd_p95 - wtd_p5, "frac_wtd_lt2": frac_lt2, "wtd_class": wclass,
            "wtd_drought_mean": dstk["wtd"].mean(axis=(0, 1)),
            "sat_rz_gs_base": sat_b_gs, "sat_rz_gs_drought": sat_d_gs,
            "beta_gs_base": np.clip((sat_b_gs - 0.2) / 0.8, 0, 1),
            "ef_gs_base": ef_b[:, GS].mean(axis=(0, 1)), "ef_gs_drought": ef_d[:, GS].mean(axis=(0, 1)),
            "ef_sat_slope": slope, "et_pet_ratio_change": et_ratio,
            "et_base_mm": stacks["qflx_evap_tot"].mean(axis=(0, 1)) * MM_S_TO_MM_YR,
            "tran_base_mm": stacks["qflx_tran_veg"].mean(axis=(0, 1)) * MM_S_TO_MM_YR,
            "recharge_base_mm": stacks["pf_et_ns"].mean(axis=(0, 1)) * H_YR * 1000.0,
            "P_mm": p_ann, "PET_mm": pet_ann, "phi": pet_ann / np.maximum(p_ann, 1e-6),
            "participation": part, "q_mean": qmean, "log_q": np.log10(np.maximum(qmean, 1e-3)),
            "gain_base_mm": gain_mm, "dist_km": dist,
            "perm_top": perm_top, "perm_mid": perm_mid, "por_top": por_top,
            "slope": np.hypot(sx, sy), "veg": _dominant_veg(d, act.shape),
        }
        for k in t:
            t[k] = np.where(act, np.asarray(t[k], dtype=np.float64), np.nan)
        t["_breakpoint_domain"] = bp
        traits[d] = t
        print(d, "breakpoint (own domain)", bp, flush=True)
    # One critical saturation for both domains: Wolf alone never leaves the
    # plateau, so its own fit pins to the search edge.
    bp = breakpoint_fit(np.concatenate(pooled_x), np.concatenate(pooled_y))
    print("pooled breakpoint", bp, flush=True)
    sc, tol = bp["s_c"], 0.01
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for d in DOMAINS:
        t = traits[d]
        eclass = np.where(t["sat_rz_gs_base"] < sc - tol, 2,
                          np.where(t["sat_rz_gs_drought"] < sc - tol, 1, 0)).astype(float)
        eclass[~(t["active"] == 1)] = np.nan
        t["et_class"] = eclass
        t["joint_class"] = t["wtd_class"] * 3 + eclass
        t["swt_joint_class"] = t["swt_class"] * 3 + eclass
        t["_breakpoint"] = bp
        ds_out = xr.Dataset({k: (("y", "x"), v) for k, v in t.items() if not k.startswith("_")},
                            attrs={"breakpoint_pooled_" + k: v for k, v in bp.items()})
        ds_out.to_netcdf(DATA_DIR / f"cell_traits_{d}.nc")
    return traits


# ---------------------------------------------------------------------------
# Step 2: Δ export attribution
# ---------------------------------------------------------------------------

def delta_gain(domain: str, case: str, years: list[int]) -> np.ndarray:
    """Per-cell Δ local surface gain (mm/yr); negative = cell exports less."""
    mem = case_member(domain, case)
    dm = [annual_mean(domain, mem, y, "gain") - annual_mean(domain, "BASE", y, "gain") for y in years]
    return np.mean(dm, axis=0) * H_YR / AREA_CELL * 1000.0


def class_shares(values: np.ndarray, classes: np.ndarray, n: int) -> dict:
    tot = np.nansum(values)
    out = {}
    for k in range(n):
        m = classes == k
        out[k] = {
            "area_frac": float(np.mean(m[np.isfinite(classes)])),
            "sum": float(np.nansum(values[m])),
            "share": float(np.nansum(values[m]) / tot) if tot else np.nan,
            "mean": float(np.nanmean(values[m])) if m.any() else np.nan,
        }
    return out


def step2_attribution(traits: dict) -> dict:
    out = {}
    for d in DOMAINS:
        t = traits[d]
        out[d] = {}
        for case in CASES:
            out[d][case] = {}
            for pname, yrs in periods(case).items():
                dg = delta_gain(d, case, yrs)
                strm = t["streams"] == 1
                out[d][case][pname] = {
                    "map": dg,
                    "total_mm_yr_domain": float(np.nansum(dg) / np.sum(np.isfinite(t["active"]))),
                    "by_wtd": class_shares(dg, t["wtd_class"], 3),
                    "by_et": class_shares(dg, t["et_class"], 3),
                    "by_joint": class_shares(dg, t["joint_class"], 9),
                    "by_swt": class_shares(dg, t["swt_class"], 3),
                    "by_swt_joint": class_shares(dg, t["swt_joint_class"], 9),
                    "stream_share": float(np.nansum(dg[strm]) / np.nansum(dg)) if np.nansum(dg) else np.nan,
                }
        out[d]["baseline_by_wtd"] = class_shares(t["gain_base_mm"], t["wtd_class"], 3)
        out[d]["baseline_by_et"] = class_shares(t["gain_base_mm"], t["et_class"], 3)
        out[d]["baseline_by_joint"] = class_shares(t["gain_base_mm"], t["joint_class"], 9)
        out[d]["baseline_by_swt"] = class_shares(t["gain_base_mm"], t["swt_class"], 3)
        out[d]["baseline_by_swt_joint"] = class_shares(t["gain_base_mm"], t["swt_joint_class"], 9)
    return out


# Figures group cells by shallowest water table (perched or regional) × ET regime.
JOINT_KEY = "swt_joint_class"
JOINT_SHOW = [0, 3, 4, 6, 8]  # classes with >1% area in either domain
JOINT_LABEL = {
    0: "WT <1 m · energy-limited",
    3: "WT 1–5 m · energy-limited",
    4: "WT 1–5 m · threshold",
    6: "WT >5 m · energy-limited",
    7: "WT >5 m · threshold",
    8: "WT >5 m · water-limited",
}
JOINT_COLOR = {0: "#56B4E9", 3: "#E69F00", 4: "#D55E00", 6: "#542788", 7: "#CC79A7", 8: "#8C510A"}


def _joint_other(k: int) -> bool:
    return k not in JOINT_SHOW


def _map(ax, z, d, traits, norm, cmap="RdBu"):
    t = traits[d]
    zz, _ = R._prepare_map(z, t["streams"] == 1, t["active"] == 1)
    im = ax.imshow(zz, cmap=cmap, norm=norm, interpolation="nearest", aspect="equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    return im


def fig_attribution(att: dict, traits: dict) -> Path:
    """Long-term Δ export maps + where the loss sits vs where area/export sit."""
    cols = [("d10", "rec2_5", "10-yr drought,\nrecovery yrs 2–5"),
            ("d50", "rec2_5", "50-yr drought,\nrecovery yrs 2–5"),
            ("pump", "stress_late", "matched pumping,\nlast 5 pumping yrs"),
            ("pump", "rec2_5", "matched pumping,\nrecovery yrs 2–5")]
    fig = plt.figure(figsize=(14.0, 10.0), constrained_layout=True)
    gs = fig.add_gridspec(3, 4, height_ratios=[1.25, 1.0, 1.15])
    lim = 20
    norm = TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim)
    im = None
    for r, d in enumerate(DOMAINS):
        for c, (case, pname, title) in enumerate(cols):
            ax = fig.add_subplot(gs[r, c])
            z = np.clip(att[d][case][pname]["map"], -lim, lim)
            im = _map(ax, z, d, traits, norm)
            if r == 0:
                ax.set_title(title, fontsize=11)
            if c == 0:
                ax.set_ylabel(LABEL[d], fontsize=LABEL_FS)
    cb = fig.colorbar(im, ax=fig.axes[: 2 * len(cols)], shrink=0.7, location="right", pad=0.01, extend="both")
    cb.set_label("Δ local surface export (mm/yr)", fontsize=LABEL_FS)
    bars = [("area", "area"), ("base", "baseline\nexport")] + [
        ((c, p), f"{'drought' if c != 'pump' else 'pumping'}\n"
                 f"{'10-yr' if c == 'd10' else '50-yr' if c == 'd50' else ''}"
                 f"{' rec 2–5' if p == 'rec2_5' else ' last 5'}".replace("\n ", "\n"))
        for c, p, _ in cols]
    for di, d in enumerate(DOMAINS):
        ax = fig.add_subplot(gs[2, 2 * di: 2 * di + 2])
        t = traits[d]
        act = t["active"] == 1
        for bi, (key, lab) in enumerate(bars):
            bottom = 0.0
            for k in list(JOINT_SHOW) + ["other"]:
                if key == "area":
                    if k == "other":
                        v = float(np.mean([_joint_other(int(j)) for j in t[JOINT_KEY][act]]))
                    else:
                        v = float(np.mean(t[JOINT_KEY][act] == k))
                else:
                    sh = att[d]["baseline_by_swt_joint"] if key == "base" else att[d][key[0]][key[1]]["by_swt_joint"]
                    if k == "other":
                        v = sum(sh[j]["share"] for j in range(9) if _joint_other(j) and np.isfinite(sh[j]["share"]))
                    else:
                        v = sh[k]["share"]
                if not np.isfinite(v) or v == 0:
                    continue
                color = "0.8" if k == "other" else JOINT_COLOR[k]
                ax.bar(bi, v, bottom=bottom if v > 0 else 0, color=color, width=0.72,
                       edgecolor="white", lw=0.4)
                if v > 0:
                    bottom += v
        ax.axvline(1.5, color="0.5", lw=0.8, ls=":")
        ax.set_xticks(range(len(bars)))
        ax.set_xticklabels([b[1] for b in bars], fontsize=9)
        ax.set_ylim(0, 1.05)
        ax.set_title(LABEL[d], fontsize=TITLE_FS)
        ax.grid(True, axis="y", alpha=0.28)
        if di == 0:
            ax.set_ylabel("Share of domain total (–)", fontsize=LABEL_FS)
    handles = [Patch(facecolor=JOINT_COLOR[k], label=JOINT_LABEL[k]) for k in JOINT_SHOW]
    handles.append(Patch(facecolor="0.8", label="other classes"))
    fig.legend(handles=handles, loc="outside lower center", ncol=6, fontsize=LEGEND_FS - 1, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_export_attribution.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------
# Step 3: near-surface persistence
# ---------------------------------------------------------------------------

def ns_persistence(domain: str, case: str) -> dict:
    mem = case_member(domain, case)
    s0, s1 = CASES[case]["stress"]
    def ns_def(y):
        return end_state(domain, "BASE", y, "s_ns") - end_state(domain, mem, y, "s_ns")
    def deep_def(y):
        return end_state(domain, "BASE", y, "s_deep") - end_state(domain, mem, y, "s_deep")
    d_end = ns_def(s1 - 1)
    out = {"ns_end": d_end, "deep_end": deep_def(s1 - 1)}
    for k in (1, 2, 5):
        dk = ns_def(s1 - 1 + k)
        out[f"ns_rec{k}"] = dk
        out[f"R{k}"] = np.where(d_end > 1e-3, dk / np.maximum(d_end, 1e-3), np.nan)
    # within-stress regeneration: last 5 stress years (d50: 85–89 not extracted → 10-yr only)
    if case in ("d10", "pump"):
        yrs = list(range(s1 - 5, s1))
        dsn = np.concatenate([year_ds(domain, "BASE", y)["s_ns"].values - year_ds(domain, mem, y)["s_ns"].values
                              for y in yrs])
        bsn = np.concatenate([year_ds(domain, "BASE", y)["s_ns"].values for y in yrs])
        pw = forcing_219h(domain, "dry" if case == "d10" else "average")["P"]
        pdom = np.nanmean(np.where(statics(domain)["active"], pw, np.nan), axis=(1, 2))
        wet = np.tile(pdom >= np.percentile(pdom, 75), len(yrs))
        ok = np.abs(dsn[wet]) <= 0.10 * np.maximum(bsn[wet], 1e-6)
        out["regen"] = np.mean(ok, axis=0)
    return out


def step3_ns(traits: dict) -> dict:
    out = {}
    for d in DOMAINS:
        out[d] = {}
        act = traits[d]["active"] == 1
        for case in CASES:
            r = ns_persistence(d, case)
            for k, v in r.items():
                r[k] = np.where(act, v, np.nan)
            tot_end = np.nansum(np.maximum(r["ns_end"], 0))
            r["domain"] = {
                "ns_end_m3": float(tot_end * AREA_CELL),
                **{f"ns_rec{k}_frac": float(np.nansum(np.maximum(r[f"ns_rec{k}"], 0)) / tot_end) for k in (1, 2, 5)},
            }
            for key, n in (("wtd_class", 3), ("et_class", 3), ("swt_class", 3), ("swt_joint_class", 9)):
                cl = traits[d][key]
                r[f"by_{key}"] = {
                    k: {
                        "ns_end_share": float(np.nansum(np.maximum(r["ns_end"], 0)[cl == k]) / tot_end),
                        "ns_rec2_share": float(np.nansum(np.maximum(r["ns_rec2"], 0)[cl == k]) /
                                               max(np.nansum(np.maximum(r["ns_rec2"], 0)), 1e-12)),
                        "R2_mass": float(np.nansum(np.maximum(r["ns_rec2"], 0)[cl == k]) /
                                         max(np.nansum(np.maximum(r["ns_end"], 0)[cl == k]), 1e-12)),
                        "regen_mean": float(np.nanmean(r["regen"][cl == k])) if "regen" in r and (cl == k).any() else np.nan,
                    }
                    for k in range(n) if (cl == k).any()
                }
            out[d][case] = r
    return out


# ---------------------------------------------------------------------------
# Step 4: hypothesis tests
# ---------------------------------------------------------------------------

def _skill(x, y, mass=None, low_x_selects=False):
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size < 50:
        return {}
    rho, _ = spearmanr(x, y)
    st = WT.optimal_threshold(x, y)
    qb = WT.quantile_bin_skill(x, y)
    res = {"n": int(x.size), "rho": rho, "step_r2": st["r2"], "step_thr": st["thr"], "bin_r2": qb["r2"]}
    if mass is not None:
        e = WT.enrichment_top(x, y, low_x_selects=low_x_selects, mass=np.asarray(mass)[ok])
        res["top20_mass"] = e.get("mass_fraction")
    return res


def _partial_spearman(x, y, groups):
    """Spearman of rank residuals after removing group means (class control)."""
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(groups)
    x, y, g = x[ok], y[ok], groups[ok]
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    for k in np.unique(g):
        m = g == k
        rx[m] -= rx[m].mean()
        ry[m] -= ry[m].mean()
    den = np.sqrt(np.sum(rx ** 2) * np.sum(ry ** 2))
    return float(np.sum(rx * ry) / den) if den > 0 else np.nan


def step4_tests(traits, att, ns) -> dict:
    out = {}
    for d in DOMAINS:
        t = traits[d]
        nonstream = (t["active"] == 1) & (t["streams"] != 1)
        loss_d = -att[d]["d10"]["rec2_5"]["map"]
        loss_p = -att[d]["pump"]["rec2_5"]["map"]
        loss_ps = -att[d]["pump"]["stress_late"]["map"]
        r2 = ns[d]["d10"]["R2"]
        nsend = np.maximum(ns[d]["d10"]["ns_end"], 0)
        deep = ns[d]["d10"]["deep_end"]
        preds = {
            "log_wtd": np.log10(np.maximum(t["wtd_mean"], 0.01)),
            "log_swt": np.log10(np.maximum(t["swt_mean"], 0.01)),
            "swt_drop": t["swt_drought_mean"] - t["swt_mean"],
            "wtd_range": t["wtd_range"],
            "frac_wtd_lt2": t["frac_wtd_lt2"],
            "sat_rz_gs_base": t["sat_rz_gs_base"],
            "et_pet_ratio_change": t["et_pet_ratio_change"],
            "ef_sat_slope": t["ef_sat_slope"],
            "log_q": t["log_q"],
            "phi": t["phi"],
            "deep_def_end": deep,
        }
        m = nonstream
        res = {"loss_d10_rec2_5": {}, "loss_pump_rec2_5": {}, "loss_pump_stress": {}, "ns_R2": {}}
        for pname, x in preds.items():
            res["loss_d10_rec2_5"][pname] = _skill(np.where(m, x, np.nan), loss_d)
            res["loss_pump_rec2_5"][pname] = _skill(np.where(m, x, np.nan), loss_p)
            res["loss_pump_stress"][pname] = _skill(np.where(m, x, np.nan), loss_ps)
            res["ns_R2"][pname] = _skill(np.where(m & (nsend > 0.01), x, np.nan), r2)
        joint = t["wtd_class"] * 3 + t["et_class"]
        res["H3_partial_rho_R2_vs_deep"] = _partial_spearman(np.where(m & (nsend > 0.01), deep, np.nan), r2, joint)
        xd = np.where(m & (nsend > 0.01), deep, np.nan)
        okd = np.isfinite(xd) & np.isfinite(r2)
        res["H3_rho_R2_vs_deep"] = spearmanr(xd[okd], r2[okd])[0]
        # 2-D class table: area, baseline export share, long-term loss share, NS R2 (mass)
        tab = {}
        base_exp = np.nansum(np.maximum(t["gain_base_mm"], 0))
        for wi in range(3):
            for ei in range(3):
                c = (t["wtd_class"] == wi) & (t["et_class"] == ei)
                if not c.any():
                    continue
                tab[f"{wi}{ei}"] = {
                    "area_frac": float(c.sum() / np.sum(t["active"] == 1)),
                    "base_export_share": float(np.nansum(np.maximum(t["gain_base_mm"], 0)[c]) / base_exp),
                    "loss_d10_share": float(np.nansum(loss_d[c]) / np.nansum(loss_d)),
                    "loss_pump_share": float(np.nansum(loss_p[c]) / np.nansum(loss_p)),
                    "ns_end_share": float(np.nansum(nsend[c]) / np.nansum(nsend)),
                    "ns_R2_mass": float(np.nansum(np.maximum(ns[d]["d10"]["ns_rec2"], 0)[c]) / max(np.nansum(nsend[c]), 1e-12)),
                }
        res["class_table"] = tab
        tab2 = {}
        for k in range(9):
            c = t["swt_joint_class"] == k
            if not c.any():
                continue
            tab2[str(k)] = {
                "area_frac": float(c.sum() / np.sum(t["active"] == 1)),
                "base_export_share": float(np.nansum(np.maximum(t["gain_base_mm"], 0)[c]) / base_exp),
                "loss_d10_share": float(np.nansum(loss_d[c]) / np.nansum(loss_d)),
                "loss_pump_share": float(np.nansum(loss_p[c]) / np.nansum(loss_p)),
                "ns_end_share": float(np.nansum(nsend[c]) / np.nansum(nsend)),
                "ns_R2_mass": float(np.nansum(np.maximum(ns[d]["d10"]["ns_rec2"], 0)[c]) / max(np.nansum(nsend[c]), 1e-12)),
                "perched_frac": float(np.nanmean(t["perched"][c])),
            }
        res["swt_class_table"] = tab2
        # participation-tercile interaction
        q = np.where(t["active"] == 1, t["log_q"], np.nan)
        terc = np.nanpercentile(q, [33.3, 66.7])
        qcl = np.where(q < terc[0], 0, np.where(q < terc[1], 1, 2)).astype(float)
        qcl[~np.isfinite(q)] = np.nan
        inter = {}
        for key in ("wtd_class", "et_class"):
            inter[key] = {}
            for ci in range(3):
                for qi in range(3):
                    c = (t[key] == ci) & (qcl == qi)
                    if c.sum() < 5:
                        continue
                    inter[key][f"{ci}{qi}"] = {
                        "n": int(c.sum()),
                        "loss_d10_mean": float(np.nanmean(loss_d[c])),
                        "ns_R2_mass": float(np.nansum(np.maximum(ns[d]["d10"]["ns_rec2"], 0)[c]) / max(np.nansum(nsend[c]), 1e-12)),
                    }
        res["overland_interaction"] = inter
        res["threshold_cells_flip_frac"] = float(np.nanmean(
            (t["sat_rz_gs_drought"] < t["_breakpoint"]["s_c"] - 0.01)[t["sat_rz_gs_base"] >= t["_breakpoint"]["s_c"] - 0.01]))
        out[d] = res
    return out


def fig_traits(traits: dict) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.3), constrained_layout=True)
    ax = axes[0]
    bins = np.logspace(-2, np.log10(400), 45)
    for d, c in zip(DOMAINS, ("#4A2410", "#B86B2B")):
        for key, ls in (("wtd_mean", "-"), ("swt_mean", "--")):
            w = traits[d][key]
            w = w[np.isfinite(w)]
            ax.hist(np.maximum(w, 0.011), bins=bins, histtype="step", lw=1.8, color=c, ls=ls,
                    weights=np.ones_like(w) / w.size)
    for x in (1, 2, 5):
        ax.axvline(x, color="0.5", ls=":", lw=1)
    ax.set_xscale("log")
    ax.set_xlabel("Baseline mean water-table depth (m)", fontsize=LABEL_FS)
    ax.set_ylabel("Fraction of cells", fontsize=LABEL_FS)
    ax.legend(handles=[Line2D([0], [0], color="#4A2410", lw=2, label="Potomac"),
                       Line2D([0], [0], color="#B86B2B", lw=2, label="Wolf"),
                       Line2D([0], [0], color="0.3", lw=1.8, label="regional WTD"),
                       Line2D([0], [0], color="0.3", lw=1.8, ls="--", label="shallowest (incl. perched)")],
              frameon=False, fontsize=9, loc="upper left")
    # EF vs sat pooled binned
    ax = axes[1]
    for d, c in zip(DOMAINS, ("#4A2410", "#B86B2B")):
        t = traits[d]
        for key, ls in (("base", "-"), ("drought", "--")):
            x = t[f"sat_rz_gs_{key}"]
            y = t[f"ef_gs_{key}"]
            ok = np.isfinite(x) & np.isfinite(y)
            xc, yc, _ = WT.binned_curve(x[ok], y[ok], 14)
            ax.plot(xc, yc, ls=ls, color=c, marker="o", ms=4)
        bp = t["_breakpoint"]
    for d, c in zip(DOMAINS, ("#4A2410", "#B86B2B")):
        ax.axvline(traits[d]["_breakpoint"]["s_c"], color=c, ls=":", lw=1.2)
    ax.set_xlabel("Growing-season root-zone saturation (–)", fontsize=LABEL_FS)
    ax.set_ylabel("Evaporative fraction LH/(LH+SH)", fontsize=LABEL_FS)
    ax.legend(handles=[Line2D([0], [0], color="0.3", ls="-", label="baseline"),
                       Line2D([0], [0], color="0.3", ls="--", label="10-yr drought (yrs 6–10)"),
                       Line2D([0], [0], color="0.3", ls=":", label="fitted breakpoint")],
              frameon=False, fontsize=9, loc="lower right")
    # class area fractions: water-table class × ET regime (hatch)
    ax = axes[2]
    xpos = {("potomac2", "wtd_class"): 0, ("potomac2", "swt_class"): 1,
            ("wolf2", "wtd_class"): 2.6, ("wolf2", "swt_class"): 3.6}
    hatches = ["", "//", ".."]
    for (d, key), xi in xpos.items():
        t = traits[d]
        act = t["active"] == 1
        bottom = 0
        for wi in range(3):
            for ei in range(3):
                f = np.mean((t[key][act] == wi) & (t["et_class"][act] == ei))
                if f <= 0:
                    continue
                ax.bar(xi, f, bottom=bottom, color=WTD_COLORS[wi], width=0.8,
                       hatch=hatches[ei], edgecolor="white", lw=0.5)
                if f > 0.04:
                    ax.text(xi, bottom + f / 2, f"{100 * f:.0f}%", ha="center", va="center", fontsize=8.5, color="white")
                bottom += f
    ax.set_xticks(list(xpos.values()))
    ax.set_xticklabels(["regional\nWTD", "shallowest\nWT"] * 2, fontsize=9)
    for d, xc in (("potomac2", 0.5), ("wolf2", 3.1)):
        ax.text(xc, 1.02, LABEL[d], ha="center", va="bottom", fontsize=11, fontweight="semibold",
                transform=ax.get_xaxis_transform())
    ax.set_ylabel("Fraction of cells", fontsize=LABEL_FS)
    hs = [Patch(facecolor=c, label=n) for n, c in zip(WTD_CLASSES, WTD_COLORS)]
    hs += [Patch(facecolor="0.55", hatch=h, edgecolor="white", label=n) for n, h in zip(ET_CLASSES, hatches)]
    ax.legend(handles=hs, frameon=False, fontsize=8.5, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    R.despine_axes(fig)
    out = FIG_DIR / "psa_trait_distributions.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


def fig_hypothesis_bins(traits, att, ns) -> Path:
    """Binned responses vs WTD and root-zone saturation, both domains."""
    fig, axes = plt.subplots(2, 4, figsize=(17.0, 7.6), sharex="col", sharey="row", constrained_layout=True)
    cols = [("log_wtd", "Baseline regional WTD (m)"), ("log_swt", "Baseline shallowest WT,\nincl. perched (m)"),
            ("sat_rz_gs_base", "Baseline GS root-zone saturation (–)"),
            ("log_q", r"log$_{10}$ baseline overland flow (m$^3$/h)")]
    for d, c in zip(DOMAINS, ("#4A2410", "#B86B2B")):
        t = traits[d]
        m = (t["active"] == 1) & (t["streams"] != 1)
        xs = {"log_wtd": np.log10(np.maximum(t["wtd_mean"], 0.01)),
              "log_swt": np.log10(np.maximum(t["swt_mean"], 0.01)),
              "sat_rz_gs_base": t["sat_rz_gs_base"], "log_q": t["log_q"]}
        nsend = np.maximum(ns[d]["d10"]["ns_end"], 0)
        for ci, (key, xl) in enumerate(cols):
            x = xs[key]
            for ri, (y, cond) in enumerate(((-att[d]["d10"]["rec2_5"]["map"], m),
                                            (ns[d]["d10"]["R2"], m & (nsend > 0.01)))):
                ok = cond & np.isfinite(x) & np.isfinite(y)
                xc, yc, _ = WT.binned_curve(x[ok], y[ok], 12)
                axes[ri, ci].plot(xc, yc, marker="o", color=c, lw=2, ms=5, label=LABEL[d])
                yp = -att[d]["pump"]["rec2_5"]["map"]
                if ri == 0:
                    okp = cond & np.isfinite(x) & np.isfinite(yp)
                    xc, yc, _ = WT.binned_curve(x[okp], yp[okp], 12)
                    axes[ri, ci].plot(xc, yc, marker="s", color=c, lw=1.4, ls="--", ms=4, mfc="white")
            axes[1, ci].set_xlabel(xl, fontsize=LABEL_FS)
    for ax in np.concatenate([axes[:, 0], axes[:, 1]]):
        ax.set_xticks([-2, -1, 0, 1, 2])
        ax.set_xticklabels(["0.01", "0.1", "1", "10", "100"])
        for v in (0, np.log10(2), np.log10(5)):
            ax.axvline(v, color="0.6", ls=":", lw=1)
    axes[0, 0].set_ylabel("Long-term export loss,\nrecovery yrs 2–5 (mm/yr)", fontsize=LABEL_FS)
    axes[1, 0].set_ylabel("Near-surface deficit left\nafter recovery yr 2 (fraction)", fontsize=LABEL_FS)
    for ax in axes.ravel():
        ax.grid(True, alpha=0.28)
        ax.axhline(0, color="0.4", lw=0.7)
    handles = [Line2D([0], [0], color=c, lw=2, label=LABEL[d]) for d, c in zip(DOMAINS, ("#4A2410", "#B86B2B"))]
    handles += [Line2D([0], [0], color="0.4", lw=2, marker="o", label="10-yr drought"),
                Line2D([0], [0], color="0.4", lw=1.4, ls="--", marker="s", mfc="white", label="matched pumping")]
    fig.legend(handles=handles, loc="outside upper center", ncol=4, fontsize=LEGEND_FS, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_hypothesis_bins.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


def fig_ns_maps(traits, ns) -> Path:
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 8.0), constrained_layout=True)
    for r, d in enumerate(DOMAINS):
        t = traits[d]
        panels = [
            (np.log10(np.maximum(t["swt_mean"], 0.01)), "Baseline shallowest water table\n(incl. perched; log$_{10}$ m)", "viridis_r", (-2, 1.5)),
            (1000 * np.maximum(ns[d]["d10"]["ns_end"], 0), "Near-surface deficit,\nend of 10-yr drought (mm)", "Oranges", (0, 250)),
            (ns[d]["d10"]["R2"], "Near-surface deficit left\nafter recovery yr 2 (fraction)", "magma_r", (0, 1)),
        ]
        for c, (z, title, cmap, (lo, hi)) in enumerate(panels):
            ax = axes[r, c]
            zz, st = R._prepare_map(z, t["streams"] == 1, t["active"] == 1)
            im = ax.imshow(zz, cmap=cmap, vmin=lo, vmax=hi, interpolation="nearest")
            ax.set_xticks([])
            ax.set_yticks([])
            for s in ax.spines.values():
                s.set_visible(False)
            if r == 0:
                ax.set_title(title, fontsize=11)
            if c == 0:
                ax.set_ylabel(LABEL[d], fontsize=LABEL_FS)
            fig.colorbar(im, ax=ax, shrink=0.7)
    out = FIG_DIR / "psa_ns_persistence_maps.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------
# Step 5: composition vs behavior
# ---------------------------------------------------------------------------

def step5_decomposition(traits, att, ns, class_key: str = "joint_class") -> dict:
    """Domain response = Σ_c a_c r_c; swap a_c between domains."""
    comp = {}
    for d in DOMAINS:
        t = traits[d]
        act = t["active"] == 1
        joint = t[class_key]
        classes = {}
        for k in range(9):
            c = act & (joint == k)
            if not c.any():
                continue
            nsend = np.maximum(ns[d]["d10"]["ns_end"], 0)
            classes[k] = {
                "a": float(c.sum() / act.sum()),
                "g_base": float(np.nanmean(t["gain_base_mm"][c])),
                "dg_d10": float(np.nanmean(att[d]["d10"]["rec2_5"]["map"][c])),
                "dg_pump": float(np.nanmean(att[d]["pump"]["rec2_5"]["map"][c])),
                "dg_pump_stress": float(np.nanmean(att[d]["pump"]["stress_late"]["map"][c])),
                "ns_end": float(np.nanmean(nsend[c])),
                "ns_rec2": float(np.nanmean(np.maximum(ns[d]["d10"]["ns_rec2"], 0)[c])),
            }
        comp[d] = classes

    def response(beh, frac):
        # Classes absent from the behavior domain have no response to borrow:
        # renormalise over shared classes and report the covered area fraction.
        a = {k: frac.get(k, 0.0) for k in beh}
        shared = [k for k in beh if a[k] > 0]
        s = sum(a[k] for k in shared)
        a = {k: a[k] / s for k in shared}
        gb = sum(a[k] * beh[k]["g_base"] for k in shared)
        out = {"coverage": s}
        for key in ("dg_d10", "dg_pump", "dg_pump_stress"):
            out[key + "_pct"] = 100 * sum(a[k] * beh[k][key] for k in shared) / gb
        ne = sum(a[k] * beh[k]["ns_end"] for k in shared)
        out["ns_R2"] = sum(a[k] * beh[k]["ns_rec2"] for k in shared) / ne if ne else np.nan
        return out

    res = {"classes": {d: {str(k): v for k, v in comp[d].items()} for d in DOMAINS}}
    fr = {d: {k: v["a"] for k, v in comp[d].items()} for d in DOMAINS}
    for beh in DOMAINS:
        for frac in DOMAINS:
            res[f"{beh}_behavior__{frac}_fractions"] = response(comp[beh], fr[frac])
    return res


def fig_decomposition(dec: dict) -> Path:
    metrics = [("dg_d10_pct", "10-yr drought, rec 2–5\nexport change (% of baseline)"),
               ("dg_pump_stress_pct", "Matched pumping, last 5 yrs\nexport change (% of baseline)"),
               ("dg_pump_pct", "Matched pumping, rec 2–5\nexport change (% of baseline)"),
               ("ns_R2", "Near-surface deficit left\nafter recovery yr 2 (fraction)")]
    combos = [("potomac2", "potomac2", "Potomac"), ("potomac2", "wolf2", "Potomac\nbehavior ×\nWolf mix"),
              ("wolf2", "potomac2", "Wolf\nbehavior ×\nPotomac mix"), ("wolf2", "wolf2", "Wolf")]
    colors = ["#4A2410", "#A67C52", "#E8C39E", "#B86B2B"]
    fig, axes = plt.subplots(1, 4, figsize=(15.0, 4.4), constrained_layout=True)
    for ax, (key, title) in zip(axes, metrics):
        vals = [dec[f"{b}_behavior__{f}_fractions"][key] for b, f, _ in combos]
        ax.bar(range(4), vals, color=colors, edgecolor=["none", "#4A2410", "#B86B2B", "none"], hatch=["", "//", "//", ""])
        ax.set_xticks(range(4))
        ax.set_xticklabels([c[2] for c in combos], fontsize=9, rotation=0)
        ax.set_title(title, fontsize=11)
        ax.axhline(0, color="0.3", lw=0.8)
        ax.grid(True, axis="y", alpha=0.28)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_composition_vs_behavior.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------
# Step 6: class column budgets
# ---------------------------------------------------------------------------

BUDGET_TERMS = [
    ("precip", "precipitation", "#000000"),
    ("et", "ET (CLM)", "#009E73"),
    ("recharge", "net recharge to top 2 m", "#0072B2"),
    ("dS_ns", "ΔS near-surface", "#56B4E9"),
    ("dS_deep", "ΔS deep", "#542788"),
    ("export", "local surface export", "#D55E00"),
    ("drain", "residual NS drainage (vertical+lateral)", "#999999"),
]
BUDGET_CLASSES = {"potomac2": [0, 3, 4], "wolf2": [0, 3, 6]}


def class_budget(domain: str, case: str, mask: np.ndarray) -> dict[str, np.ndarray]:
    """Annual anomalies (member − baseline) in mm/yr, class-mean.

    drain = recharge − ΔS_ns − export: water leaving the top 2 m other than
    as surface export (vertical drainage to the deep zone + lateral flow).
    """
    mem = case_member(domain, case)
    s0, s1 = CASES[case]["stress"]
    years = list(range(40, CASES[case]["rec_end"]))
    p_avg = forcing_219h(domain, "average")["P"].sum(0)
    p_dry = forcing_219h(domain, "dry")["P"].sum(0)
    out = {k: [] for k, *_ in BUDGET_TERMS}
    out["years"] = []
    for y in years:
        vals = {}
        for who in ("m", "b"):
            src = mem if who == "m" else "BASE"
            ds = year_ds(domain, src, y)
            if who == "m":
                ns_prev = end_state(domain, mem, y - 1, "s_ns")
                dp_prev = end_state(domain, mem, y - 1, "s_deep")
                pm = p_dry if year_wetness(case, y) == "dry" else p_avg
            else:
                ns_prev = base_prev_end(domain, y, "s_ns")
                dp_prev = base_prev_end(domain, y, "s_deep")
                pm = p_avg
            vals[who] = {
                "precip": np.nanmean(pm[mask]),
                "et": np.nanmean(ds["qflx_evap_tot"].mean("time").values[mask]) * MM_S_TO_MM_YR,
                "recharge": np.nanmean(ds["pf_et_ns"].mean("time").values[mask]) * H_YR * 1000,
                "export": np.nanmean(ds["gain"].mean("time").values[mask]) * H_YR / AREA_CELL * 1000,
                "dS_ns": np.nanmean((ds["s_ns"].isel(time=-1).values - ns_prev)[mask]) * 1000,
                "dS_deep": np.nanmean((ds["s_deep"].isel(time=-1).values - dp_prev)[mask]) * 1000,
            }
        for k in ("precip", "et", "recharge", "export", "dS_ns", "dS_deep"):
            out[k].append(vals["m"][k] - vals["b"][k])
        out["drain"].append(out["recharge"][-1] - out["dS_ns"][-1] - out["export"][-1])
        out["years"].append(y - s0)
    return {k: np.asarray(v) for k, v in out.items()}


def saturation_profiles(traits) -> dict:
    """Baseline (yr 39) time-mean saturation by layer, per joint class (z: bottom→top)."""
    res = {}
    for d in DOMAINS:
        t = traits[d]
        ds = year_ds(d, "short_baseline", 39)
        with xr.open_dataset(ds.attrs["source_219h"]) as raw:
            sat = np.asarray(raw["saturation"].mean("time").values)
            pres = np.asarray(raw["pressure"].mean("time").values)
        res[d] = {}
        for k in range(9):
            m = (t[JOINT_KEY] == k)
            if m.sum() < 5:
                continue
            res[d][k] = {"n": int(m.sum()), "sat_by_z": np.nanmean(sat[:, m], axis=1).tolist(),
                         "pressure_by_z": np.nanmean(pres[:, m], axis=1).tolist(),
                         "wtd_median": float(np.nanmedian(t["wtd_mean"][m])),
                         "swt_median": float(np.nanmedian(t["swt_mean"][m])),
                         "swt_drought_median": float(np.nanmedian(t["swt_drought_mean"][m])),
                         "perched_frac": float(np.nanmean(t["perched"][m])),
                         "sat_rz_gs_base": float(np.nanmean(t["sat_rz_gs_base"][m])),
                         "sat_rz_gs_drought": float(np.nanmean(t["sat_rz_gs_drought"][m])),
                         "perm_top_median": float(np.nanmedian(t["perm_top"][m])),
                         "log_q_median": float(np.nanmedian(t["log_q"][m])),
                         "phi_mean": float(np.nanmean(t["phi"][m]))}
    return res


def step6_budgets(traits) -> dict:
    res = {}
    for d in DOMAINS:
        t = traits[d]
        act = t["active"] == 1
        res[d] = {}
        for case in ("d10", "pump"):
            res[d][case] = {"domain": class_budget(d, case, act)}
            for k in BUDGET_CLASSES[d]:
                m = act & (t[JOINT_KEY] == k)
                if m.sum() >= 10:
                    res[d][case][k] = class_budget(d, case, m)
    return res


def fig_budgets(bud) -> Path:
    """10-yr drought: last drought year through recovery, per joint class."""
    fig, axes = plt.subplots(4, 2, figsize=(12.5, 12.0), sharex=True, constrained_layout=True)
    for c, d in enumerate(DOMAINS):
        rows = ["domain"] + BUDGET_CLASSES[d]
        for r, k in enumerate(rows):
            ax = axes[r, c]
            b = bud[d]["d10"][k]
            sel = b["years"] >= 9
            yrs = b["years"][sel] + 0.5
            ax.axvspan(9, 10, color=R.PERIOD_DROUGHT_FACE, alpha=R.PERIOD_DROUGHT_ALPHA, lw=0)
            ax.axvspan(10, 15, color=R.PERIOD_RECOVERY_FACE, alpha=R.PERIOD_RECOVERY_ALPHA, lw=0)
            for term, lab, col in BUDGET_TERMS:
                ax.plot(yrs, b[term][sel], color=col, lw=1.8, marker="o", ms=3.5, label=lab)
            ax.axhline(0, color="0.3", lw=0.8)
            ax.grid(True, alpha=0.28)
            rec = b["years"] >= 11
            lo = min(np.min([b[t_][rec].min() for t_, *_ in BUDGET_TERMS]), -5)
            hi = max(np.max([b[t_][rec].max() for t_, *_ in BUDGET_TERMS]), 5)
            ax.set_ylim(lo * 1.6, hi * 1.6)
            name = "whole domain" if k == "domain" else JOINT_LABEL[k]
            ax.set_title(f"{LABEL[d]}: {name}", fontsize=11)
            if c == 0:
                ax.set_ylabel("anomaly (mm/yr)", fontsize=LABEL_FS)
            ax.xaxis.set_major_locator(MultipleLocator(1))
    fig.supxlabel("Years since drought onset (y-axis scaled to recovery years 2–5;\n"
                  "drought-year values run off-scale)", fontsize=LABEL_FS)
    fig.legend(handles=[Line2D([0], [0], color=col, lw=2, label=lab) for _, lab, col in BUDGET_TERMS],
               loc="outside upper center", ncol=4, fontsize=LEGEND_FS - 1, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_class_column_budgets.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------
# Step 7: pumping source partition
# ---------------------------------------------------------------------------

def step7_pumping(traits) -> dict:
    res = {}
    for d in DOMAINS:
        st = statics(d)
        act = st["active"]
        mem = X.MATCHED[d]
        rate = float(mem.split("_")[1])
        rows = []
        for y in range(40, 60):
            v = {}
            for who, src in (("m", mem), ("b", "BASE")):
                ds = year_ds(d, src, y)
                if who == "m":
                    ns_prev = end_state(d, mem, y - 1, "s_ns")
                    dp_prev = end_state(d, mem, y - 1, "s_deep")
                else:
                    ns_prev = base_prev_end(d, y, "s_ns")
                    dp_prev = base_prev_end(d, y, "s_deep")
                dns = ds["s_ns"].isel(time=-1).values - ns_prev
                ddp = ds["s_deep"].isel(time=-1).values - dp_prev
                v[who] = {
                    "dS": float(np.nansum(dns + ddp)) * AREA_CELL,
                    "dS_ns": float(np.nansum(dns)) * AREA_CELL,
                    "et": float(np.nansum(ds["qflx_evap_tot"].mean("time").values)) * MM_S_TO_MM_YR / 1000 * AREA_CELL,
                    "export": float(np.nanmean(np.nansum(ds["gain"].values, axis=(1, 2)))) * H_YR,
                    "deep_src": float(np.nansum(ds["pf_et_deep"].mean("time").values)) * H_YR * AREA_CELL,
                    "rech": float(np.nansum(ds["pf_et_ns"].mean("time").values)) * H_YR * AREA_CELL,
                }
            pumped = rate * st["area_m2"] * H_YR if 40 <= y < 50 else 0.0
            rows.append({
                "year": y - 40,
                "pumped": pumped,
                "pf_deep_src_anom": v["m"]["deep_src"] - v["b"]["deep_src"],
                "from_storage": -(v["m"]["dS"] - v["b"]["dS"]),
                "from_storage_ns": -(v["m"]["dS_ns"] - v["b"]["dS_ns"]),
                "from_export": -(v["m"]["export"] - v["b"]["export"]),
                "from_et": -(v["m"]["et"] - v["b"]["et"]),
                "recharge_anom": v["m"]["rech"] - v["b"]["rech"],
            })
        for r in rows:
            r["residual"] = r["pumped"] - r["from_storage"] - r["from_export"] - r["from_et"]
        stress = [r for r in rows if 0 <= r["year"] < 10]
        tot = sum(r["pumped"] for r in stress)
        res[d] = {
            "rows": rows,
            "stress_fracs": {k: sum(r[k] for r in stress) / tot for k in
                             ("from_storage", "from_storage_ns", "from_export", "from_et", "residual")},
            "late_stress_fracs": {k: sum(r[k] for r in stress[5:]) / sum(r["pumped"] for r in stress[5:]) for k in
                                  ("from_storage", "from_export", "from_et", "residual")},
            "pf_deep_src_check": sum(r["pf_deep_src_anom"] for r in stress) / tot,
        }
    return res


def fig_pumping(pump) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.6), sharey=True, constrained_layout=True)
    terms = [("from_storage", "storage depletion", "#542788"), ("from_export", "reduced streamflow export", "#D55E00"),
             ("from_et", "reduced ET", "#009E73"), ("residual", "residual (lateral subsurface)", "#BBBBBB")]
    for ax, d in zip(axes, DOMAINS):
        rows = pump[d]["rows"]
        yrs = np.array([r["year"] for r in rows]) + 0.5
        scale = rows[1]["pumped"] if rows[1]["pumped"] else 1.0
        bp = np.zeros(len(rows))
        bn = np.zeros(len(rows))
        for k, lab, c in terms:
            v = np.array([r[k] for r in rows]) / scale
            ax.bar(yrs, np.where(v > 0, v, 0), bottom=bp, color=c, width=0.8, label=lab)
            ax.bar(yrs, np.where(v < 0, v, 0), bottom=bn, color=c, width=0.8)
            bp += np.where(v > 0, v, 0)
            bn += np.where(v < 0, v, 0)
        ax.plot(yrs, [r["pumped"] / scale for r in rows], color="k", lw=1.5, drawstyle="steps-mid", label="pumped")
        ax.axhline(0, color="0.3", lw=0.8)
        ax.axvline(10, color="0.4", ls=":", lw=1)
        ax.set_title(LABEL[d], fontsize=TITLE_FS)
        ax.grid(True, axis="y", alpha=0.28)
        ax.xaxis.set_major_locator(MultipleLocator(5))
    axes[0].set_ylabel("Annual source of pumped water\n(fraction of annual pumping)", fontsize=LABEL_FS)
    fig.supxlabel("Years since pumping onset (pumping stops at 10)", fontsize=LABEL_FS)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="outside upper center", ncol=5, fontsize=LEGEND_FS, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_pumping_capture.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------

def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items() if not isinstance(v, np.ndarray) or v.ndim <= 1}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return [_jsonable(v) for v in o.tolist()]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    return o


def main():
    summary = {}
    norm = step0_normalization()
    summary["step0_normalization"] = norm
    fig_normalization(norm)
    traits = step1_traits()
    summary["step1_breakpoints"] = {"pooled": traits[DOMAINS[0]]["_breakpoint"],
                                    **{d: traits[d]["_breakpoint_domain"] for d in DOMAINS}}
    summary["step1_class_fractions"] = {
        d: {
            "wtd": [float(np.mean(traits[d]["wtd_class"][traits[d]["active"] == 1] == k)) for k in range(3)],
            "et": [float(np.mean(traits[d]["et_class"][traits[d]["active"] == 1] == k)) for k in range(3)],
            "frac_wtd_range_crosses_2m": float(np.mean(((traits[d]["wtd_p5"] < 2) & (traits[d]["wtd_p95"] > 2))[traits[d]["active"] == 1])),
        }
        for d in DOMAINS
    }
    fig_traits(traits)
    att = step2_attribution(traits)
    summary["step2_attribution"] = {d: {c: {p: {k: v for k, v in pv.items() if k != "map"} for p, pv in cv.items()}
                                        if isinstance(cv, dict) and c in CASES else cv
                                        for c, cv in att[d].items()} for d in DOMAINS}
    fig_attribution(att, traits)
    ns = step3_ns(traits)
    summary["step3_ns"] = {d: {c: {k: v for k, v in r.items() if not isinstance(v, np.ndarray)}
                               for c, r in ns[d].items()} for d in DOMAINS}
    fig_ns_maps(traits, ns)
    tests = step4_tests(traits, att, ns)
    summary["step4_tests"] = tests
    fig_hypothesis_bins(traits, att, ns)
    summary["step5_decomposition_wtd"] = step5_decomposition(traits, att, ns, "joint_class")
    dec = step5_decomposition(traits, att, ns, JOINT_KEY)
    summary["step5_decomposition"] = dec
    fig_decomposition(dec)
    bud = step6_budgets(traits)
    summary["step6_budgets"] = {d: {c: {str(w): {k: v.tolist() for k, v in b.items()} for w, b in cb.items()}
                                    for c, cb in bud[d].items()} for d in DOMAINS}
    summary["step6_saturation_profiles"] = saturation_profiles(traits)
    fig_budgets(bud)
    pump = step7_pumping(traits)
    summary["step7_pumping"] = pump
    fig_pumping(pump)
    SUMMARY_JSON.write_text(json.dumps(_jsonable(summary), indent=1))
    print("wrote", SUMMARY_JSON)


if __name__ == "__main__":
    main()
