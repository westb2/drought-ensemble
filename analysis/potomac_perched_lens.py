#!/usr/bin/env python3
"""Perched-lens mechanism behind Potomac's slow near-surface recovery (psa workstream B).

Builds on ``potomac_sensitivity_attribution.py`` (imported, never re-run) and
answers four questions:

1. Structure: is the saturated lens in layer z5 (2–7 m) a permeability contrast
   in the CONUS2 indicator, or the ``FBz`` flow barrier? ParFlow multiplies the
   flux through the *upper* face of each cell by ``FBz``; CONUS2 puts a 0.001
   barrier on either the z4/z5 face (7 m) or the z5/z6 face (2 m).
2. Drought: does the lens survive the 10-yr drought, and does its loss predict
   the near-surface remaining fraction R₂ better than the ET-regime flip?
3. Sensitivity of the key-class result to the shallowest-WT class edges, the
   perched threshold and the pressure-head criterion.
4. Wolf: do its lenses stay wet?

Layers are indexed bottom→top (z0 = 200 m thick bottom, z9 = 0.1 m top).
The "lens layer" of a cell is the layer directly above its barrier face.

Outputs: ``_data/psa_lens.json`` and ``psa_lens_*.png`` (drought_exploratory).

Reproduce::

    conda activate /glade/work/bwest/conda-envs/droughts
    cd /glade/derecho/scratch/bwest/drought-ensemble
    python analysis/potomac_perched_lens.py
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
import yaml
from matplotlib.colors import BoundaryNorm, ListedColormap, SymLogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis import potomac_sensitivity_attribution as P  # noqa: E402
from analysis import psa_extract as X  # noqa: E402
from analysis import redo_recovery_with_50yr as R  # noqa: E402
from analysis.budyko_temp_persistent import spearmanr  # noqa: E402
from analysis.figure_paths import FIG_DIR  # noqa: E402

DOMAINS = P.DOMAINS
LABEL = P.LABEL
LABEL_FS, LEGEND_FS, TITLE_FS = P.LABEL_FS, P.LEGEND_FS, P.TITLE_FS
LENS_JSON = P.DATA_DIR / "psa_lens.json"
DZ = X.DZ_M  # bottom→top, m
TOP_FACE_DEPTH = np.round([DZ[k + 1:].sum() for k in range(len(DZ))], 6)  # depth of each layer's upper face
CENTER_DEPTH = TOP_FACE_DEPTH + DZ / 2
H_YR = P.H_YR
BASE_YEARS = P.BASE_YEARS
D10_DRY_LATE = list(range(45, 50))
D10_YEARS = list(range(40, 55))
KEY_CLASS = 4
DOMAIN_COLORS = {"potomac2": "#4A2410", "wolf2": "#B86B2B"}


# ---------------------------------------------------------------------------
# Static structure
# ---------------------------------------------------------------------------

def _vg_table(run_yaml: Path) -> dict[int, tuple[float, float]]:
    """Indicator code → (alpha, n); geology/bedrock use the domain default."""
    y = yaml.safe_load(run_yaml.read_text())
    dom = y["Geom"]["domain"]["RelPerm"]
    default = (float(dom["Alpha"]), float(dom["N"]))
    table = {}
    for name, spec in y["GeomInput"].items():
        if isinstance(spec, dict) and "Value" in spec and name not in ("domaininput", "indi_input"):
            g = y["Geom"].get(name, {})
            rp = g.get("RelPerm")
            table[int(spec["Value"])] = (float(rp["Alpha"]), float(rp["N"])) if rp else default
    return table


@lru_cache(maxsize=None)
def structure(domain: str) -> dict:
    ds0 = P.year_ds(domain, "short_baseline", 39)
    src = Path(ds0.attrs["source_219h"])
    st_dir = ROOT / "domains" / domain / "inputs" / "static"
    ind = pf.read_pfb(str(st_dir / "pf_indicator.pfb"))
    fb = pf.read_pfb(str(st_dir / "pf_flowbarrier.pfb"))
    with xr.open_dataset(src) as raw:
        kz = np.asarray(raw["perm_z"].values)
        kx = np.asarray(raw["perm_x"].values)
        por = np.asarray(raw["porosity"].values)
    vg = _vg_table(src.parent / "run.yaml")
    codes = np.nan_to_num(ind).astype(int)
    alpha = np.vectorize(lambda c: vg.get(c, (np.nan, np.nan))[0])(codes)
    n_vg = np.vectorize(lambda c: vg.get(c, (np.nan, np.nan))[1])(codes)
    act = P.statics(domain)["active"]
    has_fb = (fb < 1.0).any(axis=0)
    if not np.all(has_fb[act]) or np.any((fb < 1.0).sum(axis=0)[act] > 1):
        raise RuntimeError(f"{domain}: expected exactly one barrier layer per active cell")
    fb_layer = np.argmax(fb < 1.0, axis=0)  # barrier on this layer's upper face
    lens_layer = fb_layer + 1
    traits = {k: v.values for k, v in xr.open_dataset(P.DATA_DIR / f"cell_traits_{domain}.nc").data_vars.items()}
    s_c = float(xr.open_dataset(P.DATA_DIR / f"cell_traits_{domain}.nc").attrs["breakpoint_pooled_s_c"])
    return {"ind": codes, "fb": fb, "fb_value": float(fb[fb < 1].min()), "fb_layer": fb_layer,
            "lens_layer": lens_layer, "barrier_depth": TOP_FACE_DEPTH[fb_layer], "kz": kz, "kx": kx,
            "por": por, "alpha": alpha, "n_vg": n_vg, "active": act, "traits": traits, "s_c": s_c}


def _take(a3: np.ndarray, layer: np.ndarray) -> np.ndarray:
    """a3 (..., z, y, x) sampled at per-cell layer index (y, x)."""
    idx = np.broadcast_to(layer, a3.shape[:-3] + (1,) + layer.shape)
    return np.take_along_axis(a3, idx, axis=-3)[..., 0, :, :]


# ---------------------------------------------------------------------------
# Pressure access (raw 219 h snapshots; ~0.4 s per Potomac year)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=96)
def pressure(domain: str, member: str, y: int) -> np.ndarray:
    key = P.base_key(domain, y) if member == "BASE" else P.member_key(domain, member, y)
    with xr.open_dataset(P._index(domain)[key]) as c:
        src = c.attrs["source_219h"]
    with xr.open_dataset(src) as raw:
        return np.asarray(raw["pressure"].values, dtype=np.float32)  # time, z, y, x


def pressure_stack(domain: str, member: str, years: list[int]) -> np.ndarray:
    return np.concatenate([pressure(domain, member, y) for y in years])


def vg_kr(p: np.ndarray, alpha: np.ndarray, n: np.ndarray) -> np.ndarray:
    m = 1.0 - 1.0 / n
    ah = alpha * np.maximum(-p, 0.0)
    num = (1.0 - ah ** (n - 1) * (1.0 + ah ** n) ** (-m)) ** 2
    return np.where(p >= 0, 1.0, num / (1.0 + ah ** n) ** (m / 2))


def face_flux_down(p: np.ndarray, st: dict, lower: np.ndarray, fb_mult: np.ndarray | float) -> np.ndarray:
    """Downward Darcy flux (m/h) through the upper face of layer ``lower``.

    Same discretisation as ParFlow ``nl_function_eval.c``: dz-weighted harmonic
    Kz, upstream relative permeability, then × FBz of the lower cell.
    """
    upper = lower + 1
    pl, pu = _take(p, lower), _take(p, upper)
    dzl, dzu = DZ[lower], DZ[upper]
    kl, ku = _take(st["kz"], lower), _take(st["kz"], upper)
    k_face = (dzl + dzu) / (dzl / kl + dzu / ku)
    sep = 0.5 * (dzl + dzu)
    diff_up = (pl - pu) / sep - 1.0  # > 0 → upward flow
    kr_l = vg_kr(pl, _take(st["alpha"], lower), _take(st["n_vg"], lower))
    kr_u = vg_kr(pu, _take(st["alpha"], upper), _take(st["n_vg"], upper))
    kr = np.where(diff_up >= 0, kr_l, kr_u)
    return -k_face * diff_up * kr * fb_mult


# ---------------------------------------------------------------------------
# Lens state
# ---------------------------------------------------------------------------

def lens_state(p: np.ndarray, st: dict, h_crit: float = 0.0) -> dict[str, np.ndarray]:
    """Per window: head on the barrier, lens present, lens perched on unsaturated layer."""
    pl = _take(p, st["lens_layer"])
    pb = _take(p, st["fb_layer"])
    head_on_barrier = np.maximum(pl + DZ[st["lens_layer"]] / 2, 0.0)
    present = pl >= h_crit
    return {"head": head_on_barrier, "present": present, "perched": present & (pb < 0.0), "p_below": pb}


def shallowest_wt(p: np.ndarray, h_crit: float = 0.0) -> np.ndarray:
    """Time-mean depth to the first layer from the top with head ≥ h_crit (cf. P.shallowest_wt_depth)."""
    ptd = p[:, ::-1]
    sat = ptd >= h_crit
    first = np.argmax(sat, axis=1)
    head = np.take_along_axis(ptd, first[:, None], axis=1)[:, 0]
    depth = np.maximum(CENTER_DEPTH[::-1][first] - head, 0.0)
    return np.where(sat.any(axis=1), depth, DZ.sum()).mean(axis=0)


# ---------------------------------------------------------------------------
# Q1: structure
# ---------------------------------------------------------------------------

def _group_masks(domain: str) -> dict[str, np.ndarray]:
    st = structure(domain)
    t, act = st["traits"], st["active"]
    return {
        "all": act,
        "class4": act & (t["swt_joint_class"] == KEY_CLASS),
        "perched_flag": act & (t["perched"] == 1),
        "barrier_7m": act & (st["barrier_depth"] == 7.0),
        "barrier_2m": act & (st["barrier_depth"] == 2.0),
        "streams": act & (t["streams"] == 1),
    }


def q1_structure() -> dict:
    out = {}
    for d in DOMAINS:
        st = structure(d)
        act = st["active"]
        pb = pressure_stack(d, "BASE", BASE_YEARS)
        ls = lens_state(pb, st)
        leak = face_flux_down(pb, st, st["fb_layer"], st["fb_value"]) * H_YR * 1000.0  # mm/yr
        leak_nofb = face_flux_down(pb, st, st["fb_layer"], 1.0) * H_YR * 1000.0
        into_lens = face_flux_down(pb, st, st["lens_layer"], 1.0) * H_YR * 1000.0
        k_face_barrier = st["fb_value"] * (DZ[st["fb_layer"]] + DZ[st["lens_layer"]]) / (
            DZ[st["fb_layer"]] / _take(st["kz"], st["fb_layer"]) + DZ[st["lens_layer"]] / _take(st["kz"], st["lens_layer"]))
        kz_ratio = _take(st["kz"], st["lens_layer"]) / _take(st["kz"], st["fb_layer"])
        per_cell = {
            "lens_frac_base": ls["present"].mean(0),
            "perched_frac_base": ls["perched"].mean(0),
            "head_base": ls["head"].mean(0),
            "leak_mm": leak.mean(0),
            "leak_nofb_mm": leak_nofb.mean(0),
            "into_lens_mm": into_lens.mean(0),
            "k_barrier_mm": k_face_barrier * H_YR * 1000.0,
            "kz_ratio_lens_below": kz_ratio,
        }
        per_cell = {k: np.where(act, v, np.nan) for k, v in per_cell.items()}
        t = st["traits"]
        res = {"fb_value": st["fb_value"], "groups": {}}
        for g, m in _group_masks(d).items():
            if not m.any():
                continue
            u, c = np.unique(st["barrier_depth"][m], return_counts=True)
            res["groups"][g] = {
                "n": int(m.sum()),
                "barrier_depth_counts": {f"{k:g} m": int(v) for k, v in zip(u, c)},
                "lens_frac_base_mean": float(np.nanmean(per_cell["lens_frac_base"][m])),
                "perched_frac_base_mean": float(np.nanmean(per_cell["perched_frac_base"][m])),
                "head_on_barrier_median_m": float(np.nanmedian(per_cell["head_base"][m])),
                "barrier_leak_median_mm_yr": float(np.nanmedian(per_cell["leak_mm"][m])),
                "barrier_leak_mean_mm_yr": float(np.nanmean(per_cell["leak_mm"][m])),
                "leak_without_barrier_median_mm_yr": float(np.nanmedian(per_cell["leak_nofb_mm"][m])),
                "flux_into_lens_median_mm_yr": float(np.nanmedian(per_cell["into_lens_mm"][m])),
                "net_recharge_top2m_median_mm_yr": float(np.nanmedian(t["recharge_base_mm"][m])),
                "barrier_conductance_median_mm_yr": float(np.nanmedian(per_cell["k_barrier_mm"][m])),
                "kz_ratio_lens_over_below_median": float(np.nanmedian(per_cell["kz_ratio_lens_below"][m])),
                "regional_wtd_median_m": float(np.nanmedian(t["wtd_mean"][m])),
                "indicator_lens_layer": _counts(_take(st["ind"][None], st["lens_layer"])[0][m]),
                "indicator_below": _counts(_take(st["ind"][None], st["fb_layer"])[0][m]),
            }
        # Is a lens only ever found directly on the barrier?
        z5_lens = act & ((pb[:, 5] >= 0) & (pb[:, 4] < 0)).mean(0).__ge__(0.5)
        z6_lens = act & ((pb[:, 6] >= 0) & (pb[:, 5] < 0)).mean(0).__ge__(0.5)
        res["lens_on_barrier_check"] = {
            "z5_lens_cells": int(z5_lens.sum()),
            "z5_lens_with_barrier_at_7m": int((z5_lens & (st["barrier_depth"] == 7.0)).sum()),
            "z6_lens_cells": int(z6_lens.sum()),
            "z6_lens_with_barrier_at_2m": int((z6_lens & (st["barrier_depth"] == 2.0)).sum()),
        }
        # Physical perched definition vs the regional−shallowest > 5 m flag
        phys = act & (per_cell["perched_frac_base"] >= 0.5)
        flag = act & (t["perched"] == 1)
        res["perched_definition_agreement"] = {
            "physical_n": int(phys.sum()), "flag_n": int(flag.sum()),
            "both": int((phys & flag).sum()), "flag_only": int((flag & ~phys).sum()),
            "physical_only": int((phys & ~flag).sum()),
        }
        # Deep regional WT beneath the barrier is what makes the lens perched
        res["perched_by_regional_wtd"] = _binned_frac(t["wtd_mean"][act], per_cell["perched_frac_base"][act] >= 0.5,
                                                       [0, 1, 2, 5, 7, 10, 20, 50, 100, 1e4])
        res["_per_cell"] = per_cell
        res["_profiles"] = _profiles(d, pb)
        out[d] = res
    return out


def _counts(a: np.ndarray) -> dict[str, int]:
    u, c = np.unique(a, return_counts=True)
    return {str(int(k)): int(v) for k, v in zip(u, c)}


def _binned_frac(x, flag, edges):
    res = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (x >= lo) & (x < hi)
        res.append({"lo": lo, "hi": hi, "n": int(m.sum()), "frac": float(flag[m].mean()) if m.any() else None})
    return res


def _profiles(domain: str, pb: np.ndarray) -> dict:
    """Median baseline pressure head by layer for the key groups (z bottom→top)."""
    res = {}
    pm = pb.mean(0)
    for g, m in _group_masks(domain).items():
        if g in ("all",) or m.sum() < 5:
            continue
        res[g] = {"n": int(m.sum()), "p_median": np.nanmedian(pm[:, m], axis=1).tolist(),
                  "p_q25": np.nanpercentile(pm[:, m], 25, axis=1).tolist(),
                  "p_q75": np.nanpercentile(pm[:, m], 75, axis=1).tolist()}
    return res


# ---------------------------------------------------------------------------
# Q2 + Q4: lens through the 10-yr drought
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def ns_d10(domain: str) -> dict:
    return P.ns_persistence(domain, "d10")


def q2_drought() -> dict:
    out = {}
    for d in DOMAINS:
        st = structure(d)
        t, act = st["traits"], st["active"]
        base = lens_state(pressure_stack(d, "BASE", BASE_YEARS), st)
        dry = lens_state(pressure_stack(d, "10_year_drought", D10_DRY_LATE), st)
        end = lens_state(pressure(d, "10_year_drought", 49), st)
        rec = {k: lens_state(pressure(d, "10_year_drought", 49 + k), st) for k in (1, 2, 5)}
        rec_base = {k: lens_state(pressure(d, "BASE", 49 + k), st) for k in (1, 2, 5)}
        ns = ns_d10(d)
        cell = {
            "lens_frac_base": base["present"].mean(0),
            "lens_frac_dry": dry["present"].mean(0),
            "lens_frac_end_year": end["present"].mean(0),
            "head_base": base["head"].mean(0),
            "head_dry": dry["head"].mean(0),
            "head_end": end["head"][-1],
            **{f"head_rec{k}": rec[k]["head"][-1] for k in (1, 2, 5)},
            **{f"head_base_rec{k}": rec_base[k]["head"][-1] for k in (1, 2, 5)},
        }
        had = cell["lens_frac_base"] >= 0.5
        cell["had_lens"] = had.astype(float)
        cell["lens_lost"] = (had & (cell["lens_frac_dry"] < 0.5)).astype(float)
        cell["lens_frac_drop"] = cell["lens_frac_base"] - cell["lens_frac_dry"]
        cell["head_drop"] = cell["head_base"] - cell["head_dry"]
        cell["head_drop_frac"] = np.where(cell["head_base"] > 0.1, cell["head_drop"] / np.maximum(cell["head_base"], 0.1), np.nan)
        # fraction of the end-of-drought head deficit still missing after recovery year k
        d_end = cell["head_base"] - cell["head_end"]
        for k in (1, 2, 5):
            cell[f"head_left_rec{k}"] = np.where(
                d_end > 0.1, (cell[f"head_base_rec{k}"] - cell[f"head_rec{k}"]) / np.maximum(d_end, 0.1), np.nan)
        cell["et_flip"] = (t["et_class"] == 1).astype(float)
        cell["sat_rz_drop"] = t["sat_rz_gs_base"] - t["sat_rz_gs_drought"]
        cell["R2"] = ns["R2"]
        cell["ns_end"] = np.maximum(ns["ns_end"], 0)
        cell["ns_rec2"] = np.maximum(ns["ns_rec2"], 0)
        cell = {k: np.where(act, np.asarray(v, dtype=float), np.nan) for k, v in cell.items()}

        m = act & (t["streams"] != 1) & (cell["ns_end"] > 0.01)
        res = {"n_eval": int(m.sum())}
        preds = {
            "lens_lost": cell["lens_lost"], "lens_frac_drop": cell["lens_frac_drop"],
            "head_drop": cell["head_drop"], "head_drop_frac": cell["head_drop_frac"],
            "head_left_rec2": cell["head_left_rec2"],
            "et_flip": cell["et_flip"], "sat_rz_drop": cell["sat_rz_drop"],
            "sat_rz_gs_base": t["sat_rz_gs_base"],
            "swt_drop": t["swt_drought_mean"] - t["swt_mean"], "log_q": t["log_q"],
        }
        res["skill_R2"] = {k: P._skill(np.where(m, v, np.nan), cell["R2"], mass=cell["ns_end"])
                           for k, v in preds.items()}
        res["partial_rho"] = {
            "R2_vs_head_drop_given_et_class": P._partial_spearman(np.where(m, cell["head_drop"], np.nan), cell["R2"], t["et_class"]),
            "R2_vs_sat_rz_drop_given_lens_lost": P._partial_spearman(np.where(m, cell["sat_rz_drop"], np.nan), cell["R2"], cell["lens_lost"]),
            "R2_vs_head_drop_given_swt_joint": P._partial_spearman(np.where(m, cell["head_drop"], np.nan), cell["R2"], t["swt_joint_class"]),
            "R2_vs_sat_rz_drop_given_head_drop_tercile": P._partial_spearman(
                np.where(m, cell["sat_rz_drop"], np.nan), cell["R2"], _terciles(np.where(m, cell["head_drop"], np.nan))),
        }
        # 2×2: lens lost × ET flip
        tot_end = np.nansum(cell["ns_end"][act])
        tot_r2 = np.nansum(cell["ns_rec2"][act])
        tab = {}
        for ll in (0, 1):
            for ef in (0, 1):
                c = act & (cell["lens_lost"] == ll) & (cell["et_flip"] == ef)
                tab[f"lens_lost={ll},et_flip={ef}"] = _mass_row(c, cell, tot_end, tot_r2, act)
        res["lens_x_et_table"] = tab
        res["class4"] = _mass_row(act & (t["swt_joint_class"] == KEY_CLASS), cell, tot_end, tot_r2, act)
        c4 = act & (t["swt_joint_class"] == KEY_CLASS)
        res["class4"].update({
            "had_lens_frac": float(np.nanmean(cell["had_lens"][c4])),
            "lens_lost_frac_of_had": float(np.nanmean(cell["lens_lost"][c4 & (cell["had_lens"] == 1)])) if (c4 & (cell["had_lens"] == 1)).any() else None,
            "lens_frac_base_mean": float(np.nanmean(cell["lens_frac_base"][c4])),
            "lens_frac_dry_mean": float(np.nanmean(cell["lens_frac_dry"][c4])),
            "head_base_median": float(np.nanmedian(cell["head_base"][c4])),
            "head_dry_median": float(np.nanmedian(cell["head_dry"][c4])),
            "head_left_rec1_median": float(np.nanmedian(cell["head_left_rec1"][c4])),
            "head_left_rec2_median": float(np.nanmedian(cell["head_left_rec2"][c4])),
            "head_left_rec5_median": float(np.nanmedian(cell["head_left_rec5"][c4])),
        })
        # lost-lens cells split by class 4 membership
        lost = act & (cell["lens_lost"] == 1)
        res["lens_lost_cells"] = {
            "n": int(lost.sum()),
            "in_class4": int((lost & c4).sum()),
            "in_et_threshold": int((lost & (cell["et_flip"] == 1)).sum()),
            **_mass_row(lost, cell, tot_end, tot_r2, act),
        }
        # Does the lens hold up the root zone? Lens water table = barrier depth − head on barrier.
        ph = act & (cell["had_lens"] == 1) & (t["perched"] == 1) & (t["streams"] != 1)
        wt_b = st["barrier_depth"] - cell["head_base"]
        wt_d = st["barrier_depth"] - cell["head_dry"]
        res["lens_rootzone_coupling"] = {
            "n_perched_lens_cells": int(ph.sum()),
            "rho_lens_wt_vs_sat_rz_base": _rho(wt_b[ph], t["sat_rz_gs_base"][ph]),
            "rho_head_drop_vs_sat_rz_drop": _rho(cell["head_drop"][ph], cell["sat_rz_drop"][ph]),
            "sat_rz_base_by_lens_wt": _binned_mean(wt_b[ph], t["sat_rz_gs_base"][ph], [0, 1, 1.5, 2, 2.5, 3, 4, 7]),
            "class4_lens_wt_base_median": float(np.nanmedian(wt_b[c4])),
            "class4_lens_wt_dry_median": float(np.nanmedian(wt_d[c4])),
        }
        res["_per_cell"] = cell
        res["_series"] = _series(d, st, cell)
        out[d] = res
    return out


def _rho(x, y):
    ok = np.isfinite(x) & np.isfinite(y)
    return float(spearmanr(x[ok], y[ok])[0]) if ok.sum() > 10 else None


def _binned_mean(x, y, edges):
    res = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (x >= lo) & (x < hi) & np.isfinite(y)
        res.append({"lo": lo, "hi": hi, "n": int(m.sum()), "mean": float(np.mean(y[m])) if m.any() else None})
    return res


def _terciles(x):
    q = np.nanpercentile(x, [33.3, 66.7])
    g = np.where(x < q[0], 0, np.where(x < q[1], 1, 2)).astype(float)
    g[~np.isfinite(x)] = np.nan
    return g


def _mass_row(c, cell, tot_end, tot_r2, act):
    return {
        "n": int(c.sum()),
        "area_frac": float(c.sum() / act.sum()),
        "ns_end_share": float(np.nansum(cell["ns_end"][c]) / tot_end) if tot_end else None,
        "ns_rec2_share": float(np.nansum(cell["ns_rec2"][c]) / tot_r2) if tot_r2 else None,
        "R2_mass": float(np.nansum(cell["ns_rec2"][c]) / max(np.nansum(cell["ns_end"][c]), 1e-12)) if c.any() else None,
    }


def _series(domain: str, st: dict, cell: dict) -> dict:
    """Per-window group means through years 40–54 (drought + 5 recovery years)."""
    act = st["active"]
    t = st["traits"]
    groups = {"class4": act & (t["swt_joint_class"] == KEY_CLASS),
              "lens_lost": act & (cell["lens_lost"] == 1),
              "lens_kept": act & (cell["had_lens"] == 1) & (cell["lens_lost"] == 0)}
    res = {"t_years": (np.arange(len(D10_YEARS) * X.STEPS) + 1) / X.STEPS}
    for g, m in groups.items():
        if m.sum() < 3:
            continue
        pres, head, hb, nsd, flipd = [], [], [], [], []
        for y in D10_YEARS:
            lm = lens_state(pressure(domain, "10_year_drought", y), st)
            lb = lens_state(pressure(domain, "BASE", y), st)
            dm = P.year_ds(domain, "10_year_drought", y)
            db = P.year_ds(domain, "BASE", y)
            pres.append(lm["present"][:, m].mean(1))
            head.append(lm["head"][:, m].mean(1))
            hb.append(lb["head"][:, m].mean(1))
            nsd.append(np.nanmean((db["s_ns"].values - dm["s_ns"].values)[:, m], axis=1) * 1000.0)
            flipd.append(np.nanmean((db["sat_rz"].values - dm["sat_rz"].values)[:, m], axis=1))
        res[g] = {"n": int(m.sum()), "lens_present": np.concatenate(pres), "head": np.concatenate(head),
                  "head_base": np.concatenate(hb), "ns_deficit_mm": np.concatenate(nsd),
                  "sat_rz_deficit": np.concatenate(flipd)}
    return res


# ---------------------------------------------------------------------------
# Q3: definitional sensitivity
# ---------------------------------------------------------------------------

def q3_sensitivity() -> dict:
    out = {}
    for d in DOMAINS:
        st = structure(d)
        t, act = st["traits"], st["active"]
        ns = ns_d10(d)
        cell = {"ns_end": np.where(act, np.maximum(ns["ns_end"], 0), np.nan),
                "ns_rec2": np.where(act, np.maximum(ns["ns_rec2"], 0), np.nan)}
        tot_end, tot_r2 = np.nansum(cell["ns_end"]), np.nansum(cell["ns_rec2"])
        thr = t["et_class"] == 1
        res = {"swt_edges": [], "perched_threshold": [], "h_crit": [], "et_proxy": []}
        for lo in (0.5, 1.0, 1.5):
            for hi in (3.0, 5.0, 7.0, 10.0):
                c = act & (t["swt_mean"] >= lo) & (t["swt_mean"] < hi) & thr
                res["swt_edges"].append({"lo": lo, "hi": hi, **_mass_row(c, cell, tot_end, tot_r2, act),
                                         "perched_frac": float(np.nanmean(t["perched"][c])) if c.any() else None})
        c4 = act & (t["swt_joint_class"] == KEY_CLASS)
        gap = t["wtd_mean"] - t["swt_mean"]
        for pt in (1.0, 2.0, 5.0, 10.0, 20.0, 50.0):
            pm = act & (gap > pt)
            res["perched_threshold"].append({
                "threshold_m": pt,
                "domain_perched_frac": float(pm.sum() / act.sum()),
                "class4_perched_frac": float(np.mean(pm[c4])) if c4.any() else None,
                "perched": _mass_row(pm, cell, tot_end, tot_r2, act),
                "perched_and_et_threshold": _mass_row(pm & thr, cell, tot_end, tot_r2, act),
            })
        pb = pressure_stack(d, "BASE", BASE_YEARS)
        for hc in (-0.5, -0.25, 0.0, 0.25, 0.5):
            swt = shallowest_wt(pb, hc)
            c = act & (swt >= 1.0) & (swt < 5.0) & thr
            res["h_crit"].append({"h_crit_m": hc, "swt_median_class": float(np.nanmedian(swt[c])) if c.any() else None,
                                  "jaccard_vs_class4": float((c & c4).sum() / max((c | c4).sum(), 1)),
                                  **_mass_row(c, cell, tot_end, tot_r2, act)})
        # baseline-only ET proxy instead of the drought-defined threshold class
        for cut in (0.85, 0.90, 0.95):
            c = act & (t["swt_class"] == 1) & (t["sat_rz_gs_base"] < cut)
            res["et_proxy"].append({"sat_rz_gs_base_below": cut, **_mass_row(c, cell, tot_end, tot_r2, act),
                                    "jaccard_vs_class4": float((c & c4).sum() / max((c | c4).sum(), 1))})
        # structural definition: physically perched on the barrier (no WT threshold at all)
        ls = lens_state(pb, st)
        phys = act & (ls["perched"].mean(0) >= 0.5)
        res["structural"] = {
            "perched_on_barrier": _mass_row(phys, cell, tot_end, tot_r2, act),
            "perched_on_barrier_and_et_threshold": _mass_row(phys & thr, cell, tot_end, tot_r2, act),
            "perched_on_barrier_and_low_overland": _mass_row(
                phys & (t["log_q"] < np.nanpercentile(t["log_q"][act], 33.3)), cell, tot_end, tot_r2, act),
        }
        out[d] = res
    return out


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def _map_ax(ax, z, st, **kw):
    zz, _ = R._prepare_map(z, st["traits"]["streams"] == 1, st["active"])
    im = ax.imshow(zz, interpolation="nearest", **kw)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    return im


def fig_structure(q1: dict) -> Path:
    """Maps of barrier depth, baseline perched-lens frequency, barrier leakage; head profiles."""
    fig = plt.figure(figsize=(16.5, 8.4), constrained_layout=True)
    gs = fig.add_gridspec(2, 4, width_ratios=[1, 1, 1, 1.05])
    cm_bar = ListedColormap(["#56B4E9", "#542788"])
    ims = {}
    map_axes = {0: [], 1: [], 2: []}
    for r, d in enumerate(DOMAINS):
        st = structure(d)
        pc = q1[d]["_per_cell"]
        c4 = (st["traits"]["swt_joint_class"] == KEY_CLASS).astype(float)
        panels = [
            (np.where(st["active"], (st["barrier_depth"] == 7.0).astype(float), np.nan),
             "Flow-barrier depth", dict(cmap=cm_bar, norm=BoundaryNorm([-0.5, 0.5, 1.5], 2))),
            (pc["perched_frac_base"], "Baseline time with a perched lens\n(fraction of 219 h windows)",
             dict(cmap="Blues", vmin=0, vmax=1)),
            (pc["leak_mm"], "Baseline flux through barrier\n(mm/yr, + downward)",
             dict(cmap="PuOr_r", norm=SymLogNorm(linthresh=1.0, vmin=-300, vmax=300, base=10))),
        ]
        for c, (z, title, kw) in enumerate(panels):
            ax = fig.add_subplot(gs[r, c])
            map_axes[c].append(ax)
            ims[c] = _map_ax(ax, z, st, **kw)
            if c == 1:
                zc, _ = R._prepare_map(c4, st["traits"]["streams"] == 1, st["active"])
                ax.contour(np.nan_to_num(zc), levels=[0.5], colors="#D55E00", linewidths=0.8)
            if r == 0:
                ax.set_title(title, fontsize=LABEL_FS)
            if c == 0:
                ax.text(-0.04, 0.5, LABEL[d], transform=ax.transAxes, rotation=90, va="center", ha="right",
                        fontsize=TITLE_FS)
        axp = fig.add_subplot(gs[r, 3])
        depth = CENTER_DEPTH
        for g, col, lab in (("class4", "#D55E00", "WT 1–5 m · threshold"),
                            ("barrier_7m", "#542788", "all cells, barrier at 7 m"),
                            ("barrier_2m", "#56B4E9", "all cells, barrier at 2 m")):
            pr = q1[d]["_profiles"].get(g)
            if pr is None:
                continue
            axp.plot(pr["p_median"], depth, color=col, marker="o", ms=4, lw=1.8, label=f"{lab} (n={pr['n']})")
            axp.fill_betweenx(depth, pr["p_q25"], pr["p_q75"], color=col, alpha=0.15, lw=0)
        axp.axvline(0, color="0.3", lw=0.8)
        for bd in (2.0, 7.0):
            axp.axhline(bd, color="0.5", ls="--", lw=0.9)
        axp.set_yscale("log")
        axp.set_ylim(300, 0.04)
        axp.set_xlim(-6, 30)
        axp.set_ylabel("Depth (m)", fontsize=LABEL_FS)
        axp.grid(True, alpha=0.28)
        axp.legend(fontsize=LEGEND_FS - 2, loc="upper right", frameon=False)
        if r == 0:
            axp.set_title("Baseline pressure head by layer\n(median, IQR shaded)", fontsize=LABEL_FS)
        else:
            axp.set_xlabel("Pressure head (m)", fontsize=LABEL_FS)
        axp.text(-5.5, 2.0, "2 m face", ha="left", va="bottom", fontsize=9, color="0.4")
        axp.text(-5.5, 7.0, "7 m face", ha="left", va="bottom", fontsize=9, color="0.4")
    fig.legend(handles=[Line2D([0], [0], color="#D55E00", lw=1.2, label="WT 1–5 m · threshold cells (outlined)")],
               loc="outside upper center", ncol=1, fontsize=LEGEND_FS, frameon=False)
    cb0 = fig.colorbar(ims[0], ax=map_axes[0], shrink=0.6, location="bottom", pad=0.02, ticks=[0, 1])
    cb0.ax.set_xticklabels(["2 m", "7 m"])
    fig.colorbar(ims[1], ax=map_axes[1], shrink=0.6, location="bottom", pad=0.02)
    fig.colorbar(ims[2], ax=map_axes[2], shrink=0.6, location="bottom", pad=0.02,
                 ticks=[-100, -10, -1, 0, 1, 10, 100], format="%g")
    R.despine_axes(fig)
    out = FIG_DIR / "psa_lens_structure.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


def fig_drought(q2: dict) -> Path:
    """Lens through the drought (class 4) and the lens × ET-flip persistence table."""
    fig, axes = plt.subplots(3, 2, figsize=(12.5, 10.5), constrained_layout=True,
                             gridspec_kw={"height_ratios": [1, 1, 1.05]})
    groups = (("class4", "#D55E00", "WT 1–5 m · threshold"), ("lens_lost", "#542788", "lens lost in drought"),
              ("lens_kept", "#56B4E9", "lens kept"))
    for c, d in enumerate(DOMAINS):
        s = q2[d]["_series"]
        tt = s["t_years"]
        for r in (0, 1):
            ax = axes[r, c]
            ax.axvspan(0, 10, color=R.PERIOD_DROUGHT_FACE, alpha=R.PERIOD_DROUGHT_ALPHA, lw=0)
            ax.axvspan(10, 15, color=R.PERIOD_RECOVERY_FACE, alpha=R.PERIOD_RECOVERY_ALPHA, lw=0)
            ax.set_xlim(0, 15)
            ax.xaxis.set_major_locator(MultipleLocator(1))
            ax.grid(True, alpha=0.28)
        for g, col, lab in groups:
            if g not in s:
                continue
            gg = s[g]
            axes[0, c].plot(tt, gg["head_base"] - gg["head"], color=col, lw=1.6, label=f"{lab} (n={gg['n']})")
            axes[1, c].plot(tt, gg["ns_deficit_mm"], color=col, lw=1.6)
        axes[0, c].set_title(LABEL[d], fontsize=TITLE_FS)
        axes[0, c].axhline(0, color="0.3", lw=0.8)
        axes[1, c].axhline(0, color="0.3", lw=0.8)
        axes[0, c].legend(fontsize=LEGEND_FS - 2, frameon=False, loc="upper left")
        # 2×2 table as bars
        ax = axes[2, c]
        tab = q2[d]["lens_x_et_table"]
        keys = ["lens_lost=0,et_flip=0", "lens_lost=0,et_flip=1", "lens_lost=1,et_flip=0", "lens_lost=1,et_flip=1"]
        labs = ["neither", "ET flip\nonly", "lens lost\nonly", "both"]
        x = np.arange(4)
        w = 0.27
        for i, (met, col, lab) in enumerate((("area_frac", "0.7", "area"), ("ns_end_share", "#E69F00", "end-of-drought NS deficit"),
                                             ("ns_rec2_share", "#7B3294", "NS deficit left after rec. yr 2"))):
            ax.bar(x + (i - 1) * w, [tab[k][met] or 0 for k in keys], width=w, color=col, label=lab)
        for xi, k in zip(x, keys):
            r2 = tab[k]["R2_mass"]
            if r2 is not None and tab[k]["n"]:
                ax.text(xi, 1.02, f"R₂={r2:.2f}\nn={tab[k]['n']}", ha="center", va="bottom", fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels(labs, fontsize=10)
        ax.set_ylim(0, 1.25)
        ax.grid(True, axis="y", alpha=0.28)
    axes[0, 0].set_ylabel("Drop in head on barrier\nvs baseline (m)", fontsize=LABEL_FS)
    axes[1, 0].set_ylabel("Near-surface deficit (mm)", fontsize=LABEL_FS)
    axes[2, 0].set_ylabel("Share of domain total", fontsize=LABEL_FS)
    axes[1, 0].set_xlabel("Years since drought onset", fontsize=LABEL_FS)
    axes[1, 1].set_xlabel("Years since drought onset", fontsize=LABEL_FS)
    axes[2, 0].sharey(axes[2, 1])
    h, l = axes[2, 0].get_legend_handles_labels()
    h += [Patch(facecolor=R.PERIOD_DROUGHT_FACE, alpha=0.4, label="drought"),
          Patch(facecolor=R.PERIOD_RECOVERY_FACE, alpha=0.5, label="recovery")]
    fig.legend(handles=h, loc="outside upper center", ncol=5, fontsize=LEGEND_FS, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_lens_drought.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


def fig_sensitivity(q3: dict) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.6), constrained_layout=True, sharey=True)
    ls_lo = {0.5: ":", 1.0: "-", 1.5: "--"}
    for d in DOMAINS:
        col = DOMAIN_COLORS[d]
        rows = q3[d]["swt_edges"]
        for lo, ls in ls_lo.items():
            rr = [r for r in rows if r["lo"] == lo]
            axes[0].plot([r["hi"] for r in rr], [r["ns_rec2_share"] for r in rr], color=col, ls=ls, marker="o", ms=4)
        rr = q3[d]["perched_threshold"]
        axes[1].plot([r["threshold_m"] for r in rr], [r["perched_and_et_threshold"]["ns_rec2_share"] for r in rr],
                     color=col, marker="o", ms=4)
        axes[1].plot([r["threshold_m"] for r in rr], [r["perched"]["ns_rec2_share"] for r in rr],
                     color=col, marker="s", ms=4, ls="--", mfc="white")
        rr = q3[d]["h_crit"]
        axes[2].plot([r["h_crit_m"] for r in rr], [r["ns_rec2_share"] for r in rr], color=col, marker="o", ms=4)
    axes[0].set_xlabel("Upper edge of intermediate shallowest-WT class (m)", fontsize=LABEL_FS)
    axes[1].set_xlabel("Perched threshold: regional − shallowest WT (m)", fontsize=LABEL_FS)
    axes[1].set_xscale("log")
    axes[2].set_xlabel("Pressure-head criterion for the water table (m)", fontsize=LABEL_FS)
    axes[0].set_ylabel("Share of NS deficit left\nafter recovery yr 2", fontsize=LABEL_FS)
    for ax in axes:
        ax.grid(True, alpha=0.28)
        ax.set_ylim(0, 1)
    axes[0].axvline(5, color="0.6", ls=":", lw=1)
    axes[1].axvline(5, color="0.6", ls=":", lw=1)
    axes[2].axvline(0, color="0.6", ls=":", lw=1)
    handles = [Line2D([0], [0], color=DOMAIN_COLORS[d], lw=2, label=LABEL[d]) for d in DOMAINS]
    handles += [Line2D([0], [0], color="0.4", ls=ls, label=f"lower edge {lo:g} m") for lo, ls in ls_lo.items()]
    handles += [Line2D([0], [0], color="0.4", marker="o", label="perched × threshold ET"),
                Line2D([0], [0], color="0.4", marker="s", ls="--", mfc="white", label="all perched")]
    fig.legend(handles=handles, loc="outside upper center", ncol=7, fontsize=LEGEND_FS - 1, frameon=False)
    R.despine_axes(fig)
    out = FIG_DIR / "psa_lens_sensitivity.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    return out


# ---------------------------------------------------------------------------

def _strip(res: dict) -> dict:
    return {d: {k: v for k, v in r.items() if not k.startswith("_")} for d, r in res.items()}


def main():
    np.seterr(divide="ignore", invalid="ignore", over="ignore")  # inactive cells have kz = 0
    q1 = q1_structure()
    q2 = q2_drought()
    q3 = q3_sensitivity()
    summary = {"q1_structure": _strip(q1), "q2_drought": _strip(q2), "q3_sensitivity": q3,
               "profiles": {d: q1[d]["_profiles"] for d in DOMAINS},
               "layer_top_face_depth_m": TOP_FACE_DEPTH.tolist()}
    LENS_JSON.write_text(json.dumps(P._jsonable(summary), indent=1))
    print("wrote", LENS_JSON)
    fig_structure(q1)
    fig_drought(q2)
    fig_sensitivity(q3)
    return q1, q2, q3


if __name__ == "__main__":
    main()
