#!/usr/bin/env python3
"""Early pumping analysis: shallow/deep + fast-loss / mid-year regen proxies.

Recovery years are not on disk yet, so temporary vs persistent cannot be defined
from recovery yr-1. Proxies used here:

1. **Near-surface vs deep** end-of-pump deficits (z≥6 = top 2 m; z<6 = deep).
   Pumping extracts at layer 2 (deep), so deficits may sit deep even where
   drought would have paid with a regenerating near-surface skin.
2. **Fast loss / mid-year regen**: within pumping years, near-surface ΔS that
   oscillates toward zero on precip pulses vs deep ΔS that ratchets down —
   same mid-stress diagnostics as ``shallow_deep_shielding.py``, average-year P.
3. **Fast vs slow domain totals**: project the slow (linear) deficit branch to
   pump onset; residual at onset ≈ fast spike; end-of-pump slow branch ≈
   persistent-like accumulation (no recovery needed).

Outputs → ``analysis/figures/pumping_shallow_deep_*.png`` + summary markdown.
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

from analysis.paper_figures import utils  # noqa: E402
from analysis.redo_pumping_recovery_analogues import (  # noqa: E402
    COLORS,
    DOMAIN_LABELS,
    DOMAINS,
    INTERVAL,
    LABEL_FS,
    LEGEND_FS,
    PUMP_ENSEMBLE,
    PUMP_YEARS,
    RATES,
    SPINUP_YEARS,
    STEPS_PER_YEAR,
    TITLE_FS,
    _resolve_member,
    baseline_219h_files,
    pumping_hourly_files,
)
from analysis.shallow_deep_shielding import (  # noqa: E402
    DEEP_COLOR,
    SHALLOW_COLOR,
    SHALLOW_Z0,
    spearmanr,
)

from analysis.figure_paths import FIG_DIR, FIG_ROOT, fig_path, resolve_figure  # noqa: E402
CACHE_DIR = FIG_DIR / "_pumping_zone_219h_cache"
SUMMARY_MD = ROOT / "analysis" / "pumping_shallow_deep_proxies_summary.md"
DS_SCALE = 1e6
CELL_AREA_M2 = 1_000_000.0
FOCUS_RATE = 1e-5  # mid rate for pulse-year example / spatial maps

FIG_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Forcing / I/O
# ---------------------------------------------------------------------------

_P219_CACHE: dict[str, np.ndarray] = {}


def average_year_precip_219h(domain_name: str) -> np.ndarray:
    """Domain-mean precip (mm) per 219 h window of the average WY."""
    if domain_name in _P219_CACHE:
        return _P219_CACHE[domain_name]
    fdir = ROOT / "domains" / domain_name / "inputs" / f"{domain_name}_average" / "forcing"
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


def zone_cache_path(domain_name: str, year_dir: Path) -> Path:
    return CACHE_DIR / domain_name / f"{year_dir.name}_zone_219h.nc"


def build_zone_219h_from_hourly(domain_name: str, hourly_path: str | Path) -> Path:
    """Slim 219 h: domain near-surface / deep storage + end-year layer maps."""
    hourly_path = Path(hourly_path)
    out = zone_cache_path(domain_name, hourly_path.parent)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return out

    print(f"  caching zone 219h {domain_name}/{hourly_path.parent.name[:12]}…", flush=True)
    with xr.open_dataset(hourly_path, chunks={"time": INTERVAL}) as ds:
        assert int(ds.sizes["time"]) == 8760
        mask = ds["mask"]
        if "time" in mask.dims:
            mask = mask.isel(time=0)
        active = mask.any(dim="z") > 0 if "z" in mask.dims else mask > 0

        stor_snap = ds["subsurface_storage"].isel(time=slice(INTERVAL - 1, None, INTERVAL))
        stor_snap = stor_snap.where(active).compute()
        shallow = stor_snap.isel(z=slice(SHALLOW_Z0, None)).sum(dim=("z", "y", "x"))
        deep = stor_snap.isel(z=slice(0, SHALLOW_Z0)).sum(dim=("z", "y", "x"))
        end = stor_snap.isel(time=-1)
        shallow_map = end.isel(z=slice(SHALLOW_Z0, None)).sum(dim="z")
        deep_map = end.isel(z=slice(0, SHALLOW_Z0)).sum(dim="z")

        times = (np.arange(1, STEPS_PER_YEAR + 1) * INTERVAL).astype(float)
        ds_out = xr.Dataset(
            {
                "shallow_storage": (("time",), shallow.values.astype(np.float64)),
                "deep_storage": (("time",), deep.values.astype(np.float64)),
                "shallow_map_m3": (("y", "x"), shallow_map.values.astype(np.float64)),
                "deep_map_m3": (("y", "x"), deep_map.values.astype(np.float64)),
                "mask": mask,
            },
            coords={"time": times},
        )
        tmp = out.with_suffix(".tmp.nc")
        ds_out.to_netcdf(tmp)
        tmp.replace(out)
    return out


def baseline_zone_year(domain_name: str, year_index: int) -> dict[str, np.ndarray | xr.DataArray]:
    """Near-surface / deep totals (+ end maps) from condensed baseline 219h."""
    path = Path(baseline_219h_files(domain_name)[year_index])
    with xr.open_dataset(path) as ds:
        stor = ds["subsurface_storage"]
        mask = ds["mask"]
        if "time" in mask.dims:
            mask = mask.isel(time=0)
        active = mask.any(dim="z") > 0 if "z" in mask.dims else mask > 0
        stor = stor.where(active)
        sh = stor.isel(z=slice(SHALLOW_Z0, None)).sum(dim=("z", "y", "x")).values.astype(np.float64)
        de = stor.isel(z=slice(0, SHALLOW_Z0)).sum(dim=("z", "y", "x")).values.astype(np.float64)
        end = stor.isel(time=-1)
        return {
            "shallow": sh,
            "deep": de,
            "shallow_map": end.isel(z=slice(SHALLOW_Z0, None)).sum(dim="z").load(),
            "deep_map": end.isel(z=slice(0, SHALLOW_Z0)).sum(dim="z").load(),
        }


def pump_zone_year(domain_name: str, rate: float, year_index: int) -> dict:
    """Year index in [SPINUP_YEARS, SPINUP_YEARS+PUMP_YEARS).

    Prefer consolidated ``processed_output_219h.nc`` (has z-storage + mask). Fall
    back to building a slim zone cache from hourly derived products when needed.
    """
    files_219 = utils._file_locations(
        PUMP_ENSEMBLE, _resolve_member(rate), domain_name, 0, interval=INTERVAL
    )
    path_219 = Path(files_219[year_index])
    if path_219.exists() and path_219.name.startswith("processed_output_219h"):
        with xr.open_dataset(path_219) as ds:
            stor = ds["subsurface_storage"]
            mask = ds["mask"]
            if "time" in mask.dims:
                mask = mask.isel(time=0)
            active = mask.any(dim="z") > 0 if "z" in mask.dims else mask > 0
            stor = stor.where(active)
            sh = (
                stor.isel(z=slice(SHALLOW_Z0, None))
                .sum(dim=("z", "y", "x"))
                .values.astype(np.float64)
            )
            de = (
                stor.isel(z=slice(0, SHALLOW_Z0))
                .sum(dim=("z", "y", "x"))
                .values.astype(np.float64)
            )
            end = stor.isel(time=-1)
            return {
                "shallow": sh,
                "deep": de,
                "shallow_map": end.isel(z=slice(SHALLOW_Z0, None)).sum(dim="z").load(),
                "deep_map": end.isel(z=slice(0, SHALLOW_Z0)).sum(dim="z").load(),
            }

    hourly = pumping_hourly_files(domain_name, rate)
    path = build_zone_219h_from_hourly(domain_name, hourly[year_index])
    with xr.open_dataset(path) as ds:
        return {
            "shallow": ds["shallow_storage"].values.astype(np.float64),
            "deep": ds["deep_storage"].values.astype(np.float64),
            "shallow_map": ds["shallow_map_m3"].load(),
            "deep_map": ds["deep_map_m3"].load(),
        }


def pumping_zone_series(domain_name: str, rate: float) -> dict:
    """Shallow/deep anomalies for 3 pump years; t=0 at pump onset."""
    p_year = average_year_precip_219h(domain_name)
    t_all, sh_all, de_all, p_all = [], [], [], []
    for k in range(PUMP_YEARS):
        year = SPINUP_YEARS + k
        pump = pump_zone_year(domain_name, rate, year)
        base = baseline_zone_year(domain_name, year)
        n = min(len(pump["shallow"]), len(base["shallow"]), len(p_year))
        t_all.append(k + np.arange(n, dtype=np.float64) / STEPS_PER_YEAR)
        sh_all.append(pump["shallow"][:n] - base["shallow"][:n])
        de_all.append(pump["deep"][:n] - base["deep"][:n])
        p_all.append(p_year[:n])
    return {
        "t": np.concatenate(t_all),
        "shallow": np.concatenate(sh_all),
        "deep": np.concatenate(de_all),
        "precip": np.concatenate(p_all),
        "rate": rate,
    }


def end_deficit_maps(domain_name: str, rate: float, pump_year_k: int) -> dict:
    """End-of pump year k (0-based) shallow/deep deficit maps (m water)."""
    year = SPINUP_YEARS + pump_year_k
    pump = pump_zone_year(domain_name, rate, year)
    base = baseline_zone_year(domain_name, year)
    sh = (base["shallow_map"] - pump["shallow_map"]) / CELL_AREA_M2
    de = (base["deep_map"] - pump["deep_map"]) / CELL_AREA_M2
    col = sh + de
    f_sh = sh / xr.apply_ufunc(np.maximum, col, 1e-12)
    return {"shallow": sh, "deep": de, "f_shallow": f_sh, "col": col}


def pulse_stats(series: dict) -> dict:
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


def midyear_regen_metrics(series: dict) -> dict:
    """Per-year: seasonal rebound (max−min of anomaly) vs net year change."""
    rows = []
    for k in range(PUMP_YEARS):
        m = (series["t"] >= k) & (series["t"] < k + 1)
        for zone, key in (("shallow", "shallow"), ("deep", "deep")):
            y = series[key][m]
            if y.size < 4:
                continue
            net = float(y[-1] - y[0])
            amp = float(np.nanmax(y) - np.nanmin(y))
            # regen proxy: upward excursions relative to year-start (m³)
            rebound = float(np.nanmax(y) - y[0])
            rows.append(
                {
                    "year_k": k,
                    "zone": zone,
                    "net_m3": net,
                    "amp_m3": amp,
                    "rebound_m3": rebound,
                }
            )
    return {"by_year": rows}


def fast_slow_decomposition(series: dict) -> dict:
    """Project slow linear deficit branch to t=0; residual = fast spike proxy.

    Deficit = −(shallow+deep) anomaly in 10⁶ m³. Fit late branch (t≥1 yr) and
    full-period linear; report onset spike and end-of-pump slow deficit.
    """
    tot = -(series["shallow"] + series["deep"]) / DS_SCALE
    t = series["t"]
    late = t >= 1.0
    if late.sum() < 5:
        late = t >= 0.5
    coef = np.polyfit(t[late], tot[late], 1)
    slow_at_0 = float(np.polyval(coef, 0.0))
    slow_at_end = float(np.polyval(coef, float(t[-1])))
    total_at_0 = float(tot[0])
    total_at_end = float(tot[-1])
    spike = max(total_at_0 - slow_at_0, 0.0)
    # also split end deficit into shallow vs deep
    sh_end = float(-series["shallow"][-1] / DS_SCALE)
    de_end = float(-series["deep"][-1] / DS_SCALE)
    return {
        "spike_1e6m3": spike,
        "slow_at_0_1e6m3": slow_at_0,
        "slow_at_end_1e6m3": slow_at_end,
        "total_at_0_1e6m3": total_at_0,
        "total_at_end_1e6m3": total_at_end,
        "shallow_end_deficit_1e6m3": sh_end,
        "deep_end_deficit_1e6m3": de_end,
        "pct_end_deep": 100.0 * de_end / max(sh_end + de_end, 1e-9),
        "slope_1e6m3_per_yr": float(coef[0]),
    }


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def fig_mid_pump_regen(series_by_domain: dict):
    fig, axes = plt.subplots(
        2,
        len(DOMAINS),
        figsize=(4.4 * len(DOMAINS), 5.6),
        sharex="col",
        constrained_layout=True,
    )
    pump_patch = Patch(facecolor="C3", alpha=0.25, edgecolor="none", label="pumping period")
    line_handles = [
        Line2D([0], [0], color=COLORS[r], lw=1.8, label=f"{r:.0e} m/h")
        for r in RATES
        if any(r in series_by_domain[d] for d in DOMAINS)
    ]

    for col, domain_name in enumerate(DOMAINS):
        ax_sh = axes[0, col]
        ax_de = axes[1, col]
        for rate, ser in series_by_domain[domain_name].items():
            ax_sh.plot(ser["t"], ser["shallow"] / DS_SCALE, color=COLORS[rate], lw=1.3, alpha=0.95)
            ax_de.plot(ser["t"], ser["deep"] / DS_SCALE, color=COLORS[rate], lw=1.3, alpha=0.95)
        for ax in (ax_sh, ax_de):
            ax.axvspan(0, PUMP_YEARS, color="C3", alpha=0.08)
            ax.axhline(0.0, color="0.55", lw=0.7)
            ax.xaxis.set_major_locator(MultipleLocator(1))
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax_sh.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        if col == 0:
            ax_sh.set_ylabel(r"Near-surface $\Delta S$ ($10^6$ m$^3$)", fontsize=LABEL_FS)
            ax_de.set_ylabel(r"Deep $\Delta S$ ($10^6$ m$^3$)", fontsize=LABEL_FS)
        if col == 1:
            axes[0, 1].sharey(axes[0, 0])
            axes[1, 1].sharey(axes[1, 0])

    fig.supxlabel("Year (from pumping start)", fontsize=LABEL_FS)
    fig.legend(
        handles=line_handles + [pump_patch],
        loc="outside upper center",
        ncol=5,
        frameon=False,
        fontsize=LEGEND_FS,
    )
    out = FIG_DIR / "pumping_shallow_deep_mid_pump_regen.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_pulse_year(series_by_domain: dict, rate: float = FOCUS_RATE):
    """Precip + near-surface / deep anomalies for one mid-pump year.

    Near-surface and deep use separate y-axes so the regenerating skin is
    visible beside the much larger deep ratchet.
    """
    fig, axes = plt.subplots(
        3,
        len(DOMAINS),
        figsize=(4.4 * len(DOMAINS), 6.2),
        sharex="col",
        constrained_layout=True,
    )
    mid = float(PUMP_YEARS // 2)  # middle pump year (0-based start)
    for col, domain_name in enumerate(DOMAINS):
        ser = series_by_domain[domain_name][rate]
        m = (ser["t"] >= mid) & (ser["t"] < mid + 1.0)
        t = ser["t"][m] - mid
        ax_p = axes[0, col]
        ax_sh = axes[1, col]
        ax_de = axes[2, col]
        ax_p.bar(
            t,
            ser["precip"][m],
            width=1.0 / STEPS_PER_YEAR * 0.9,
            color="0.65",
            edgecolor="none",
        )
        ax_p.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        ax_sh.plot(t, ser["shallow"][m] / DS_SCALE, color=SHALLOW_COLOR, lw=1.8)
        ax_de.plot(t, ser["deep"][m] / DS_SCALE, color=DEEP_COLOR, lw=1.8)
        for ax in (ax_sh, ax_de):
            ax.axhline(0.0, color="0.55", lw=0.7)
            ax.xaxis.set_major_locator(MultipleLocator(0.25))
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        if col == 0:
            ax_p.set_ylabel("Domain-mean P (mm / 219 h)", fontsize=LABEL_FS)
            ax_sh.set_ylabel(r"Near-surface $\Delta S$ ($10^6$ m$^3$)", fontsize=LABEL_FS)
            ax_de.set_ylabel(r"Deep $\Delta S$ ($10^6$ m$^3$)", fontsize=LABEL_FS)
        if col == 1:
            axes[1, 1].sharey(axes[1, 0])
            axes[2, 1].sharey(axes[2, 0])

    fig.supxlabel(
        f"Year fraction (pump year {int(mid) + 1} of {PUMP_YEARS}; rate {rate:.0e} m/h)",
        fontsize=LABEL_FS,
    )
    out = FIG_DIR / "pumping_shallow_deep_mid_pump_year_pulse.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_depth_partition_bars(end_totals: dict):
    """Stacked near-surface vs deep end-pump deficits by rate (yr1 / end stress)."""
    fig, axes = plt.subplots(
        1,
        len(DOMAINS),
        figsize=(4.4 * len(DOMAINS), 4.4),
        sharey=False,
        constrained_layout=True,
    )
    x = np.arange(len(RATES), dtype=float)
    width = 0.36
    legend_handles = [
        Patch(facecolor=SHALLOW_COLOR, edgecolor="0.2", label="Near-surface (top 2 m)"),
        Patch(facecolor=DEEP_COLOR, edgecolor="0.2", label="Deep (>2 m)"),
    ]

    for ax, domain_name in zip(axes, DOMAINS):
        for offset, which, alpha in ((-width / 2, "yr1", 1.0), (width / 2, "end", 0.95)):
            sh, de = [], []
            for rate in RATES:
                tot = end_totals[domain_name][rate][which]
                sh.append(tot["shallow"] / DS_SCALE)
                de.append(tot["deep"] / DS_SCALE)
            ax.bar(
                x + offset,
                sh,
                width,
                color=SHALLOW_COLOR,
                edgecolor="0.2",
                linewidth=0.6,
                alpha=alpha,
            )
            ax.bar(
                x + offset,
                de,
                width,
                bottom=sh,
                color=DEEP_COLOR,
                edgecolor="0.2",
                linewidth=0.6,
                alpha=alpha,
            )
        ax.set_xticks(x)
        ax.set_xticklabels([f"{r:.0e}" for r in RATES], rotation=15)
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.axhline(0.0, color="0.5", lw=0.6)
        ymax = ax.get_ylim()[1]
        for i in range(len(RATES)):
            ax.text(x[i] - width / 2, ymax * 0.02, "Y1", ha="center", va="bottom", fontsize=8, color="0.35")
            ax.text(
                x[i] + width / 2,
                ymax * 0.02,
                f"Y{PUMP_YEARS}",
                ha="center",
                va="bottom",
                fontsize=8,
                color="0.35",
            )

    axes[0].set_ylabel(r"Storage deficit ($10^6$ m$^3$)", fontsize=LABEL_FS)
    fig.supxlabel("Pumping rate (m/h domain-avg)", fontsize=LABEL_FS)
    fig.legend(
        handles=legend_handles
        + [
            Line2D([0], [0], color="none", label="Y1 = end pump year 1"),
            Line2D([0], [0], color="none", label=f"Y{PUMP_YEARS} = end of pumping"),
        ],
        loc="outside upper center",
        ncol=4,
        frameon=False,
        fontsize=LEGEND_FS,
    )
    out = FIG_DIR / "pumping_shallow_deep_end_deficit_partition.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def seasonal_fast_proxy(series: dict) -> dict:
    """Temp-like proxy = mean mid-year near-surface rebound; persist-like = deep net/yr.

    Rebound = max(anomaly) − year-start within each pump year (upward pulse).
    Deep net = year-start − year-end (drawdown; positive = loss).
    Drought-style onset-spike projection is ~0 under pumping (deficit grows from
    zero), so seasonal rebound is the useful fast-loss stand-in.
    """
    sh_reb, de_net = [], []
    for k in range(PUMP_YEARS):
        m = (series["t"] >= k) & (series["t"] < k + 1)
        sh = series["shallow"][m]
        de = series["deep"][m]
        if sh.size < 4:
            continue
        sh_reb.append(float(np.nanmax(sh) - sh[0]))
        de_net.append(float(de[0] - de[-1]))  # positive if deep loses
    return {
        "ns_rebound_mean_1e6m3": float(np.mean(sh_reb)) / DS_SCALE if sh_reb else 0.0,
        "deep_net_mean_1e6m3": float(np.mean(de_net)) / DS_SCALE if de_net else 0.0,
    }


def fig_fast_regen_vs_deep_bars(proxies: dict):
    """Near-surface mid-year rebound (temp proxy) vs deep annual net loss."""
    fig, axes = plt.subplots(
        1,
        len(DOMAINS),
        figsize=(4.4 * len(DOMAINS), 4.2),
        sharey=False,
        constrained_layout=True,
    )
    x = np.arange(len(RATES), dtype=float)
    width = 0.36
    for ax, domain_name in zip(axes, DOMAINS):
        reb = [proxies[domain_name][r]["ns_rebound_mean_1e6m3"] for r in RATES]
        deep = [proxies[domain_name][r]["deep_net_mean_1e6m3"] for r in RATES]
        ax.bar(
            x - width / 2,
            reb,
            width,
            color=SHALLOW_COLOR,
            edgecolor="0.2",
            label="Near-surface mid-year rebound",
        )
        ax.bar(
            x + width / 2,
            deep,
            width,
            color=DEEP_COLOR,
            edgecolor="0.2",
            label="Deep net loss / year",
        )
        ax.set_xticks(x)
        ax.set_xticklabels([f"{r:.0e}" for r in RATES], rotation=15)
        ax.set_title(DOMAIN_LABELS[domain_name], fontsize=TITLE_FS)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.axhline(0.0, color="0.5", lw=0.6)
    axes[0].set_ylabel(r"Storage ($10^6$ m$^3$)", fontsize=LABEL_FS)
    fig.supxlabel("Pumping rate (m/h domain-avg)", fontsize=LABEL_FS)
    fig.legend(loc="outside upper center", ncol=2, frameon=False, fontsize=LEGEND_FS)
    out = FIG_DIR / "pumping_fast_regen_vs_deep_drawdown.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_spatial_f_shallow(maps_by_domain: dict, rate: float = FOCUS_RATE):
    """End yr3: shallow deficit, deep deficit, f_shallow."""
    from analysis.redo_pumping_recovery_analogues import STREAM_COLOR, _prepare_map, stream_mask

    col_keys = ("shallow", "deep", "f_shallow")
    col_titles = {
        "shallow": "Near-surface deficit (m)",
        "deep": "Deep deficit (m)",
        "f_shallow": "Fraction near-surface",
    }
    landscape = {d: stream_mask(d) for d in DOMAINS}

    prep = {}
    for domain_name in DOMAINS:
        streams, active = landscape[domain_name]
        mp = maps_by_domain[domain_name]
        fields = {k: mp[k].values for k in col_keys}
        prepared = {}
        depth_stack = []
        for key, arr in fields.items():
            z, st = _prepare_map(arr, streams, active, align_landscape=True)
            prepared[key] = (z, st)
            if key in ("shallow", "deep"):
                depth_stack.append(z[np.isfinite(z)])
        vmax_d = float(np.nanpercentile(np.abs(np.concatenate(depth_stack)), 98)) if depth_stack else 1e-3
        prep[domain_name] = {"maps": prepared, "vmax_d": max(vmax_d, 1e-3)}

    fig = plt.figure(figsize=(12.0, 6.8), constrained_layout=False)
    outer = fig.add_gridspec(
        len(DOMAINS), 1, left=0.08, right=0.88, top=0.95, bottom=0.08, hspace=0.28
    )
    im_f = None
    last_im_d = {}
    for d_i, domain_name in enumerate(DOMAINS):
        band = outer[d_i].subgridspec(
            2, len(col_keys), height_ratios=[0.28, 1.0], hspace=0.12, wspace=0.12
        )
        ax_head = fig.add_subplot(band[0, :])
        ax_head.axis("off")
        ax_head.set_title(
            f"{DOMAIN_LABELS[domain_name]}  ({rate:.0e} m/h, end pump yr 3)",
            fontsize=14,
            fontweight="semibold",
            pad=2,
        )
        for k_i, key in enumerate(col_keys):
            ax = fig.add_subplot(band[1, k_i])
            z, streams = prep[domain_name]["maps"][key]
            if key in ("shallow", "deep"):
                last_im_d[domain_name] = ax.imshow(
                    z,
                    origin="lower",
                    cmap="YlOrBr",
                    vmin=0.0,
                    vmax=prep[domain_name]["vmax_d"],
                    interpolation="nearest",
                    aspect="equal",
                )
            else:
                im_f = ax.imshow(
                    z,
                    origin="lower",
                    cmap="YlOrBr",
                    vmin=0.0,
                    vmax=1.0,
                    interpolation="nearest",
                    aspect="equal",
                )
            ax.contour(streams.astype(float), levels=[0.5], colors=[STREAM_COLOR], linewidths=0.6)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.set_title(col_titles[key], fontsize=11, pad=4)

    for i, domain_name in enumerate(DOMAINS):
        y0 = 0.58 if i == 0 else 0.18
        cax = fig.add_axes([0.90, y0, 0.012, 0.28])
        cb = fig.colorbar(last_im_d[domain_name], cax=cax)
        cb.set_label(f"{DOMAIN_LABELS[domain_name]} deficit (m)", fontsize=10)
    cax_f = fig.add_axes([0.90, 0.08, 0.012, 0.08])
    cb_f = fig.colorbar(im_f, cax=cax_f)
    cb_f.set_label("Fraction", fontsize=10)

    out = FIG_DIR / "pumping_shallow_deep_spatial_end_yr3.png"
    fig.savefig(out, dpi=160, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print("wrote", out)


def write_summary(summary: dict):
    lines = [
        "# Pumping: shallow/deep + fast-loss proxies (no recovery yet)",
        "",
        "**Date:** August 2026  ",
        "**Script:** [`pumping_shallow_deep_proxies.py`](pumping_shallow_deep_proxies.py)  ",
        "",
        "Recovery years are not on disk, so temporary/persistent cannot be defined",
        "from recovery year 1. This early look asks whether **near-surface (fast /",
        "regenerating)** vs **deep (slow / accumulating)** losses still diverge under",
        "pumping — where extraction is applied at **layer 2 (deep)**, including in",
        "high water-availability cells.",
        "",
        "## Proxies",
        "",
        "| Proxy | Definition |",
        "|-------|------------|",
        "| Near-surface / deep deficit | End-pump column deficit split at 2 m (z≥6 vs z<6) |",
        "| Mid-pump regen | Near-surface ΔS pulses with average-year P; deep ΔS ratchets |",
        "| Fast / temp proxy | Mean mid-year near-surface rebound (max − year-start) |",
        "| Persist-like proxy | Mean deep net loss per pump year |",
        "",
        "Note: the drought-style onset-spike (project slow branch to t=0) is ~0 under",
        "pumping — deficit grows from near zero — so seasonal rebound is the useful",
        "fast-loss stand-in until recovery years exist.",
        "",
        "## Figures",
        "",
        "- [pumping_shallow_deep_mid_pump_regen.png](figures/pumping_shallow_deep_mid_pump_regen.png)",
        "- [pumping_shallow_deep_mid_pump_year_pulse.png](figures/pumping_shallow_deep_mid_pump_year_pulse.png)",
        "- [pumping_shallow_deep_end_deficit_partition.png](figures/pumping_shallow_deep_end_deficit_partition.png)",
        "- [pumping_fast_regen_vs_deep_drawdown.png](figures/pumping_fast_regen_vs_deep_drawdown.png)",
        "- [pumping_shallow_deep_spatial_end_yr3.png](figures/pumping_shallow_deep_spatial_end_yr3.png)",
        "",
        "## End-of-pump depth partition (% of deficit in deep)",
        "",
        "| Domain | Rate | End yr 1 % deep | End yr 3 % deep |",
        "|--------|------|----------------:|----------------:|",
    ]
    for domain_name in DOMAINS:
        for rate in RATES:
            y1 = summary["end_totals"][domain_name][str(rate)]["yr1"]
            y3 = summary["end_totals"][domain_name][str(rate)]["end"]
            tot1 = y1["shallow"] + y1["deep"]
            tot3 = y3["shallow"] + y3["deep"]
            pct1 = 100.0 * y1["deep"] / max(tot1, 1e-9)
            pct3 = 100.0 * y3["deep"] / max(tot3, 1e-9)
            lines.append(
                f"| {DOMAIN_LABELS[domain_name]} | {rate:.0e} | {pct1:.0f} | {pct3:.0f} |"
            )

    lines += [
        "",
        "## Mid-pump wet-window ΔS (pooled 219 h; 1e-5 m/h)",
        "",
        "| Domain | Wet ΔS near-surface | Wet ΔS deep | ρ(P, ΔS_ns) | ρ(P, ΔS_deep) |",
        "|--------|--------------------:|------------:|------------:|--------------:|",
    ]
    for domain_name in DOMAINS:
        ps = summary["pulse"][domain_name][str(FOCUS_RATE)]
        lines.append(
            f"| {DOMAIN_LABELS[domain_name]} | "
            f"{ps['wet_d_shallow']/DS_SCALE:+.1f}×10⁶ m³ | "
            f"{ps['wet_d_deep']/DS_SCALE:+.1f}×10⁶ m³ | "
            f"{ps['corr_p_shallow']:.2f} | {ps['corr_p_deep']:.2f} |"
        )

    lines += [
        "",
        "## Mid-year regen vs deep drawdown (10⁶ m³ / year mean)",
        "",
        "| Domain | Rate | NS mid-year rebound | Deep net loss / yr |",
        "|--------|------|--------------------:|-------------------:|",
    ]
    for domain_name in DOMAINS:
        for rate in RATES:
            d = summary["fast_proxy"][domain_name][str(rate)]
            lines.append(
                f"| {DOMAIN_LABELS[domain_name]} | {rate:.0e} | "
                f"{d['ns_rebound_mean_1e6m3']:.2f} | {d['deep_net_mean_1e6m3']:.1f} |"
            )

    lines += [
        "",
        "## Takeaways (early)",
        "",
    ]
    for note in summary.get("takeaways", []):
        lines.append(f"- {note}")
    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "conda activate /glade/work/bwest/conda-envs/droughts",
        "source ~/pf_env.sh",
        "cd /glade/derecho/scratch/bwest/drought-ensemble",
        "python analysis/pumping_shallow_deep_proxies.py",
        "```",
        "",
    ]
    SUMMARY_MD.write_text("\n".join(lines))
    print("wrote", SUMMARY_MD)


def main():
    series_by_domain: dict = {d: {} for d in DOMAINS}
    end_totals: dict = {d: {} for d in DOMAINS}
    decomp: dict = {d: {} for d in DOMAINS}
    pulse: dict = {d: {} for d in DOMAINS}
    regen: dict = {d: {} for d in DOMAINS}
    fast_proxy: dict = {d: {} for d in DOMAINS}
    maps_focus: dict = {}

    for domain_name in DOMAINS:
        for rate in RATES:
            print(f"Series {domain_name} {rate:.0e}…", flush=True)
            ser = pumping_zone_series(domain_name, rate)
            series_by_domain[domain_name][rate] = ser
            pulse[domain_name][rate] = pulse_stats(ser)
            regen[domain_name][rate] = midyear_regen_metrics(ser)
            decomp[domain_name][rate] = fast_slow_decomposition(ser)
            fast_proxy[domain_name][rate] = seasonal_fast_proxy(ser)
            print(
                f"  ns_reb={fast_proxy[domain_name][rate]['ns_rebound_mean_1e6m3']:.2f} "
                f"deep_net={fast_proxy[domain_name][rate]['deep_net_mean_1e6m3']:.1f} "
                f"%deep_end={decomp[domain_name][rate]['pct_end_deep']:.0f} "
                f"ρ_ns={pulse[domain_name][rate]['corr_p_shallow']:.2f} "
                f"ρ_de={pulse[domain_name][rate]['corr_p_deep']:.2f}",
                flush=True,
            )

            end_totals[domain_name][rate] = {}
            end_k = PUMP_YEARS - 1
            for which, k in (("yr1", 0), ("end", end_k)):
                mp = end_deficit_maps(domain_name, rate, k)
                sh = float(np.nansum(np.maximum(mp["shallow"].values, 0.0))) * CELL_AREA_M2
                de = float(np.nansum(np.maximum(mp["deep"].values, 0.0))) * CELL_AREA_M2
                end_totals[domain_name][rate][which] = {"shallow": sh, "deep": de}
            if rate == FOCUS_RATE:
                maps_focus[domain_name] = end_deficit_maps(domain_name, rate, end_k)

    fig_mid_pump_regen(series_by_domain)
    fig_pulse_year(series_by_domain, FOCUS_RATE)
    fig_depth_partition_bars(end_totals)
    fig_fast_regen_vs_deep_bars(fast_proxy)
    fig_spatial_f_shallow(maps_focus, FOCUS_RATE)

    # takeaways from numbers
    takeaways = []
    for domain_name in DOMAINS:
        ps = pulse[domain_name][FOCUS_RATE]
        takeaways.append(
            f"**{DOMAIN_LABELS[domain_name]}** mid-pump (1e-5): wet-window near-surface "
            f"ΔS {ps['wet_d_shallow']/DS_SCALE:+.1f}×10⁶ m³ vs deep "
            f"{ps['wet_d_deep']/DS_SCALE:+.1f}×10⁶ m³ "
            f"(ρ(P,ns)={ps['corr_p_shallow']:.2f}, ρ(P,deep)={ps['corr_p_deep']:.2f})."
        )
        pcts = [
            100.0
            * end_totals[domain_name][r]["end"]["deep"]
            / max(
                end_totals[domain_name][r]["end"]["shallow"]
                + end_totals[domain_name][r]["end"]["deep"],
                1e-9,
            )
            for r in RATES
        ]
        takeaways.append(
            f"**{DOMAIN_LABELS[domain_name]}** end-of-pump deficit is "
            f"{min(pcts):.0f}–{max(pcts):.0f}% deep across rates "
            "(extraction at layer 2; contrast drought where temporary ≈ near-surface)."
        )
    for domain_name in DOMAINS:
        fp = fast_proxy[domain_name][FOCUS_RATE]
        takeaways.append(
            f"**{DOMAIN_LABELS[domain_name]}** (1e-5): mean near-surface mid-year rebound "
            f"{fp['ns_rebound_mean_1e6m3']:.1f}×10⁶ m³ vs deep net loss "
            f"{fp['deep_net_mean_1e6m3']:.0f}×10⁶ m³/yr — regenerating skin is tiny "
            "beside the deep ratchet."
        )
    takeaways.append(
        "Drought-style onset spike ≈ 0 under pumping (deficit grows from ~0); "
        "seasonal near-surface rebound is the better temporary proxy until recovery runs."
    )

    # JSON-serializable summary
    def _ser_nested(obj):
        if isinstance(obj, dict):
            return {str(k): _ser_nested(v) for k, v in obj.items()}
        if isinstance(obj, (np.floating, float)):
            return float(obj)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        return obj

    summary = {
        "end_totals": _ser_nested(end_totals),
        "decomp": _ser_nested(decomp),
        "pulse": _ser_nested(pulse),
        "regen": _ser_nested(regen),
        "fast_proxy": _ser_nested(fast_proxy),
        "takeaways": takeaways,
        "focus_rate": FOCUS_RATE,
        "shallow_z0": SHALLOW_Z0,
    }
    json_path = FIG_DIR / "pumping_shallow_deep_proxies.json"
    json_path.write_text(json.dumps(summary, indent=2))
    print("wrote", json_path)
    write_summary(summary)


if __name__ == "__main__":
    main()
