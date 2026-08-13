#!/usr/bin/env python3
"""Local Budyko / energy–water framing of temporary vs persistent deficits.

Baseline-only predictors (late-spinup average forcing) vs recovery deficits
from drought members. Figures under analysis/figures/budyko_*.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import parflow as pf
import xarray as xr
from matplotlib.lines import Line2D

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))


def spearmanr(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Spearman ρ without scipy (env scipy.sparse is broken)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = x.size
    if n < 3:
        return np.nan, np.nan
    rx = np.argsort(np.argsort(x)).astype(np.float64)
    ry = np.argsort(np.argsort(y)).astype(np.float64)
    rx -= rx.mean()
    ry -= ry.mean()
    denom = np.sqrt(np.sum(rx * rx) * np.sum(ry * ry))
    if denom <= 0:
        return np.nan, np.nan
    return float(np.sum(rx * ry) / denom), np.nan

from analysis.paper_figures import utils  # noqa: E402
from analysis.redo_recovery_with_50yr import (  # noqa: E402
    CELL_AREA_M2,
    COLORS,
    DOMAIN_LABELS,
    DOMAINS,
    DROUGHT_LENGTHS,
    FIG_DIR,
    INTERVAL,
    LABEL_FS,
    LEGEND_FS,
    SPINUP_YEARS,
    STREAM_COLOR,
    STREAM_FLOW_PERCENTILE,
    TITLE_FS,
    baseline_name,
    condensed_year_path,
    storage_deficit_pair,
    stream_mask,
)

ENSEMBLE = "droughts"
BASELINE_YEARS = (35, 36, 37, 38, 39)  # late spinup average
FOCUS_LENGTHS = [10, 50]
TEMP_COLOR = "#D4A574"
PERSIST_COLOR = "#5C3317"
HOURS_PER_YEAR = utils.ONE_YEAR

SUMMARY_PATH = FIG_DIR / "budyko_temp_persistent_summary.json"
CSV_PATH = FIG_DIR / "budyko_temp_persistent_spearman.csv"


def active_mask_from_ds(ds) -> np.ndarray:
    mask = ds["mask"]
    if "z" in mask.dims:
        return (mask.any(dim="z") > 0).values
    return (mask > 0).values


def annual_precip_mm(domain_name: str) -> np.ndarray:
    """CW3E APCP (mm/s) → annual precip (mm/yr) for average forcing."""
    fdir = ROOT / "domains" / domain_name / "inputs" / f"{domain_name}_average" / "forcing"
    files = sorted(fdir.glob("CW3E.APCP.*_to_*.pfb"))
    if not files:
        raise FileNotFoundError(f"No APCP forcing in {fdir}")
    acc = None
    for path in files:
        arr = pf.read_pfb(str(path))  # (24, y, x), mm/s
        day_mm = np.sum(arr, axis=0) * 3600.0
        acc = day_mm if acc is None else acc + day_mm
    return acc.astype(np.float64)


def annual_hamon_pet_mm(domain_name: str) -> np.ndarray:
    """Hamon PET (mm/yr) from CW3E Temp (K); daylength from calendar day."""
    fdir = ROOT / "domains" / domain_name / "inputs" / f"{domain_name}_average" / "forcing"
    files = sorted(fdir.glob("CW3E.Temp.*_to_*.pfb"))
    if not files:
        raise FileNotFoundError(f"No Temp forcing in {fdir}")
    # Water year starts Oct 1 in these runs; approximate day-of-year for daylength.
    # File order is sequential hours from start; treat file i as day i of WY.
    lat_fallback_deg = 39.0 if domain_name.startswith("potomac") else 42.5
    acc = None
    for i, path in enumerate(files):
        arr = pf.read_pfb(str(path))  # (24, y, x) K
        t_c = np.mean(arr, axis=0) - 273.15
        # day of year approx: Oct 1 = DOY 274
        doy = ((274 - 1 + i) % 365) + 1
        # approximate daylength (hours) at fixed lat
        decl = 0.4093 * np.sin(2 * np.pi * (doy - 81) / 365.0)
        lat = np.deg2rad(lat_fallback_deg)
        cos_ha = float(np.clip(-np.tan(lat) * np.tan(decl), -1.0, 1.0))
        ha = np.arccos(cos_ha)
        daylen = 24.0 * ha / np.pi
        es = 0.6108 * np.exp(17.27 * t_c / (t_c + 237.3))  # kPa
        pet_day = 29.8 * daylen * es / (t_c + 273.2)  # mm/day
        pet_day = np.where(np.isfinite(pet_day), np.maximum(pet_day, 0.0), 0.0)
        acc = pet_day if acc is None else acc + pet_day
    return acc.astype(np.float64)


def baseline_fields(domain_name: str) -> dict:
    """Late-spinup mean overland, WTD, recharge, K, porosity."""
    flows = []
    wtds = []
    rech = []
    part = []
    active = None
    k_top = None
    for yi in BASELINE_YEARS:
        path = condensed_year_path(domain_name, "short_baseline", yi)
        with xr.open_dataset(path) as ds:
            if active is None:
                active = active_mask_from_ds(ds)
                k_top = np.asarray(ds["perm_x"].isel(z=0).values, dtype=np.float64)
            flow = np.asarray(ds["overland_flow"].mean(dim="time").values, dtype=np.float64)
            # participation: fraction of condensed steps with Q > 1 m³/h
            q = np.asarray(ds["overland_flow"].values, dtype=np.float64)
            part.append(np.mean(q > 1.0, axis=0))
            flows.append(flow)
            wtds.append(np.asarray(ds["wtd"].isel(time=-1).values, dtype=np.float64))
            # annual column EvapTrans depth (m/yr): sum over z of mean rate (1/T) * dz?
            # evaptrans in ParFlow is [1/T]; depth flux ≈ sum_z evaptrans * dz_layer
            # Prefer evaptrans_sum (mean*219) integrated in time then * layers via porosity? 
            # Existing analysis: annual column EvapTrans depth from sum over z of time-integrated flux.
            et = ds["evaptrans"]
            # convert: mean(1/h) * 8760 h * dz — need DZ. Use DZ_Multiplier * base dz if present.
            if "DZ_Multiplier" in ds:
                dz_mult = np.asarray(ds["DZ_Multiplier"].values, dtype=np.float64)
                # CONUS2 nominal dz varies; use multiplier relative thicknesses with sum→column depth proxy:
                # ParFlow EvapTrans source is already volumetric rate / cell volume units of [T^-1]
                # Column water depth rate ≈ sum_z (evaptrans * dz_z). Without absolute dz, use
                # sum over z of mean(evaptrans) * DZ_Multiplier as relative, scaled so domain
                # mean matches sum of evaptrans_sum * unknown. Safer: integrate evaptrans_sum.
                et_sum = np.asarray(ds["evaptrans_sum"].sum(dim="z").sum(dim="time").values)
                # evaptrans_sum = mean * 219 over each window; 40 windows → *1 gives year integral of mean*219
                # Actual hours = 40*219 = 8760. Integral of rate ≈ sum(evaptrans_sum) over time
                # but still [T^-1]*h = dimensionless; times dz for meters.
                # Use dz from multiplier * reference layer thicknesses if available via Domain — fallback:
                # treat sum_z mean(evaptrans)*8760 as 1/T * T = dimensionless saturation-like;
                # multiply by porosity*dz later. Simpler approach used elsewhere: 
                # recharge_m = sum_z(mean(evaptrans)) * HOURS * mean_dz_approx
                et_mean = np.asarray(et.mean(dim="time").values, dtype=np.float64)
                # Approximate layer thickness from CONUS2: upper layers thinner. Use
                # DZ_Multiplier with a unit base so relative column depth ∝ sum(et*dz_mult).
                # Scale so units are m/yr by assuming base dz = 1 m * multiplier is wrong.
                # Better: read porosity and pressure already imply storage in m³; 
                # For flux, ParFlow docs: EvapTrans units are [T^-1] applied as 
                # d(sat)/dt source. Depth equivalent ≈ sum(evaptrans * porosity * dz).
                nz = et_mean.shape[0]
                # CONUS2 default layer thicknesses (m), top→bottom often:
                dz_conus2 = np.array(
                    [0.1, 0.3, 0.6, 1.0, 2.0, 5.0, 10.0, 20.0, 25.0, 50.0][:nz],
                    dtype=np.float64,
                )
                if dz_mult.shape[0] == nz:
                    dz = dz_conus2[:, None, None] * dz_mult
                else:
                    dz = np.broadcast_to(dz_conus2[:, None, None], et_mean.shape)
                # depth flux (m/h) ≈ sum_z evaptrans * dz  (if evaptrans is 1/T on volume)
                depth_m_per_h = np.sum(et_mean * dz, axis=0)
                rech.append(depth_m_per_h * HOURS_PER_YEAR)
            else:
                et_mean = np.asarray(et.mean(dim="time").sum(dim="z").values)
                rech.append(et_mean * HOURS_PER_YEAR)

    flow = np.mean(flows, axis=0)
    wtd = np.mean(wtds, axis=0)
    recharge = np.mean(rech, axis=0)
    participation = np.mean(part, axis=0)
    # overland depth equivalent (m/yr) if all discharge were local (upper bound / routing proxy)
    q_depth = flow * HOURS_PER_YEAR / CELL_AREA_M2

    streams = np.isfinite(flow) & active & (flow >= np.nanpercentile(
        np.where(active, flow, np.nan), STREAM_FLOW_PERCENTILE
    ))
    return {
        "active": active,
        "streams": streams,
        "flow": np.where(active, flow, np.nan),
        "q_depth": np.where(active, q_depth, np.nan),
        "participation": np.where(active, participation, np.nan),
        "wtd": np.where(active, wtd, np.nan),
        "recharge": np.where(active, recharge, np.nan),
        "log10_k_top": np.where(active, np.log10(np.maximum(k_top, 1e-20)), np.nan),
    }


def distance_to_stream_km(streams: np.ndarray, active: np.ndarray) -> np.ndarray:
    """Euclidean distance (km) to nearest stream cell; 1 km grid."""
    from collections import deque

    ny, nx = streams.shape
    dist = np.full((ny, nx), np.inf, dtype=np.float64)
    q: deque[tuple[int, int]] = deque()
    ys, xs = np.where(streams & active)
    for y, x in zip(ys.tolist(), xs.tolist()):
        dist[y, x] = 0.0
        q.append((y, x))
    # multi-source BFS on 8-connected grid (approx Euclidean via cell steps)
    # refine with true Euclidean to stream seeds
    if ys.size == 0:
        return np.where(active, np.nan, np.nan)
    stream_yx = np.column_stack([ys, xs]).astype(np.float64)
    yy, xx = np.indices((ny, nx))
    # chunked min distance for memory
    out = np.full((ny, nx), np.nan, dtype=np.float64)
    active_idx = np.where(active)
    pts = np.column_stack([active_idx[0], active_idx[1]]).astype(np.float64)
    # for each active point, min distance to any stream (vectorized in blocks)
    block = 5000
    mins = np.empty(pts.shape[0], dtype=np.float64)
    for i0 in range(0, pts.shape[0], block):
        chunk = pts[i0 : i0 + block]
        # (n_chunk, n_stream)
        d2 = (chunk[:, None, 0] - stream_yx[None, :, 0]) ** 2 + (
            chunk[:, None, 1] - stream_yx[None, :, 1]
        ) ** 2
        mins[i0 : i0 + block] = np.sqrt(d2.min(axis=1))
    out[active_idx] = mins
    return out


def load_domain_bundle(domain_name: str) -> dict:
    print(f"Building baseline + climate for {domain_name}…", flush=True)
    base = baseline_fields(domain_name)
    p_mm = annual_precip_mm(domain_name)
    pet_mm = annual_hamon_pet_mm(domain_name)
    active = base["active"]
    # align shapes
    assert p_mm.shape == active.shape, (p_mm.shape, active.shape)
    phi = np.where(active & (p_mm > 1.0), pet_mm / p_mm, np.nan)
    # local runoff index proxy: overland depth / P (P in m)
    p_m = p_mm / 1000.0
    r_index = np.where(active & (p_m > 1e-6), base["q_depth"] / p_m, np.nan)
    # evaporative-ish: 1 - recharge/P clipped (not true AET/P)
    e_proxy = np.where(
        active & (p_m > 1e-6),
        np.clip(1.0 - base["recharge"] / p_m, 0.0, 2.0),
        np.nan,
    )
    dist = distance_to_stream_km(base["streams"], active)
    deficits = {}
    for L in DROUGHT_LENGTHS:
        print(f"  storage deficits {domain_name} {L}-yr…", flush=True)
        pair = storage_deficit_pair(domain_name, L)
        temp = np.asarray(pair["temporary"].values, dtype=np.float64)
        pers = np.asarray(pair["persistent"].values, dtype=np.float64)
        tot = temp + pers
        f_temp = np.full_like(tot, np.nan)
        ok = np.isfinite(tot) & (tot > 1e-6)
        f_temp[ok] = temp[ok] / tot[ok]
        deficits[L] = {
            "temporary": np.where(active, temp, np.nan),
            "persistent": np.where(active, pers, np.nan),
            "f_temp": np.where(active, f_temp, np.nan),
            "total": np.where(active, tot, np.nan),
        }
    return {
        **base,
        "P_mm": np.where(active, p_mm, np.nan),
        "PET_mm": np.where(active, pet_mm, np.nan),
        "phi": phi,
        "R_index": r_index,
        "E_proxy": e_proxy,
        "dist_km": dist,
        "deficits": deficits,
    }


def stratum_masks(bundle: dict) -> dict[str, np.ndarray]:
    """Hydrologic-position bins for stratified tests."""
    active = bundle["active"]
    streams = bundle["streams"]
    dist = bundle["dist_km"]
    wtd = bundle["wtd"]
    flow = bundle["flow"]

    # non-stream active
    nons = active & ~streams
    # near: within 2 km of stream
    near = nons & np.isfinite(dist) & (dist <= 2.0)
    # upland: far and deep WTD (top tercile WTD among nons)
    wtd_n = wtd[nons & np.isfinite(wtd)]
    if wtd_n.size:
        wtd_hi = np.nanpercentile(wtd_n, 66)
    else:
        wtd_hi = np.inf
    upland = nons & np.isfinite(dist) & (dist > 5.0) & np.isfinite(wtd) & (wtd >= wtd_hi)
    # mid: remaining nons
    mid = nons & ~near & ~upland
    return {
        "Stream": streams,
        "Near-stream": near,
        "Mid-landscape": mid,
        "Upland (deep WTD)": upland,
    }


def spearman_screen(bundles: dict) -> list[dict]:
    rows = []
    predictors = [
        ("phi", "Aridity φ (PET/P)"),
        ("P_mm", "Annual P"),
        ("PET_mm", "Hamon PET"),
        ("participation", "Overland participation"),
        ("flow", "Mean overland flow"),
        ("R_index", "Overland depth / P"),
        ("wtd", "Baseline WTD"),
        ("recharge", "Local recharge"),
        ("E_proxy", "1 − recharge/P"),
        ("dist_km", "Dist. to stream"),
        ("log10_k_top", "log₁₀ K (top)"),
    ]
    for domain_name, b in bundles.items():
        active = b["active"]
        streams = b["streams"]
        mask = active & ~streams
        for L in FOCUS_LENGTHS:
            for kind, key in [
                ("f_temp", "f_temp"),
                ("temporary", "temporary"),
                ("persistent", "persistent"),
            ]:
                y = b["deficits"][L][key]
                for pk, plab in predictors:
                    x = b[pk]
                    m = mask & np.isfinite(x) & np.isfinite(y)
                    if kind != "f_temp":
                        # for magnitudes, require some deficit present
                        m = m & (b["deficits"][L]["total"] > 1e-6)
                    n = int(m.sum())
                    if n < 30:
                        rho, p = np.nan, np.nan
                    else:
                        rho, p = spearmanr(x[m], y[m])
                    rows.append(
                        {
                            "domain": domain_name,
                            "L": L,
                            "response": kind,
                            "predictor": pk,
                            "predictor_label": plab,
                            "rho": float(rho) if np.isfinite(rho) else np.nan,
                            "p": float(p) if np.isfinite(p) else np.nan,
                            "n": n,
                        }
                    )
    return rows


def fig_maps_state_and_ftemp(bundles: dict):
    """Maps: φ, overland participation, f_temp (10-yr) — slide 16:9 layout."""
    from analysis.redo_recovery_with_50yr import _prepare_map

    metrics = [
        ("phi", "Aridity φ (PET/P)", "viridis", (0.5, 1.5)),
        ("participation", "Overland participation", "Blues", None),
        (("deficits", 10, "f_temp"), "Temporary fraction (10-yr)", "YlOrBr", (0.0, 1.0)),
    ]
    fig = plt.figure(figsize=(13.2, 7.2), constrained_layout=False)
    outer = fig.add_gridspec(
        len(DOMAINS), 1, left=0.08, right=0.98, top=0.95, bottom=0.06, hspace=0.28
    )
    for d_i, domain_name in enumerate(DOMAINS):
        b = bundles[domain_name]
        streams, active = b["streams"], b["active"]
        band = outer[d_i].subgridspec(
            2, len(metrics), height_ratios=[0.28, 1.0], hspace=0.12, wspace=0.18
        )
        ax_head = fig.add_subplot(band[0, :])
        ax_head.axis("off")
        ax_head.set_title(
            DOMAIN_LABELS[domain_name], fontsize=15, fontweight="semibold", pad=2
        )
        for k_i, (key, title, cmap, vlim) in enumerate(metrics):
            ax = fig.add_subplot(band[1, k_i])
            if isinstance(key, tuple):
                z = b[key[0]][key[1]][key[2]]
            else:
                z = b[key]
            zc, sc = _prepare_map(z, streams, active, align_landscape=True)
            if vlim is None:
                vmin, vmax = 0.0, float(np.nanpercentile(z[active], 98))
            else:
                vmin, vmax = vlim
            im = ax.imshow(
                zc, origin="lower", cmap=cmap, vmin=vmin, vmax=vmax, aspect="equal"
            )
            ax.contour(
                sc.astype(float),
                levels=[0.5],
                colors=[STREAM_COLOR],
                linewidths=0.7,
            )
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.set_title(title, fontsize=11, pad=4)
            cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
            cbar.ax.tick_params(labelsize=9)
    out = FIG_DIR / "budyko_maps_phi_overland_ftemp.png"
    fig.savefig(out, dpi=160, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print("wrote", out)


def fig_hexbins(bundles: dict):
    """f_temp hexbins vs φ, participation, WTD for 10- and 50-yr."""
    xvars = [
        ("phi", "Aridity φ (PET/P)", (0.6, 1.4)),
        ("participation", "Overland participation (-)", None),
        ("wtd", "Baseline WTD (m)", None),
        ("dist_km", "Distance to stream (km)", None),
    ]
    fig, axes = plt.subplots(
        len(FOCUS_LENGTHS),
        len(xvars),
        figsize=(14, 6.8),
        constrained_layout=True,
    )
    for r, L in enumerate(FOCUS_LENGTHS):
        for c, (xk, xlab, xlim) in enumerate(xvars):
            ax = axes[r, c]
            xs, ys, ds = [], [], []
            for domain_name in DOMAINS:
                b = bundles[domain_name]
                m = b["active"] & ~b["streams"]
                x = b[xk][m]
                y = b["deficits"][L]["f_temp"][m]
                ok = np.isfinite(x) & np.isfinite(y)
                xs.append(x[ok])
                ys.append(y[ok])
                ds.append(np.full(ok.sum(), domain_name))
            x = np.concatenate(xs)
            y = np.concatenate(ys)
            if x.size < 20:
                ax.set_visible(False)
                continue
            # log for participation if skewed
            if xk == "participation":
                xplot = np.clip(x, 1e-4, None)
                hb = ax.hexbin(
                    xplot, y, gridsize=35, cmap="YlOrBr", mincnt=3, xscale="log",
                    extent=None,
                )
            else:
                hb = ax.hexbin(x, y, gridsize=35, cmap="YlOrBr", mincnt=3)
            # Spearman on pooled non-stream
            rho, _ = spearmanr(x, y)
            ax.text(
                0.04,
                0.96,
                f"ρ={rho:+.2f}",
                transform=ax.transAxes,
                va="top",
                fontsize=10,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8),
            )
            if r == 0:
                ax.set_title(xlab, fontsize=11)
            if c == 0:
                ax.set_ylabel(f"{L}-yr temporary fraction", fontsize=LABEL_FS)
            if xlim is not None and xk != "participation":
                ax.set_xlim(*xlim)
            ax.set_ylim(0, 1)
            if c == len(xvars) - 1:
                fig.colorbar(hb, ax=ax, fraction=0.046, pad=0.02)
    out = FIG_DIR / "budyko_hexbin_ftemp_vs_predictors.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_stratified_bars(bundles: dict):
    """Domain-total temporary vs persistent by landscape stratum and drought length."""
    strata_order = ["Stream", "Near-stream", "Mid-landscape", "Upland (deep WTD)"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), sharey=False, constrained_layout=True)
    for col, domain_name in enumerate(DOMAINS):
        b = bundles[domain_name]
        strata = stratum_masks(b)
        for row, kind in enumerate(("temporary", "persistent")):
            ax = axes[row, col]
            x = np.arange(len(DROUGHT_LENGTHS))
            width = 0.18
            for i, sname in enumerate(strata_order):
                mask = strata[sname]
                vals = []
                for L in DROUGHT_LENGTHS:
                    z = b["deficits"][L][kind]
                    # m water equiv * cell area → m³, then 10⁶ m³
                    vals.append(float(np.nansum(np.where(mask, z, 0.0))) * CELL_AREA_M2 / 1e6)
                ax.bar(
                    x + (i - 1.5) * width,
                    vals,
                    width=width,
                    label=sname,
                    color=plt.cm.YlOrBr(0.25 + 0.2 * i),
                    edgecolor="0.3",
                    linewidth=0.4,
                )
            ax.set_xticks(x)
            ax.set_xticklabels([str(L) for L in DROUGHT_LENGTHS])
            ax.grid(True, axis="y", alpha=0.3)
            if row == 0:
                ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
            if col == 0:
                lab = "Temporary" if kind == "temporary" else "Persistent"
                ax.set_ylabel(f"{lab} deficit (10⁶ m³)", fontsize=LABEL_FS)
            if row == 1:
                ax.set_xlabel("Drought length (yr)", fontsize=LABEL_FS)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="outside upper center",
        ncol=4,
        fontsize=LEGEND_FS,
        frameon=False,
    )
    out = FIG_DIR / "budyko_stratified_temp_persist_bars.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_ftemp_by_stratum(bundles: dict):
    """Mean temporary fraction by stratum vs drought length."""
    strata_order = ["Stream", "Near-stream", "Mid-landscape", "Upland (deep WTD)"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True, constrained_layout=True)
    for col, domain_name in enumerate(DOMAINS):
        ax = axes[col]
        b = bundles[domain_name]
        strata = stratum_masks(b)
        for i, sname in enumerate(strata_order):
            mask = strata[sname]
            ys = []
            for L in DROUGHT_LENGTHS:
                ft = b["deficits"][L]["f_temp"]
                vals = ft[mask & np.isfinite(ft)]
                ys.append(float(np.nanmean(vals)) if vals.size else np.nan)
            ax.plot(
                DROUGHT_LENGTHS,
                ys,
                marker="o",
                lw=1.6,
                color=plt.cm.YlOrBr(0.3 + 0.18 * i),
                label=sname,
            )
        ax.set_xscale("log")
        ax.set_xticks(DROUGHT_LENGTHS)
        ax.set_xticklabels([str(L) for L in DROUGHT_LENGTHS])
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        if col == 0:
            ax.set_ylabel("Mean temporary fraction", fontsize=LABEL_FS)
        ax.set_xlabel("Drought length (yr)", fontsize=LABEL_FS)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="outside upper center",
        ncol=4,
        fontsize=LEGEND_FS,
        frameon=False,
    )
    out = FIG_DIR / "budyko_ftemp_by_stratum.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_budyko_space(bundles: dict):
    """Cells in (φ, R_index) space colored by f_temp — local Budyko diagram."""
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6), constrained_layout=True)
    for col, L in enumerate(FOCUS_LENGTHS):
        ax = axes[col]
        for domain_name, marker in zip(DOMAINS, ("o", "s")):
            b = bundles[domain_name]
            m = b["active"] & ~b["streams"]
            x = b["phi"][m]
            y = np.clip(b["R_index"][m], 1e-6, None)
            z = b["deficits"][L]["f_temp"][m]
            ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
            # subsample for clarity
            idx = np.where(ok)[0]
            if idx.size > 4000:
                rng = np.random.default_rng(0)
                idx = rng.choice(idx, size=4000, replace=False)
            sc = ax.scatter(
                x[idx],
                y[idx],
                c=z[idx],
                s=8,
                marker=marker,
                cmap="YlOrBr",
                vmin=0,
                vmax=1,
                alpha=0.55,
                linewidths=0,
                label=DOMAIN_LABELS[domain_name],
            )
        ax.set_yscale("log")
        ax.set_xlabel("Aridity φ (PET/P)", fontsize=LABEL_FS)
        if col == 0:
            ax.set_ylabel("Overland depth / P (-)", fontsize=LABEL_FS)
        ax.set_title(f"{L}-year drought", fontsize=TITLE_FS)
        ax.grid(True, alpha=0.3, which="both")
        cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.02)
        cbar.set_label("Temporary fraction", fontsize=10)
    handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="0.4", markersize=8, label="Potomac"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="0.4", markersize=8, label="Wolf"),
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=2, frameon=False, fontsize=LEGEND_FS)
    out = FIG_DIR / "budyko_space_ftemp.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_spearman_heatmap(rows: list[dict]):
    predictors = []
    seen = set()
    for r in rows:
        if r["predictor"] not in seen:
            seen.add(r["predictor"])
            predictors.append((r["predictor"], r["predictor_label"]))
    # columns: domain × L × response(f_temp)
    col_defs = [
        (d, L, "f_temp")
        for d in DOMAINS
        for L in FOCUS_LENGTHS
    ]
    mat = np.full((len(predictors), len(col_defs)), np.nan)
    lookup = {(r["domain"], r["L"], r["response"], r["predictor"]): r["rho"] for r in rows}
    for j, (d, L, resp) in enumerate(col_defs):
        for i, (pk, _) in enumerate(predictors):
            mat[i, j] = lookup.get((d, L, resp, pk), np.nan)

    fig, ax = plt.subplots(figsize=(10, 6.2), constrained_layout=True)
    from matplotlib.colors import TwoSlopeNorm

    norm = TwoSlopeNorm(vmin=-0.8, vcenter=0.0, vmax=0.8)
    im = ax.imshow(mat, aspect="auto", cmap="RdBu_r", norm=norm)
    ax.set_yticks(range(len(predictors)))
    ax.set_yticklabels([lab for _, lab in predictors], fontsize=11)
    ax.set_xticks(range(len(col_defs)))
    ax.set_xticklabels(
        [f"{DOMAIN_LABELS[d]}\n{L}-yr" for d, L, _ in col_defs],
        fontsize=10,
    )
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            if np.isfinite(v):
                ax.text(
                    j,
                    i,
                    f"{v:+.2f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if abs(v) > 0.45 else "black",
                )
    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("Spearman ρ vs temporary fraction", fontsize=11)
    out = FIG_DIR / "budyko_spearman_ftemp.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_phi_uniformity(bundles: dict):
    """Show φ is nearly uniform while overland / f_temp vary — climate vs connectivity."""
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 7.0), constrained_layout=True)
    for col, domain_name in enumerate(DOMAINS):
        b = bundles[domain_name]
        m = b["active"]
        ax = axes[0, col]
        ax.hist(b["phi"][m & np.isfinite(b["phi"])], bins=40, color="#4C78A8", alpha=0.85)
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        if col == 0:
            ax.set_ylabel("Cells", fontsize=LABEL_FS)
        ax.set_xlabel("Aridity φ (PET/P)", fontsize=LABEL_FS)
        ax.grid(True, alpha=0.3)

        ax2 = axes[1, col]
        part = b["participation"][m & np.isfinite(b["participation"])]
        ax2.hist(part, bins=40, color="#F58518", alpha=0.85)
        if col == 0:
            ax2.set_ylabel("Cells", fontsize=LABEL_FS)
        ax2.set_xlabel("Overland participation (-)", fontsize=LABEL_FS)
        ax2.set_yscale("log")
        ax2.grid(True, alpha=0.3)
    out = FIG_DIR / "budyko_phi_vs_overland_hist.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def summarize(bundles: dict, rows: list[dict]) -> dict:
    summary = {"domains": {}, "notes": []}
    for domain_name, b in bundles.items():
        active = b["active"]
        phi = b["phi"][active & np.isfinite(b["phi"])]
        part = b["participation"][active & np.isfinite(b["participation"])]
        dsum = {
            "phi_mean": float(np.nanmean(phi)),
            "phi_p05": float(np.nanpercentile(phi, 5)),
            "phi_p95": float(np.nanpercentile(phi, 95)),
            "P_mm_mean": float(np.nanmean(b["P_mm"][active])),
            "PET_mm_mean": float(np.nanmean(b["PET_mm"][active])),
            "participation_mean": float(np.nanmean(part)),
            "stratum_ftemp": {},
            "stratum_persist_growth_50_over_10": {},
        }
        strata = stratum_masks(b)
        for sname, mask in strata.items():
            dsum["stratum_ftemp"][sname] = {}
            for L in FOCUS_LENGTHS:
                ft = b["deficits"][L]["f_temp"]
                vals = ft[mask & np.isfinite(ft)]
                dsum["stratum_ftemp"][sname][str(L)] = (
                    float(np.nanmean(vals)) if vals.size else None
                )
            p10 = b["deficits"][10]["persistent"]
            p50 = b["deficits"][50]["persistent"]
            s10 = float(np.nansum(np.where(mask, p10, 0.0)))
            s50 = float(np.nansum(np.where(mask, p50, 0.0)))
            dsum["stratum_persist_growth_50_over_10"][sname] = (
                (s50 / s10) if s10 > 0 else None
            )
        summary["domains"][domain_name] = dsum

    # top predictors for f_temp
    top = []
    for domain_name in DOMAINS:
        for L in FOCUS_LENGTHS:
            subset = [
                r
                for r in rows
                if r["domain"] == domain_name and r["L"] == L and r["response"] == "f_temp"
            ]
            subset = [r for r in subset if np.isfinite(r["rho"])]
            subset.sort(key=lambda r: abs(r["rho"]), reverse=True)
            top.append(
                {
                    "domain": domain_name,
                    "L": L,
                    "top": [
                        {"predictor": r["predictor"], "rho": r["rho"]}
                        for r in subset[:5]
                    ],
                }
            )
    summary["top_ftemp_predictors"] = top
    return summary


def main():
    bundles = {d: load_domain_bundle(d) for d in DOMAINS}
    rows = spearman_screen(bundles)
    with CSV_PATH.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("wrote", CSV_PATH)

    fig_phi_uniformity(bundles)
    fig_maps_state_and_ftemp(bundles)
    fig_hexbins(bundles)
    fig_budyko_space(bundles)
    fig_stratified_bars(bundles)
    fig_ftemp_by_stratum(bundles)
    fig_spearman_heatmap(rows)

    summary = summarize(bundles, rows)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2))
    print("wrote", SUMMARY_PATH)

    # console takeaways
    print("\n========== SUMMARY ==========")
    for d in DOMAINS:
        s = summary["domains"][d]
        print(
            f"{DOMAIN_LABELS[d]}: φ={s['phi_mean']:.2f} "
            f"[{s['phi_p05']:.2f}, {s['phi_p95']:.2f}], "
            f"P={s['P_mm_mean']:.0f} mm, PET={s['PET_mm_mean']:.0f} mm"
        )
        for sn, ft in s["stratum_ftemp"].items():
            print(
                f"  {sn:22s} f_temp 10/50={ft.get('10')}/{ft.get('50')}  "
                f"persist×(50/10)={s['stratum_persist_growth_50_over_10'][sn]}"
            )


if __name__ == "__main__":
    main()
