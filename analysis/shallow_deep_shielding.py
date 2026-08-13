#!/usr/bin/env python3
"""Near-surface vs deep storage: temporary/persistent partition + mid-drought regen.

Near-surface = CONUS2 layers z≥6 (top 2 m; GWMM “unconfined”).
Deep         = layers z<6 (below 2 m).

Theory: cells whose drought losses live in near-surface storage regenerate on
precip pulses even mid-drought, so those losses stay temporary and shield the
column from persistent (deep) drawdown.
"""
from __future__ import annotations

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
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

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
    COLORS,
    DOMAIN_LABELS,
    DOMAINS,
    DROUGHT_LENGTHS,
    FIG_DIR,
    INTERVAL,
    LABEL_FS,
    LEGEND_FS,
    RECOVERY_YEARS,
    SPINUP_YEARS,
    STEPS_PER_YEAR,
    STREAM_COLOR,
    TITLE_FS,
    _prepare_map,
    baseline_name,
    condensed_year_path,
    potomac_snapshot_path,
    storage_deficit_pair,
    stream_mask,
)

ENSEMBLE = "droughts"
CELL_AREA_M2 = 1_000_000.0
SHALLOW_Z0 = 6  # layers [SHALLOW_Z0:] = top 2 m
SHALLOW_COLOR = "#6BAED6"
DEEP_COLOR = "#542788"
DS_SCALE = 1e6
FOCUS_L = 10  # heatmaps / pulse composites

DZ_M = np.array(
    [1.0, 0.5, 0.25, 0.125, 0.05, 0.025, 0.005, 0.003, 0.0015, 0.0005]
) * 200.0


def _active_from_ds(ds: xr.Dataset) -> xr.DataArray:
    mask = ds["mask"]
    if "z" in mask.dims:
        return mask.any(dim="z") > 0
    return mask > 0


def read_layer_storage_snapshot(domain_name, member, year_index, *, which="last"):
    """Return subsurface_storage (z,y,x) in m³ at one snapshot."""
    if (
        domain_name == "potomac2"
        and member in ("baseline", "short_baseline")
        and year_index >= 55
    ):
        snap = potomac_snapshot_path(year_index)
        if snap is not None:
            with xr.open_dataset(snap) as ds:
                stor = ds["subsurface_storage"]
                if "time" in stor.dims:
                    stor = stor.isel(time=-1 if which == "last" else 0)
                active = _active_from_ds(ds)
                return stor.where(active).load()
        year_index = min(year_index, 54)
        member = "short_baseline"

    path = condensed_year_path(domain_name, member, year_index)
    with xr.open_dataset(path) as ds:
        t_idx = 0 if which == "first" else -1
        stor = ds["subsurface_storage"].isel(time=t_idx)
        active = _active_from_ds(ds)
        return stor.where(active).load()


def zone_deficit_pair(domain_name: str, drought_length: int) -> dict:
    """Temporary/persistent deficits split into near-surface vs deep (m water)."""
    member = f"{drought_length}_year_drought"
    bmem = baseline_name(domain_name)
    start_year = SPINUP_YEARS + drought_length - 1
    yr1_year = SPINUP_YEARS + drought_length

    d0 = read_layer_storage_snapshot(domain_name, member, start_year)
    b0 = read_layer_storage_snapshot(domain_name, bmem, start_year)
    d1 = read_layer_storage_snapshot(domain_name, member, yr1_year)
    b1 = read_layer_storage_snapshot(domain_name, bmem, yr1_year)

    def0 = (b0 - d0) / CELL_AREA_M2  # m
    def1 = (b1 - d1) / CELL_AREA_M2
    recovered = def0 - def1

    shallow0 = def0.isel(z=slice(SHALLOW_Z0, None)).sum(dim="z")
    deep0 = def0.isel(z=slice(0, SHALLOW_Z0)).sum(dim="z")
    shallow1 = def1.isel(z=slice(SHALLOW_Z0, None)).sum(dim="z")
    deep1 = def1.isel(z=slice(0, SHALLOW_Z0)).sum(dim="z")

    temp_sh = xr.apply_ufunc(np.maximum, recovered.isel(z=slice(SHALLOW_Z0, None)).sum("z"), 0.0)
    temp_de = xr.apply_ufunc(np.maximum, recovered.isel(z=slice(0, SHALLOW_Z0)).sum("z"), 0.0)
    pers_sh = xr.apply_ufunc(np.maximum, shallow1, 0.0)
    pers_de = xr.apply_ufunc(np.maximum, deep1, 0.0)

    col0 = shallow0 + deep0
    f_shallow = shallow0 / xr.apply_ufunc(np.maximum, col0, 1e-12)

    return {
        "shallow_end": shallow0,
        "deep_end": deep0,
        "f_shallow_end": f_shallow,
        "temp_shallow": temp_sh,
        "temp_deep": temp_de,
        "pers_shallow": pers_sh,
        "pers_deep": pers_de,
        "layer_end": def0,  # z,y,x
        "layer_rec": recovered,
    }


def domain_zone_totals_m3(pair: dict) -> dict[str, float]:
    out = {}
    for key in (
        "temp_shallow",
        "temp_deep",
        "pers_shallow",
        "pers_deep",
        "shallow_end",
        "deep_end",
    ):
        v = pair[key].values
        out[key] = float(np.nansum(v[np.isfinite(v)])) * CELL_AREA_M2
    return out


def available_lengths(domain_name: str) -> list[int]:
    """Drought lengths with end-of-drought + yr1 baseline snapshots."""
    out = []
    for L in DROUGHT_LENGTHS:
        y1 = SPINUP_YEARS + L
        bmem = baseline_name(domain_name)
        if domain_name == "potomac2" and y1 >= 55:
            if potomac_snapshot_path(y1) is None or potomac_snapshot_path(y1 - 1) is None:
                continue
        else:
            try:
                condensed_year_path(domain_name, bmem, y1)
            except Exception:
                continue
        try:
            condensed_year_path(domain_name, f"{L}_year_drought", y1)
        except Exception:
            continue
        out.append(L)
    return out


# ---------------------------------------------------------------------------
# Mid-drought series + precip
# ---------------------------------------------------------------------------

_P219_CACHE: dict[str, np.ndarray] = {}


def dry_year_precip_219h(domain_name: str) -> np.ndarray:
    """Domain-mean precip (mm) in each 219 h window of the dry WY."""
    if domain_name in _P219_CACHE:
        return _P219_CACHE[domain_name]
    fdir = ROOT / "domains" / domain_name / "inputs" / f"{domain_name}_dry" / "forcing"
    files = sorted(fdir.glob("CW3E.APCP.*_to_*.pfb"))
    if not files:
        raise FileNotFoundError(fdir)
    hours = []
    for path in files:
        arr = pf.read_pfb(str(path))  # (24, y, x) mm/s
        hours.append((arr * 3600.0).mean(axis=(1, 2)))
    p = np.concatenate(hours)
    n = (utils.ONE_YEAR // INTERVAL) * INTERVAL
    p = p[:n].reshape(-1, INTERVAL).sum(axis=1)
    _P219_CACHE[domain_name] = p.astype(np.float64)
    return _P219_CACHE[domain_name]


def zone_anomaly_year(domain_name: str, member: str, year_index: int, bmem: str):
    """Return (t_frac_in_year, shallow_anom_m3, deep_anom_m3) for one year."""
    dpath = condensed_year_path(domain_name, member, year_index)
    bpath = condensed_year_path(domain_name, bmem, year_index)
    with xr.open_dataset(dpath) as dds, xr.open_dataset(bpath) as bds:
        a = dds["subsurface_storage"] - bds["subsurface_storage"]
        sh = a.isel(z=slice(SHALLOW_Z0, None)).sum(dim=("z", "y", "x")).values
        de = a.isel(z=slice(0, SHALLOW_Z0)).sum(dim=("z", "y", "x")).values
    t = np.arange(sh.shape[0], dtype=np.float64) / STEPS_PER_YEAR
    return t, sh.astype(np.float64), de.astype(np.float64)


def drought_zone_series(domain_name: str, drought_length: int, *, include_recovery: bool = False):
    """Shallow/deep anomalies from drought start; optionally through recovery."""
    member = f"{drought_length}_year_drought"
    t_all, sh_all, de_all, p_all = [], [], [], []
    p_year = dry_year_precip_219h(domain_name)
    n_years = drought_length + (RECOVERY_YEARS if include_recovery else 0)
    for k in range(n_years):
        year = SPINUP_YEARS + k
        # Full baseline for wolf years ≥55; potomac long baseline not condensed.
        if year >= 55:
            if domain_name == "potomac2":
                break
            bmem = baseline_name(domain_name)
        else:
            bmem = "short_baseline"
        t, sh, de = zone_anomaly_year(domain_name, member, year, bmem)
        t_all.append(k + t)
        sh_all.append(sh)
        de_all.append(de)
        p_all.append(p_year[: sh.shape[0]])
    return {
        "t": np.concatenate(t_all),
        "shallow": np.concatenate(sh_all),
        "deep": np.concatenate(de_all),
        "precip": np.concatenate(p_all),
        "drought_length": drought_length,
    }


def pulse_stats(series: dict) -> dict:
    """Wet vs dry 219 h window ΔS for near-surface vs deep."""
    sh = series["shallow"]
    de = series["deep"]
    p = series["precip"]
    n = min(len(sh), len(p), len(de))
    sh, de, p = sh[:n], de[:n], p[:n]
    dsh = np.diff(sh)
    dde = np.diff(de)
    pw = p[1:]
    wet = pw >= np.nanpercentile(pw, 75)
    dry = pw <= np.nanpercentile(pw, 25)
    return {
        "corr_p_shallow": float(np.corrcoef(pw, dsh)[0, 1]),
        "corr_p_deep": float(np.corrcoef(pw, dde)[0, 1]),
        "wet_d_shallow": float(np.nanmean(dsh[wet])),
        "wet_d_deep": float(np.nanmean(dde[wet])),
        "dry_d_shallow": float(np.nanmean(dsh[dry])),
        "dry_d_deep": float(np.nanmean(dde[dry])),
        "n_wet": int(wet.sum()),
        "n_dry": int(dry.sum()),
    }


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def fig_aggregate_partition(zone_pairs: dict):
    """Stacked bars: temporary & persistent each split near-surface vs deep."""
    lengths = DROUGHT_LENGTHS
    fig, axes = plt.subplots(
        1,
        len(DOMAINS),
        figsize=(4.2 * len(DOMAINS), 4.2),
        sharey=False,
        constrained_layout=True,
    )
    if len(DOMAINS) == 1:
        axes = [axes]

    x = np.arange(len(lengths), dtype=float)
    width = 0.36
    legend_handles = [
        Patch(facecolor=SHALLOW_COLOR, edgecolor="0.2", label="Near-surface (top 2 m)"),
        Patch(facecolor=DEEP_COLOR, edgecolor="0.2", label="Deep (>2 m)"),
    ]

    for ax, domain_name in zip(axes, DOMAINS):
        temp_sh, temp_de, pers_sh, pers_de = [], [], [], []
        for L in lengths:
            if L not in zone_pairs[domain_name]:
                temp_sh.append(0.0)
                temp_de.append(0.0)
                pers_sh.append(0.0)
                pers_de.append(0.0)
                continue
            tot = domain_zone_totals_m3(zone_pairs[domain_name][L])
            temp_sh.append(tot["temp_shallow"] / DS_SCALE)
            temp_de.append(tot["temp_deep"] / DS_SCALE)
            pers_sh.append(tot["pers_shallow"] / DS_SCALE)
            pers_de.append(tot["pers_deep"] / DS_SCALE)

        ax.bar(
            x - width / 2,
            temp_sh,
            width,
            color=SHALLOW_COLOR,
            edgecolor="0.2",
            linewidth=0.6,
        )
        ax.bar(
            x - width / 2,
            temp_de,
            width,
            bottom=temp_sh,
            color=DEEP_COLOR,
            edgecolor="0.2",
            linewidth=0.6,
        )
        ax.bar(
            x + width / 2,
            pers_sh,
            width,
            color=SHALLOW_COLOR,
            edgecolor="0.2",
            linewidth=0.6,
            alpha=0.95,
        )
        ax.bar(
            x + width / 2,
            pers_de,
            width,
            bottom=pers_sh,
            color=DEEP_COLOR,
            edgecolor="0.2",
            linewidth=0.6,
            alpha=0.95,
        )

        ax.set_xticks(x)
        ax.set_xticklabels([str(L) for L in lengths])
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.axhline(0.0, color="0.5", lw=0.6)

        # annotate bar groups
        ymax = ax.get_ylim()[1]
        for i in range(len(lengths)):
            ax.text(
                x[i] - width / 2,
                temp_sh[i] + temp_de[i] + 0.02 * ymax,
                "T",
                ha="center",
                va="bottom",
                fontsize=9,
                color="0.3",
            )
            ax.text(
                x[i] + width / 2,
                pers_sh[i] + pers_de[i] + 0.02 * ymax,
                "P",
                ha="center",
                va="bottom",
                fontsize=9,
                color="0.3",
            )

    axes[0].set_ylabel(r"Storage deficit ($10^6$ m$^3$)", fontsize=LABEL_FS)
    fig.supxlabel("Drought length (years)", fontsize=LABEL_FS)
    fig.legend(
        handles=legend_handles
        + [
            Line2D([0], [0], color="none", label="T = temporary (recovered in yr 1)"),
            Line2D([0], [0], color="none", label="P = persistent (remaining after yr 1)"),
        ],
        loc="outside upper center",
        ncol=2,
        frameon=False,
        fontsize=LEGEND_FS,
    )
    out = FIG_DIR / "shallow_deep_temp_persist_partition.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_spatial_10yr(zone_pairs: dict, landscape: dict, col_pairs: dict):
    """10-yr maps: near-surface / deep end-drought deficit + f_shallow vs f_temp."""
    col_keys = ("shallow_end", "deep_end", "f_shallow_end", "f_temp")
    col_titles = {
        "shallow_end": "Near-surface deficit (m)",
        "deep_end": "Deep deficit (m)",
        "f_shallow_end": "Fraction near-surface",
        "f_temp": "Temporary fraction",
    }
    CMAP = "YlOrBr"

    prep = {}
    for domain_name in DOMAINS:
        streams, active = landscape[domain_name]
        zp = zone_pairs[domain_name][FOCUS_L]
        cp = col_pairs[domain_name][FOCUS_L]
        f_temp = cp["temporary"] / xr.apply_ufunc(
            np.maximum, cp["temporary"] + cp["persistent"], 1e-12
        )
        fields = {
            "shallow_end": zp["shallow_end"].values,
            "deep_end": zp["deep_end"].values,
            "f_shallow_end": zp["f_shallow_end"].values,
            "f_temp": f_temp.values,
        }
        prepared = {}
        depth_stack = []
        for key, arr in fields.items():
            z, st = _prepare_map(arr, streams, active, align_landscape=True)
            prepared[key] = (z, st)
            if key in ("shallow_end", "deep_end"):
                depth_stack.append(z[np.isfinite(z)])
        z0, _ = prepared["shallow_end"]
        vmax_d = float(np.nanpercentile(np.abs(np.concatenate(depth_stack)), 98))
        prep[domain_name] = {
            "maps": prepared,
            "vmax_d": max(vmax_d, 1e-3),
        }

    fig = plt.figure(figsize=(13.2, 7.2), constrained_layout=False)
    outer = fig.add_gridspec(
        len(DOMAINS), 1, left=0.10, right=0.88, top=0.95, bottom=0.08, hspace=0.30
    )
    im_f = None
    last_im_d = {}

    for d_i, domain_name in enumerate(DOMAINS):
        band = outer[d_i].subgridspec(
            2, len(col_keys), height_ratios=[0.3, 1.0], hspace=0.15, wspace=0.12
        )
        ax_head = fig.add_subplot(band[0, :])
        ax_head.axis("off")
        ax_head.set_title(
            DOMAIN_LABELS[domain_name], fontsize=15, fontweight="semibold", pad=2
        )
        for k_i, key in enumerate(col_keys):
            ax = fig.add_subplot(band[1, k_i])
            z, streams = prep[domain_name]["maps"][key]
            if key in ("shallow_end", "deep_end"):
                last_im_d[domain_name] = ax.imshow(
                    z,
                    origin="lower",
                    cmap=CMAP,
                    vmin=0.0,
                    vmax=prep[domain_name]["vmax_d"],
                    interpolation="nearest",
                    aspect="equal",
                )
            else:
                im_f = ax.imshow(
                    z,
                    origin="lower",
                    cmap=CMAP,
                    vmin=0.0,
                    vmax=1.0,
                    interpolation="nearest",
                    aspect="equal",
                )
            ax.contour(
                streams.astype(float),
                levels=[0.5],
                colors=[STREAM_COLOR],
                linewidths=0.6,
            )
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.set_title(col_titles[key], fontsize=11, pad=4)

    # colorbars: deficit per domain above fraction bar
    for i, domain_name in enumerate(DOMAINS):
        y0 = 0.58 if i == 0 else 0.18
        cax = fig.add_axes([0.90, y0, 0.012, 0.28])
        cb = fig.colorbar(last_im_d[domain_name], cax=cax)
        cb.set_label(f"{DOMAIN_LABELS[domain_name]} deficit (m)", fontsize=10)
        cb.ax.tick_params(labelsize=9)
    cax_f = fig.add_axes([0.90, 0.08, 0.012, 0.08])
    cb_f = fig.colorbar(im_f, cax=cax_f)
    cb_f.set_label("Fraction", fontsize=10)
    cb_f.ax.tick_params(labelsize=9)

    out = FIG_DIR / "shallow_deep_spatial_10yr.png"
    fig.savefig(out, dpi=160, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print("wrote", out)

    # Spearman: f_shallow vs f_temp
    rows = []
    for domain_name in DOMAINS:
        streams, active = landscape[domain_name]
        zp = zone_pairs[domain_name][FOCUS_L]
        cp = col_pairs[domain_name][FOCUS_L]
        f_temp = (
            cp["temporary"]
            / xr.apply_ufunc(np.maximum, cp["temporary"] + cp["persistent"], 1e-12)
        ).values
        f_sh = zp["f_shallow_end"].values
        mask = active & ~streams & np.isfinite(f_temp) & np.isfinite(f_sh)
        col = zp["shallow_end"].values + zp["deep_end"].values
        mask = mask & (col > 1e-4)
        rho, p = spearmanr(f_sh[mask], f_temp[mask])
        rows.append(
            {
                "domain": domain_name,
                "n": int(mask.sum()),
                "rho_f_shallow_f_temp": float(rho),
                "p": float(p),
            }
        )
        deep = zp["deep_end"].values
        pers = cp["persistent"].values
        m2 = active & ~streams & np.isfinite(deep) & np.isfinite(pers) & (col > 1e-4)
        rho2, p2 = spearmanr(deep[m2], pers[m2])
        rows[-1]["rho_deep_persistent"] = float(rho2)
        rows[-1]["p_deep"] = float(p2)
        sh = zp["shallow_end"].values
        temp = cp["temporary"].values
        rho3, p3 = spearmanr(sh[m2], temp[m2])
        rows[-1]["rho_shallow_temporary"] = float(rho3)
        rows[-1]["p_shallow"] = float(p3)
    return rows


def fig_mid_drought_regen(
    series_by_domain: dict,
    pulse_by_domain: dict,
    *,
    outfile: str = "shallow_deep_mid_drought_regen.png",
    include_recovery: bool = False,
):
    """Drought-course near-surface vs deep storage anomalies."""
    fig, axes = plt.subplots(
        2,
        len(DOMAINS),
        figsize=(4.4 * len(DOMAINS), 5.6),
        sharex="col",
        constrained_layout=True,
    )
    if len(DOMAINS) == 1:
        axes = axes.reshape(2, 1)

    drought_patch = Patch(facecolor="C3", alpha=0.25, edgecolor="none", label="drought period")
    recovery_patch = Patch(
        facecolor="#9ECAE1", alpha=0.35, edgecolor="none", label="recovery"
    )
    line_handles = [
        Line2D([0], [0], color=COLORS[L], lw=1.8, label=f"{L}-yr drought")
        for L in DROUGHT_LENGTHS
        if any(L in series_by_domain[d] for d in DOMAINS)
    ]

    for col, domain_name in enumerate(DOMAINS):
        ax_sh = axes[0, col]
        ax_de = axes[1, col]

        for L, ser in series_by_domain[domain_name].items():
            t = ser["t"]
            ax_sh.plot(t, ser["shallow"] / DS_SCALE, color=COLORS[L], lw=1.3, alpha=0.95)
            ax_de.plot(t, ser["deep"] / DS_SCALE, color=COLORS[L], lw=1.3, alpha=0.95)

        Lmax = max(series_by_domain[domain_name])
        for ax in (ax_sh, ax_de):
            ax.axvspan(0, Lmax, color="C3", alpha=0.08)
            if include_recovery:
                ax.axvspan(Lmax, Lmax + RECOVERY_YEARS, color="#9ECAE1", alpha=0.12)
                ax.axvline(Lmax, color="0.35", ls=":", lw=0.9)
            ax.axhline(0.0, color="0.55", lw=0.7)
            ax.xaxis.set_major_locator(MultipleLocator(2 if not include_recovery else 2))
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)

        ax_sh.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)

        if col == 0:
            ax_sh.set_ylabel(r"Near-surface $\Delta S$ ($10^6$ m$^3$)", fontsize=LABEL_FS)
            ax_de.set_ylabel(r"Deep $\Delta S$ ($10^6$ m$^3$)", fontsize=LABEL_FS)

        if col == 1:
            axes[0, 1].sharey(axes[0, 0])
            axes[1, 1].sharey(axes[1, 0])

    fig.supxlabel("Year (from drought start)", fontsize=LABEL_FS)
    legend_handles = line_handles + [drought_patch]
    if include_recovery:
        legend_handles.append(recovery_patch)
    fig.legend(
        handles=legend_handles,
        loc="outside upper center",
        ncol=5,
        frameon=False,
        fontsize=LEGEND_FS,
    )
    out = FIG_DIR / outfile
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_pulse_year_example(series_by_domain: dict):
    """Single mid-drought year: precip + near-surface/deep anomaly (10-yr)."""
    fig, axes = plt.subplots(
        2,
        len(DOMAINS),
        figsize=(4.4 * len(DOMAINS), 5.0),
        sharex="col",
        constrained_layout=True,
    )
    if len(DOMAINS) == 1:
        axes = axes.reshape(2, 1)

    for col, domain_name in enumerate(DOMAINS):
        ser = series_by_domain[domain_name][FOCUS_L]
        # pick year index ~ middle of drought (year 5 of 10)
        mid = 4.0
        m = (ser["t"] >= mid) & (ser["t"] < mid + 1.0)
        t = ser["t"][m] - mid  # year fraction within mid year
        p = ser["precip"][m]
        sh = ser["shallow"][m] / DS_SCALE
        de = ser["deep"][m] / DS_SCALE

        ax_p = axes[0, col]
        ax_s = axes[1, col]
        ax_p.bar(t, p, width=1.0 / STEPS_PER_YEAR * 0.9, color="0.65", edgecolor="none")
        ax_p.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        ax_s.plot(t, sh, color=SHALLOW_COLOR, lw=1.8, label="Near-surface")
        ax_s.plot(t, de, color=DEEP_COLOR, lw=1.8, label="Deep")
        ax_s.axhline(0.0, color="0.55", lw=0.7)
        ax_s.xaxis.set_major_locator(MultipleLocator(0.25))
        ax_s.ticklabel_format(axis="y", style="plain", useOffset=False)
        if col == 0:
            ax_p.set_ylabel("Domain-mean P (mm / 219 h)", fontsize=LABEL_FS)
            ax_s.set_ylabel(r"$\Delta S$ ($10^6$ m$^3$)", fontsize=LABEL_FS)
            ax_s.legend(frameon=False, fontsize=LEGEND_FS)
        if col == 1:
            axes[1, 1].sharey(axes[1, 0])

    fig.supxlabel(f"Year fraction (drought year {int(mid) + 1} of {FOCUS_L})", fontsize=LABEL_FS)
    out = FIG_DIR / "shallow_deep_mid_drought_year_pulse.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_layer_recover_profile(zone_pairs: dict):
    """Domain-total end-drought deficit and recovery fraction by layer (10-yr)."""
    fig, axes = plt.subplots(
        1,
        len(DOMAINS),
        figsize=(4.0 * len(DOMAINS), 4.6),
        sharey=True,
        constrained_layout=True,
    )
    if len(DOMAINS) == 1:
        axes = [axes]

    # depth of layer midpoint from land surface
    depth_mid = np.cumsum(DZ_M[::-1])[::-1] - 0.5 * DZ_M

    for ax, domain_name in zip(axes, DOMAINS):
        zp = zone_pairs[domain_name][FOCUS_L]
        layer_end = zp["layer_end"].sum(dim=("y", "x")).values * CELL_AREA_M2 / DS_SCALE
        layer_rec = zp["layer_rec"].sum(dim=("y", "x")).values * CELL_AREA_M2 / DS_SCALE
        # recovery fraction where end deficit > 0
        with np.errstate(divide="ignore", invalid="ignore"):
            frac = np.where(layer_end > 1e-6, layer_rec / layer_end, np.nan)

        ax2 = ax.twiny()
        ax.barh(
            depth_mid,
            layer_end,
            height=DZ_M * 0.85,
            color="0.75",
            edgecolor="0.3",
            label="End-drought deficit",
        )
        ax2.plot(
            frac,
            depth_mid,
            "o-",
            color="#C51B7D",
            lw=1.5,
            ms=5,
            label="Recovered in yr 1",
        )
        ax.axhline(2.0, color=SHALLOW_COLOR, ls="--", lw=1.2)
        ax.set_ylim(depth_mid.max() * 1.05, 0)  # surface at top
        ax.set_xlabel(r"Deficit ($10^6$ m$^3$)", fontsize=LABEL_FS)
        ax2.set_xlabel("Fraction recovered in year 1", fontsize=LABEL_FS, color="#C51B7D")
        ax2.set_xlim(-0.2, 1.05)
        ax2.tick_params(axis="x", colors="#C51B7D")
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        ax.text(
            0.98,
            0.02,
            "← near-surface\n(top 2 m)",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            color=SHALLOW_COLOR,
        )

    axes[0].set_ylabel("Depth below land surface (m)", fontsize=LABEL_FS)
    out = FIG_DIR / "shallow_deep_layer_recovery_profile_10yr.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    landscape = {d: stream_mask(d) for d in DOMAINS}

    zone_pairs: dict = {}
    col_pairs: dict = {}
    summary = {"shallow_z0": SHALLOW_Z0, "shallow_depth_m": 2.0, "domains": {}}

    for domain_name in DOMAINS:
        zone_pairs[domain_name] = {}
        col_pairs[domain_name] = {}
        summary["domains"][domain_name] = {}
        for L in available_lengths(domain_name):
            print(f"Zone deficits {domain_name} {L}-yr…", flush=True)
            zp = zone_deficit_pair(domain_name, L)
            zone_pairs[domain_name][L] = zp
            col_pairs[domain_name][L] = storage_deficit_pair(domain_name, L)
            tot = domain_zone_totals_m3(zp)
            temp = tot["temp_shallow"] + tot["temp_deep"]
            pers = tot["pers_shallow"] + tot["pers_deep"]
            summary["domains"][domain_name][str(L)] = {
                **{k: v / DS_SCALE for k, v in tot.items()},
                "pct_temp_near_surface": 100.0 * tot["temp_shallow"] / max(temp, 1.0),
                "pct_pers_deep": 100.0 * tot["pers_deep"] / max(pers, 1.0),
            }

    fig_aggregate_partition(zone_pairs)
    fig_layer_recover_profile(zone_pairs)
    spearman_rows = fig_spatial_10yr(zone_pairs, landscape, col_pairs)
    summary["spatial_spearman_10yr"] = spearman_rows

    # mid-drought series (all lengths available on short_baseline years)
    series_by_domain = {}
    series_with_recovery = {}
    pulse_by_domain = {}
    for domain_name in DOMAINS:
        series_by_domain[domain_name] = {}
        series_with_recovery[domain_name] = {}
        for L in DROUGHT_LENGTHS:
            # Mid-drought anomalies need a baseline seasonal year for each drought year.
            # Potomac long baseline is snapshot-only past yr 54, so skip 50-yr there.
            if domain_name == "potomac2" and L == 50:
                continue
            # Keep regen timeseries to ≤10 yr so seasonal pulses stay readable;
            # 50-yr still enters the aggregate partition bars.
            if L > FOCUS_L:
                continue
            print(f"Mid-drought series {domain_name} {L}-yr…", flush=True)
            try:
                ser = drought_zone_series(domain_name, L, include_recovery=False)
                ser_r = drought_zone_series(domain_name, L, include_recovery=True)
            except Exception as exc:
                print(f"  skip: {exc}")
                continue
            if len(ser["t"]) == 0:
                print("  skip: empty series")
                continue
            series_by_domain[domain_name][L] = ser
            series_with_recovery[domain_name][L] = ser_r
        # pulse stats from 10-yr
        print(f"Pulse stats {domain_name}…", flush=True)
        pulse_by_domain[domain_name] = pulse_stats(
            series_by_domain[domain_name][FOCUS_L]
        )
        summary["domains"][domain_name]["pulse_10yr"] = pulse_by_domain[domain_name]

    fig_mid_drought_regen(series_by_domain, pulse_by_domain)
    fig_mid_drought_regen(
        series_with_recovery,
        pulse_by_domain,
        outfile="shallow_deep_mid_drought_regen_with_recovery.png",
        include_recovery=True,
    )
    fig_pulse_year_example(series_by_domain)

    out_json = FIG_DIR / "shallow_deep_shielding_summary.json"
    out_json.write_text(json.dumps(summary, indent=2))
    print("wrote", out_json)
    # Curated narrative lives in shallow_deep_shielding_summary.md — do not overwrite.


if __name__ == "__main__":
    main()
