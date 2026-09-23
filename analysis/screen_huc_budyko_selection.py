#!/usr/bin/env python3
"""Broader (not fully national) HUC8 screen for Budyko Track A/B selection.

Scope: eastern US headwaters (HUC2 01–08) + Interior plains/mountain sources
(HUC2 10–11) + western headwaters (HUC2 12–18). Disk-safe: tiny CSVs only; no get_domain.

Method (matches pumping-rate-context Jul 2026 recipe):
  - CONUS2 baseline monthly streamflow WY2003 mean at USGS gage cells
  - vs USGS mean Q 1990–2019; RSR on log10 Q across gages in the HUC
  - WTD: CONUS2 baseline monthly mean WY2003 water_table_depth on HUC mask
    (ss_water_table_depth not in catalog; documented as proxy)
  - φ: CW3E monthly precip sum + Hamon PET from monthly air_temp (WY2003)
"""
from __future__ import annotations

import csv
import json
import sys
import time
import types
from pathlib import Path

# Broken scipy.sparse.linalg._propack in this env breaks xarray/rioxarray imports.
class _Pack:
    def __getattr__(self, name):
        def _f(*a, **k):
            raise RuntimeError(f"propack stub: {name}")

        return _f


_propack = types.ModuleType("scipy.sparse.linalg._propack")
for _n in ("_spropack", "_dpropack", "_cpropack", "_zpropack"):
    setattr(_propack, _n, _Pack())
sys.modules["scipy.sparse.linalg._propack"] = _propack

import numpy as np
import requests
import hf_hydrodata as hf
import subsettools as st

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
OUT = ROOT / "analysis"
CACHE = OUT / ".tmp_huc_screen"
CACHE.mkdir(parents=True, exist_ok=True)

# Broader screen candidate pool (headwater-leaning names; corridors filtered later)
CANDIDATES: dict[str, str] = {
    # --- Eastern / Appalachian / Coastal (Track A priority) ---
    "01080101": "Upper Androscoggin",
    "01080201": "Black-Ottauquechee",
    "01090001": "Upper Connecticut",
    "02020003": "Middle Hudson",  # expect corridor reject via drain
    "02040101": "Upper Delaware",
    "02040103": "Lackawaxen",
    "02050101": "Upper Susquehanna",
    "02050102": "Chenango",
    "02050201": "Upper West Branch Susquehanna",
    "02050202": "Sinnemahoning",
    "02070001": "South Branch Potomac",
    "02070002": "North Branch Potomac",
    "02070003": "Cacapon-Town",
    "02070004": "South Fork Shenandoah",
    "02070005": "North Fork Shenandoah",
    "02070008": "Middle Potomac-Catoctin",  # corridor
    "02060003": "Gunpowder-Patapsco",
    "02060006": "Patuxent",
    "02080109": "Nanticoke",
    "02080111": "Pocomoke-W Lower Delmarva",
    "03010101": "Upper Roanoke",
    "03010103": "Middle Roanoke",
    "03020101": "Upper Neuse",
    "03030003": "Upper Cape Fear",
    "03050101": "Seneca (Savannah headwaters)",
    "03060103": "Upper Oconee",
    "03130001": "Upper Chattahoochee",
    "03150101": "Conasauga",
    "04100003": "St Joseph (Maumee)",
    "04120101": "Niagara",  # corridor risk
    "04140201": "Upper St Lawrence",
    "05010001": "Allegheny Headwaters",
    "05010003": "Middle Allegheny-Tionesta",
    "05020001": "Tygart Valley",
    "05020004": "Cheat",
    "05050001": "Upper New",
    "05050002": "Middle New",
    "05060001": "Gauley",
    "05070201": "Upper Great Miami",
    "05080001": "Upper Wabash",
    "05120101": "Tippecanoe",
    "05130101": "Upper Cumberland",
    "05130105": "South Fork Cumberland",
    "06010102": "South Fork Holston",
    "06010104": "Watauga",
    "06020001": "Upper Clinch",
    "06020002": "Powell",
    "06030001": "Hiwassee",
    "07010101": "Mississippi Headwaters",
    "07010104": "Leech Lake",
    "07020001": "Minnesota Headwaters",
    "07030005": "Upper Chippewa",
    "07070001": "Turkey",
    "07120001": "Kankakee",
    "08010210": "Wolf",
    "08020203": "Yalobusha",
    "08030201": "Upper Hatchie",
    # --- Interior plains / mountain sources (Track B priority) ---
    "10020001": "Red Rock (Missouri headwaters)",
    "10020004": "Madison",
    "10030101": "Yellowstone Headwaters",
    "10180001": "North Platte Headwaters",
    "10190001": "South Platte Headwaters",
    "10250001": "Arikaree",
    "10250002": "North Fork Republican",
    "10250003": "South Fork Republican",
    "10250005": "Frenchman",
    "10260004": "Upper Niobrara",
    "11020001": "Arkansas Headwaters",
    "11020002": "Upper Arkansas",
    "11030001": "Middle Arkansas",
    "11040002": "Upper Cimarron",
    "11120101": "Middle Canadian",
    "13010001": "Rio Grande Headwaters",
    "14010001": "Colorado Headwaters",
    "14020001": "Blue River",
    "14050001": "Upper Green",
    "16010101": "Upper Bear",
    "17040201": "Snake Headwaters",
    "17040202": "Gros Ventre",
    # --- Western US headwaters (Track B priority; Track A where intermediate WTD) ---
    # HUC2 12 — Texas-Gulf
    "12030106": "Upper Guadalupe",
    "12040101": "Upper Colorado (TX)",
    "12050101": "Upper Brazos",
    "12050201": "Double Mountain Fork Brazos",
    "12070102": "Upper Nueces",
    "12090301": "Upper Trinity",
    "12100201": "Upper Sabine",
    # HUC2 13 — Rio Grande
    "13010101": "Upper Rio Grande-Elephant Butte",
    "13010201": "Red (NM headwaters)",
    "13020101": "Rio Chama",
    "13020201": "Upper Pecos",
    "13020202": "Hondo-Sacramento",
    "13030101": "Jemez",
    "13050101": "Mimbres",
    # HUC2 14 — Upper Colorado
    "14010002": "Gunnison Headwaters",
    "14010003": "Upper Colorado-Dolores",
    "14010005": "Upper San Juan",
    "14020003": "Upper White",
    "14020004": "Upper Yampa",
    "14050002": "Blacks Fork",
    "14060001": "Lower Green",
    # HUC2 15 — Lower Colorado
    "15010001": "Upper Colorado (LC region)",
    "15010002": "Paria",
    "15010003": "Upper Virgin",
    "15020001": "Lower Colorado-Little Colorado headwaters",
    "15030101": "Upper Gila",
    "15030201": "Upper Salt",
    "15030301": "Upper Verde",
    # HUC2 16 — Great Basin
    "16010201": "Upper Humboldt",
    "16030001": "Upper Carson",
    "16050101": "Walker",
    "16060102": "Owens Valley",
    "16060103": "Upper Owens",
    "16060107": "Upper Owens headwaters",
    # HUC2 17 — Pacific Northwest
    "17010101": "Upper Klamath",
    "17050101": "Upper John Day",
    "17060101": "Upper Deschutes",
    "17070101": "Upper Willamette",
    "17080101": "Upper Rogue",
    "17090101": "Upper Umpqua",
    # HUC2 18 — California
    "18010201": "Upper Sacramento",
    "18010202": "McCloud-Pit",
    "18020101": "Upper San Joaquin",
    "18020104": "Upper Merced",
    "18020107": "Upper Kings",
    "18020110": "Upper Kern",
    "18070101": "Upper Salinas",
}

HARD_REJECT = {
    "02070008": "corridor (mainstem Potomac)",
    "02070010": "corridor / metro Fall Line",
    "04120101": "corridor (Niagara / Great Lakes)",
    "02080109": "tidal Coastal Plain risk",
    "02080110": "tidal / Tangier",
    "02080108": "Hampton Roads tidal",
    "02080208": "Hampton Roads poor skill",
}

# Prefer Jul 2026 Mid-Atlantic RSR snapshot when present (same recipe; known cell map)
REF_RSR_CSV = ROOT / ".tmp_hydrodata" / "huc8_streamflow_rsr.csv"

WY_START, WY_END = "2002-10-01", "2003-09-01"  # monthly files through Aug in end exclusive quirks
OBS_START, OBS_END = "1990-01-01", "2019-12-31"


def _register():
    pin = json.loads((Path.home() / ".hydrodata" / "pin.json").read_text())
    hf.register_api_pin(pin["email"], str(pin["pin"]))


def _cache_json(path: Path, obj):
    path.write_text(json.dumps(obj))


def _load_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def usgs_sites(huc8: str) -> list[dict]:
    cp = CACHE / f"sites_{huc8}.json"
    cached = _load_json(cp)
    if cached is not None:
        return cached
    url = "https://waterservices.usgs.gov/nwis/site/"
    r = requests.get(
        url,
        params={
            "format": "rdb",
            "huc": huc8,
            "siteType": "ST",
            "siteOutput": "expanded",
            "hasDataTypeCd": "dv",
            "parameterCd": "00060",
            "siteStatus": "all",
        },
        timeout=120,
    )
    if r.status_code == 404:
        _cache_json(cp, [])
        return []
    r.raise_for_status()
    lines = [ln for ln in r.text.splitlines() if ln and not ln.startswith("#")]
    if len(lines) < 3:
        _cache_json(cp, [])
        return []
    header = lines[0].split("\t")
    rows = []
    for ln in lines[2:]:
        parts = ln.split("\t")
        if len(parts) < len(header):
            continue
        d = dict(zip(header, parts))
        rows.append(
            {
                "site_id": d.get("site_no"),
                "name": d.get("station_nm"),
                "lat": d.get("dec_lat_va"),
                "lon": d.get("dec_long_va"),
                "drain_mi2": d.get("drain_area_va"),
                "huc_cd": d.get("huc_cd"),
            }
        )
    _cache_json(cp, rows)
    time.sleep(0.15)
    return rows


def usgs_lt_mean_m3s(site_id: str) -> float:
    cp = CACHE / f"obs_lt_{site_id}.json"
    cached = _load_json(cp)
    if cached is not None:
        v = cached.get("mean_m3s")
        return float(v) if v is not None else float("nan")
    url = "https://waterservices.usgs.gov/nwis/dv/"
    try:
        r = requests.get(
            url,
            params={
                "format": "json",
                "sites": site_id,
                "startDT": OBS_START,
                "endDT": OBS_END,
                "parameterCd": "00060",
                "statCd": "00003",
            },
            timeout=180,
        )
        r.raise_for_status()
        ts = r.json()["value"]["timeSeries"]
        if not ts:
            _cache_json(cp, {"mean_m3s": None})
            return float("nan")
        vals = []
        for v in ts[0]["values"][0]["value"]:
            try:
                vals.append(float(v["value"]))
            except Exception:
                pass
        vals = np.asarray(vals, dtype=float)
        vals = vals[np.isfinite(vals) & (vals >= 0)]
        if vals.size < 30:
            _cache_json(cp, {"mean_m3s": None})
            return float("nan")
        mean = float(np.mean(vals) * 0.028316846592)  # cfs → m3/s
        _cache_json(cp, {"mean_m3s": mean})
        time.sleep(0.1)
        return mean
    except Exception:
        _cache_json(cp, {"mean_m3s": None})
        return float("nan")


def _as_float(x) -> float:
    try:
        if x is None:
            return float("nan")
        return float(x)
    except Exception:
        return float("nan")


def sim_mean_m3s(
    i: int,
    j: int,
    *,
    snap_radius: int = 4,
    drain_mi2: float | None = None,
) -> tuple[float, int, int]:
    """WY2003 monthly mean streamflow; snap using CONUS2 drainage_area when possible.

    Returns (q_m3s, i_snap, j_snap). Prefer the neighborhood cell whose modeled
    drainage area best matches the USGS gage drainage (km²). Fall back to nearest
    ``distance_stream_lin == 0`` cell, then nearest Q>0.05 cell.
    """
    drain_key = (
        f"{drain_mi2:.2f}" if drain_mi2 is not None and np.isfinite(drain_mi2) else "nodrain"
    )
    cp = CACHE / f"sim_da{snap_radius}_{i}_{j}_{drain_key}.json"
    cached = _load_json(cp)
    if cached is not None:
        q = cached.get("mean_m3s")
        return (
            float(q) if q is not None else float("nan"),
            int(cached.get("i_snap", i)),
            int(cached.get("j_snap", j)),
        )
    try:
        r = snap_radius
        gb = [i - r, j - r, i + r + 1, j + r + 1]
        data = np.asarray(
            hf.get_gridded_data(
                dict(
                    dataset="conus2_baseline",
                    variable="streamflow",
                    temporal_resolution="monthly",
                    aggregation="mean",
                    start_time="2002-10-01",
                    end_time="2003-10-01",
                    grid_bounds=gb,
                )
            ),
            dtype=float,
        )
        qm = np.nanmean(data, axis=0) if data.ndim == 3 else data
        qm = qm / 3600.0
        da = np.asarray(
            hf.get_gridded_data(
                dict(
                    dataset="conus2_domain",
                    variable="drainage_area",
                    grid="conus2",
                    grid_bounds=gb,
                )
            ),
            dtype=float,
        )
        while da.ndim > 2:
            da = da[0]
        try:
            dstream = np.asarray(
                hf.get_gridded_data(
                    dict(
                        dataset="conus2_domain",
                        variable="distance_stream_lin",
                        grid="conus2",
                        grid_bounds=gb,
                    )
                ),
                dtype=float,
            )
            while dstream.ndim > 2:
                dstream = dstream[0]
        except Exception:
            dstream = np.zeros_like(qm)

        if qm.shape != da.shape:
            ny = min(qm.shape[0], da.shape[0])
            nx = min(qm.shape[1], da.shape[1])
            qm, da, dstream = qm[:ny, :nx], da[:ny, :nx], dstream[:ny, :nx]

        cy, cx = min(r, qm.shape[0] - 1), min(r, qm.shape[1] - 1)
        yy, xx = cy, cx

        target_km2 = (
            float(drain_mi2) * 2.589988
            if drain_mi2 is not None and np.isfinite(drain_mi2) and drain_mi2 > 0
            else None
        )
        if target_km2 is not None:
            # Prefer stream cells (distance_stream_lin==0) with drainage near gage
            stream = np.isfinite(da) & np.isfinite(qm) & (dstream <= 0.5) & (da > 0)
            if not stream.any():
                stream = np.isfinite(da) & np.isfinite(qm) & (da > 0) & (qm > 1e-4)
            if stream.any():
                ys, xs = np.where(stream)
                err = np.abs(np.log10(np.clip(da[ys, xs], 1e-3, None)) - np.log10(target_km2))
                # mild distance penalty so we don't jump across the window
                dist = np.sqrt((ys - cy) ** 2 + (xs - cx) ** 2)
                score = err + 0.05 * dist
                pick = int(np.argmin(score))
                yy, xx = int(ys[pick]), int(xs[pick])
        else:
            stream = np.isfinite(qm) & (dstream <= 0.5) & (qm > 0.05)
            if not stream.any():
                stream = np.isfinite(qm) & (qm > 0.05)
            if stream.any():
                if stream[cy, cx]:
                    yy, xx = cy, cx
                else:
                    ys, xs = np.where(stream)
                    dist2 = (ys - cy) ** 2 + (xs - cx) ** 2
                    pick = int(np.argmin(dist2))
                    yy, xx = int(ys[pick]), int(xs[pick])

        if not np.isfinite(qm[yy, xx]):
            _cache_json(cp, {"mean_m3s": None, "i_snap": i, "j_snap": j})
            return float("nan"), i, j
        i_s, j_s = i - r + int(yy), j - r + int(xx)
        mean = float(qm[yy, xx])
        _cache_json(
            cp,
            {
                "mean_m3s": mean,
                "i_snap": i_s,
                "j_snap": j_s,
                "da_km2": float(da[yy, xx]) if np.isfinite(da[yy, xx]) else None,
                "target_km2": target_km2,
            },
        )
        return mean, i_s, j_s
    except Exception as e:
        _cache_json(cp, {"mean_m3s": None, "error": str(e)[:200], "i_snap": i, "j_snap": j})
        return float("nan"), i, j


def load_ref_rsr() -> dict[str, dict]:
    if not REF_RSR_CSV.exists():
        return {}
    out = {}
    with REF_RSR_CSV.open() as f:
        for r in csv.DictReader(f):
            try:
                out[r["huc8"]] = {
                    "rsr_lt": float(r["rsr_lt"]) if r.get("rsr_lt") not in ("", None) else float("nan"),
                    "n_lt": int(float(r["n_lt"])) if r.get("n_lt") not in ("", None) else 0,
                    "med_sim_over_obs_lt": float(r["med_sim_over_obs_lt"])
                    if r.get("med_sim_over_obs_lt") not in ("", None)
                    else float("nan"),
                    "source": "jul2026_midatlantic_csv",
                }
            except Exception:
                pass
    return out


def rsr_log10(sim: np.ndarray, obs: np.ndarray) -> float:
    s = np.log10(np.clip(sim, 1e-6, None))
    o = np.log10(np.clip(obs, 1e-6, None))
    if o.size < 2 or np.std(o) == 0:
        return float("nan")
    return float(np.sqrt(np.mean((s - o) ** 2)) / np.std(o, ddof=0))


def score_huc_rsr(huc8: str) -> dict:
    sites = usgs_sites(huc8)
    site_rows = []
    sims, obss = [], []
    max_drain = 0.0
    outlet = ""
    tidal = False
    for s in sites:
        try:
            drain = float(s["drain_mi2"]) if s.get("drain_mi2") not in (None, "") else float("nan")
        except Exception:
            drain = float("nan")
        if np.isfinite(drain) and drain > max_drain:
            max_drain = drain
            outlet = s["site_id"]
        nm = (s.get("name") or "").lower()
        if any(k in nm for k in ("tidal", "estuary", "bay at", "near mouth")):
            tidal = True
        try:
            lat = float(s["lat"])
            lon = float(s["lon"])
        except Exception:
            continue
        try:
            ij = hf.from_latlon("conus2", lat, lon)
            i0, j0 = int(round(ij[0])), int(round(ij[1]))
        except Exception:
            continue
        sim, i, j = sim_mean_m3s(
            i0, j0, snap_radius=4, drain_mi2=drain if np.isfinite(drain) else None
        )
        obs = _as_float(usgs_lt_mean_m3s(s["site_id"]))
        sim = _as_float(sim)
        row = {
            "huc8": huc8,
            "site_id": s["site_id"],
            "i0": i0,
            "j0": j0,
            "i": i,
            "j": j,
            "sim_m3s": sim if np.isfinite(sim) else "",
            "obs_lt": obs if np.isfinite(obs) else "",
            "drain": drain if np.isfinite(drain) else "",
        }
        site_rows.append(row)
        # Require positive flow on a snapped channel cell; skip tiny/empty snaps
        if (
            np.isfinite(sim)
            and np.isfinite(obs)
            and obs > 0
            and sim > 1e-3
            and (not np.isfinite(drain) or drain >= 1.0)
        ):
            sims.append(sim)
            obss.append(obs)
    sims_a = np.asarray(sims, dtype=float)
    obss_a = np.asarray(obss, dtype=float)
    rsr = rsr_log10(sims_a, obss_a) if sims_a.size else float("nan")
    med_ratio = (
        float(np.median(sims_a / obss_a)) if sims_a.size else float("nan")
    )
    return {
        "huc8": huc8,
        "n_gages": len(sites),
        "n_lt": int(sims_a.size),
        "rsr_lt": rsr,
        "med_sim_over_obs_lt": med_ratio,
        "max_drain_mi2": max_drain if max_drain > 0 else float("nan"),
        "outlet_gage": outlet,
        "tidal_hint": tidal,
        "site_rows": site_rows,
    }


def huc_wtd_phi(huc8: str) -> dict:
    cp = CACHE / f"wtd_phi_{huc8}.json"
    cached = _load_json(cp)
    if cached is not None:
        return cached
    out: dict = {"huc8": huc8}
    try:
        ij_bounds, mask = st.define_huc_domain(hucs=[huc8], grid="conus2")
        active = np.asarray(mask) > 0
        out["n_active"] = int(active.sum())
        out["ij_bounds"] = list(map(int, ij_bounds))
    except Exception as e:
        out["error"] = f"mask:{e}"
        _cache_json(cp, out)
        return out

    try:
        wtd = np.asarray(
            hf.get_gridded_data(
                dict(
                    dataset="conus2_baseline",
                    variable="water_table_depth",
                    temporal_resolution="monthly",
                    aggregation="mean",
                    start_time="2002-10-01",
                    end_time="2003-10-01",
                    huc_id=huc8,
                    grid="conus2",
                )
            ),
            dtype=float,
        )
        # time,y,x → mean over months
        if wtd.ndim == 3:
            wtd_m = np.nanmean(wtd, axis=0)
        else:
            wtd_m = wtd
        # align mask
        if wtd_m.shape != active.shape:
            # trim/pad to mask
            ny, nx = active.shape
            wtd_m = wtd_m[:ny, :nx]
        vals = wtd_m[active & np.isfinite(wtd_m)]
        if vals.size:
            out["wtd_p10"] = float(np.percentile(vals, 10))
            out["wtd_p50"] = float(np.percentile(vals, 50))
            out["wtd_p90"] = float(np.percentile(vals, 90))
            out["frac_wtd_2_20"] = float(np.mean((vals >= 2) & (vals <= 20)))
            out["frac_wtd_le2"] = float(np.mean(vals <= 2))
            out["frac_wtd_le5"] = float(np.mean(vals <= 5))
    except Exception as e:
        out["wtd_error"] = str(e)[:200]

    # φ from CW3E monthly
    try:
        precip = np.asarray(
            hf.get_gridded_data(
                dict(
                    dataset="CW3E",
                    variable="precipitation",
                    temporal_resolution="monthly",
                    aggregation="sum",
                    start_time="2002-10-01",
                    end_time="2003-10-01",
                    huc_id=huc8,
                    grid="conus2",
                )
            ),
            dtype=float,
        )
        temp = np.asarray(
            hf.get_gridded_data(
                dict(
                    dataset="CW3E",
                    variable="air_temp",
                    temporal_resolution="monthly",
                    aggregation="mean",
                    start_time="2002-10-01",
                    end_time="2003-10-01",
                    huc_id=huc8,
                    grid="conus2",
                )
            ),
            dtype=float,
        )
        # precip monthly sum mm; temp K
        if precip.ndim == 3:
            p_ann = np.nansum(precip, axis=0)
        else:
            p_ann = precip
        # Hamon monthly using mid-month DOY approx
        # months Oct..Sep → DOY midpoints
        mid_doy = np.array([288, 318, 349, 15, 46, 74, 105, 135, 166, 196, 227, 258], dtype=float)
        # rough centroid lat from ij bounds
        # CONUS2 lat approx: use 39 as fallback; better from hf
        try:
            # sample center
            i0, j0, i1, j1 = out["ij_bounds"]
            latlon = hf.gridded.to_latlon("conus2", (i0 + i1) / 2, (j0 + j1) / 2)
            lat_deg = float(latlon[0])
        except Exception:
            lat_deg = 39.0
        pet_acc = None
        t_arr = temp if temp.ndim == 3 else temp[None, ...]
        n_t = t_arr.shape[0]
        for ti in range(min(n_t, 12)):
            t_c = t_arr[ti] - 273.15
            doy = mid_doy[ti % 12]
            decl = 0.4093 * np.sin(2 * np.pi * (doy - 81) / 365.0)
            lat = np.deg2rad(lat_deg)
            cos_ha = float(np.clip(-np.tan(lat) * np.tan(decl), -1.0, 1.0))
            daylen = 24.0 * np.arccos(cos_ha) / np.pi
            # days in month approx
            dim = np.array([31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 31, 30])[ti % 12]
            es = 0.6108 * np.exp(17.27 * t_c / (t_c + 237.3))
            pet_day = 29.8 * daylen * es / (t_c + 273.2)
            pet_day = np.where(np.isfinite(pet_day), np.maximum(pet_day, 0.0), 0.0)
            pet_m = pet_day * dim
            pet_acc = pet_m if pet_acc is None else pet_acc + pet_m
        if p_ann.shape != active.shape:
            ny, nx = active.shape
            p_ann = p_ann[:ny, :nx]
            pet_acc = pet_acc[:ny, :nx]
        phi = np.where(active & (p_ann > 1), pet_acc / p_ann, np.nan)
        phi_v = phi[active & np.isfinite(phi)]
        p_v = p_ann[active]
        if phi_v.size:
            out["phi_mean"] = float(np.nanmean(phi_v))
            out["phi_p50"] = float(np.nanpercentile(phi_v, 50))
            out["P_mean_mm"] = float(np.nanmean(p_v))
            out["PET_mean_mm"] = float(np.nanmean(pet_acc[active]))
    except Exception as e:
        out["phi_error"] = str(e)[:200]

    # stream ribbon hint from streamflow field on mask
    try:
        q = np.asarray(
            hf.get_gridded_data(
                dict(
                    dataset="conus2_baseline",
                    variable="streamflow",
                    temporal_resolution="monthly",
                    aggregation="mean",
                    start_time="2002-10-01",
                    end_time="2003-10-01",
                    huc_id=huc8,
                    grid="conus2",
                )
            ),
            dtype=float,
        )
        if q.ndim == 3:
            q_m = np.nanmean(q, axis=0)
        else:
            q_m = q
        if q_m.shape != active.shape:
            ny, nx = active.shape
            q_m = q_m[:ny, :nx]
        flow = np.where(active, q_m, np.nan)
        thr = np.nanpercentile(flow, 97)
        streams = active & np.isfinite(flow) & (flow >= thr)
        if "wtd_p10" in out:
            wtd_m = np.asarray(
                hf.get_gridded_data(
                    dict(
                        dataset="conus2_baseline",
                        variable="water_table_depth",
                        temporal_resolution="monthly",
                        aggregation="mean",
                        start_time="2002-10-01",
                        end_time="2003-10-01",
                        huc_id=huc8,
                        grid="conus2",
                    )
                ),
                dtype=float,
            )
            if wtd_m.ndim == 3:
                wtd_m = np.nanmean(wtd_m, axis=0)
            if wtd_m.shape != active.shape:
                ny, nx = active.shape
                wtd_m = wtd_m[:ny, :nx]
            sv = wtd_m[streams & np.isfinite(wtd_m)]
            lo = np.nanpercentile(flow, 33)
            up = active & np.isfinite(flow) & (flow <= lo)
            uv = wtd_m[up & np.isfinite(wtd_m)]
            if sv.size:
                out["stream_wtd_p10"] = float(np.percentile(sv, 10))
                out["stream_wtd_p50"] = float(np.percentile(sv, 50))
            if uv.size and sv.size:
                out["upland_wtd_p50"] = float(np.percentile(uv, 50))
                out["corridor_contrast"] = float(out["upland_wtd_p50"] - out["stream_wtd_p50"])
    except Exception as e:
        out["ribbon_error"] = str(e)[:200]

    _cache_json(cp, out)
    return out


def label_track(row: dict) -> str:
    if row.get("hard_reject"):
        return "reject"
    if row.get("headwater") is False:
        return "reject"
    rsr = row.get("rsr_lt")
    if rsr is None or not np.isfinite(rsr) or rsr > 0.55:
        return "reject_rsr"
    p50 = row.get("wtd_p50")
    frac = row.get("frac_wtd_2_20")
    p10 = row.get("wtd_p10")
    p90 = row.get("wtd_p90")
    phi = row.get("phi_mean")
    contrast = row.get("corridor_contrast")
    if any(v is None or not np.isfinite(v) for v in (p50, frac, p10, p90, phi)):
        return "need_wtd_phi"
    A = (3 <= p50 <= 25) and (frac >= 0.30) and (p10 <= 2.5) and (p90 >= 15)
    A_soft = (2 <= p50 <= 35) and (frac >= 0.25) and (p10 <= 5) and (p90 >= 12)
    B = phi >= 1.2 and p10 <= 5
    ribbon = np.isfinite(contrast) and contrast >= 5 and p10 <= 5
    if A and B and ribbon:
        return "both"
    if A and B:
        return "both_weak_ribbon"
    if A:
        return "A"
    if A_soft:
        return "A_soft"
    if B and ribbon:
        return "B"
    if B:
        return "B_weak_ribbons"
    if phi < 0.75 and p50 < 3:
        return "neither_wolf_clone"
    if p50 > 30 and frac < 0.15:
        return "neither_deep_like_potomac"
    return "neither"


def main():
    _register()
    ref_rsr = load_ref_rsr()
    print(f"Screening {len(CANDIDATES)} HUC8s… (ref RSR HUCs={len(ref_rsr)})", flush=True)
    rsr_rows = []
    site_all = []
    for k, (huc, name) in enumerate(CANDIDATES.items(), 1):
        print(f"[{k}/{len(CANDIDATES)}] RSR {huc} {name}", flush=True)
        try:
            sc = score_huc_rsr(huc)
        except Exception as e:
            sc = {
                "huc8": huc,
                "n_gages": 0,
                "n_lt": 0,
                "rsr_lt": float("nan"),
                "med_sim_over_obs_lt": float("nan"),
                "max_drain_mi2": float("nan"),
                "outlet_gage": "",
                "tidal_hint": False,
                "site_rows": [],
                "error": str(e)[:200],
            }
        sc["name"] = name
        sc["rsr_source"] = "this_screen"
        # Prefer Jul 2026 Mid-Atlantic long-term RSR when available
        if huc in ref_rsr and np.isfinite(ref_rsr[huc]["rsr_lt"]):
            sc["rsr_lt_recomputed"] = sc.get("rsr_lt")
            sc["rsr_lt"] = ref_rsr[huc]["rsr_lt"]
            sc["n_lt"] = ref_rsr[huc]["n_lt"] or sc.get("n_lt")
            sc["med_sim_over_obs_lt"] = ref_rsr[huc]["med_sim_over_obs_lt"]
            sc["rsr_source"] = "jul2026_midatlantic_csv"
        site_all.extend(sc.pop("site_rows", []))
        rsr_rows.append(sc)
        # incremental save
        with (OUT / "huc8_headwater_streamflow_rsr.csv").open("w", newline="") as f:
            fields = [
                "huc8",
                "name",
                "n_gages",
                "rsr_lt",
                "n_lt",
                "med_sim_over_obs_lt",
                "max_drain_mi2",
                "outlet_gage",
                "tidal_hint",
                "rsr_source",
                "rsr_lt_recomputed",
                "error",
            ]
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rsr_rows)

    with (OUT / "huc8_headwater_streamflow_sites.csv").open("w", newline="") as f:
        fields = ["huc8", "site_id", "i", "j", "sim_m3s", "obs_lt", "drain"]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(site_all)

    # Annotate survivors
    annotated = []
    for sc in rsr_rows:
        huc = sc["huc8"]
        rsr = sc.get("rsr_lt", float("nan"))
        max_drain = sc.get("max_drain_mi2", float("nan"))
        reject = HARD_REJECT.get(huc, "")
        headwater = True
        if np.isfinite(max_drain) and max_drain >= 5000:
            headwater = False
            if not reject:
                reject = "likely corridor (max gage drain >=5000 mi2)"
        elif np.isfinite(max_drain) and max_drain >= 3000:
            headwater = "marginal"
        if sc.get("tidal_hint") and not reject:
            reject = "tidal name hint"
        row = {
            "huc8": huc,
            "name": sc.get("name"),
            "rsr_lt": rsr if np.isfinite(rsr) else "",
            "n_lt": sc.get("n_lt"),
            "n_gages": sc.get("n_gages"),
            "max_drain_mi2": max_drain if np.isfinite(max_drain) else "",
            "outlet_gage": sc.get("outlet_gage"),
            "headwater": headwater,
            "tidal_hint": sc.get("tidal_hint"),
            "hard_reject": reject,
            "region": (
                "eastern"
                if huc.startswith(("01", "02", "03", "04", "05", "06", "07", "08"))
                else "western"
                if huc.startswith(("12", "13", "14", "15", "16", "17", "18"))
                else "interior"
            ),
        }
        # WTD/φ only if skill-ish and not hard-rejected corridor
        want_metrics = (
            not reject
            and headwater is not False
            and np.isfinite(rsr)
            and rsr <= 0.70  # slightly loose to annotate near-misses
            and sc.get("n_lt", 0) >= 2
        ) or huc in ("02070001", "08010210", "10250003", "02060006")
        if want_metrics:
            print(f"  WTD/φ {huc}…", flush=True)
            m = huc_wtd_phi(huc)
            for k in (
                "n_active",
                "wtd_p10",
                "wtd_p50",
                "wtd_p90",
                "frac_wtd_2_20",
                "frac_wtd_le2",
                "phi_mean",
                "phi_p50",
                "P_mean_mm",
                "PET_mean_mm",
                "stream_wtd_p10",
                "stream_wtd_p50",
                "upland_wtd_p50",
                "corridor_contrast",
                "wtd_error",
                "phi_error",
            ):
                if k in m:
                    row[k] = m[k]
        row["track_label"] = label_track(
            {
                **row,
                "rsr_lt": rsr if np.isfinite(rsr) else np.nan,
                "wtd_p50": row.get("wtd_p50", np.nan),
                "frac_wtd_2_20": row.get("frac_wtd_2_20", np.nan),
                "wtd_p10": row.get("wtd_p10", np.nan),
                "wtd_p90": row.get("wtd_p90", np.nan),
                "phi_mean": row.get("phi_mean", np.nan),
                "corridor_contrast": row.get("corridor_contrast", np.nan),
                "hard_reject": reject,
                "headwater": headwater,
            }
        )
        annotated.append(row)
        with (OUT / "huc_selection_annotated_tracks.csv").open("w", newline="") as f:
            # stable field order
            keys = []
            for r in annotated:
                for k in r:
                    if k not in keys:
                        keys.append(k)
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(annotated)

    # Rank picks
    def score_A(r):
        try:
            return (
                float(r.get("frac_wtd_2_20", 0))
                * max(float(r.get("corridor_contrast", 0)), 0.1)
                / max(float(r.get("rsr_lt", 1)), 0.05)
            )
        except Exception:
            return -1

    def score_B(r):
        try:
            ribbon = max(float(r.get("corridor_contrast", 0)), 0)
            return float(r.get("phi_mean", 0)) * (1 + ribbon) / max(float(r.get("rsr_lt", 1)), 0.05)
        except Exception:
            return -1

    A_pool = [r for r in annotated if r.get("track_label") in ("A", "A_soft", "both", "both_weak_ribbon")]
    B_pool = [r for r in annotated if r.get("track_label") in ("B", "B_weak_ribbons", "both", "both_weak_ribbon")]
    A_pool.sort(key=score_A, reverse=True)
    B_pool.sort(key=score_B, reverse=True)

    summary = {
        "n_candidates": len(CANDIDATES),
        "n_rsr_le_055": sum(
            1
            for r in annotated
            if isinstance(r.get("rsr_lt"), (int, float)) and float(r["rsr_lt"]) <= 0.55
        ),
        "A_top": A_pool[:5],
        "B_top": B_pool[:5],
        "wtd_note": "CONUS2 baseline WY2003 monthly mean water_table_depth (ss_water_table_depth not in catalog)",
    }
    (OUT / "huc_selection_screen_summary.json").write_text(
        json.dumps(summary, indent=2, default=str)
    )
    print("\n=== TOP TRACK A ===", flush=True)
    for r in A_pool[:5]:
        print(
            r["huc8"],
            r["name"],
            f"RSR={r.get('rsr_lt')}",
            f"φ={r.get('phi_mean')}",
            f"WTD50={r.get('wtd_p50')}",
            f"frac2-20={r.get('frac_wtd_2_20')}",
            r.get("track_label"),
            flush=True,
        )
    print("\n=== TOP TRACK B ===", flush=True)
    for r in B_pool[:5]:
        print(
            r["huc8"],
            r["name"],
            f"RSR={r.get('rsr_lt')}",
            f"φ={r.get('phi_mean')}",
            f"contrast={r.get('corridor_contrast')}",
            r.get("track_label"),
            flush=True,
        )
    print("wrote CSVs under", OUT, flush=True)


if __name__ == "__main__":
    main()
