# HUC selection recommendation (disk-safe screen)

**Date:** 2026-08-13  
**Plan:** [`budyko_huc_selection_plan.md`](budyko_huc_selection_plan.md)  
**Status:** Steps 1–4 from available data only. **Stopped at Step 5 (user gate).** No `get_domain`, no new spinups, no HydroData downloads.

**Disk posture:** `/glade/derecho/scratch` ≈ **89% full** (~3.4 T free). `drought-ensemble` alone ≈ 27 T. This screen wrote only tiny CSVs under `analysis/` (~16 KB total).

---

## Blockers (honest)

| Need | Status |
|------|--------|
| Expanded national CONUS2 RSR (`huc8_headwater_streamflow_rsr.csv` beyond Mid-Atlantic) | **Blocked:** `hf_hydrodata` PIN for `benjaminwest@arizona.edu` is **expired**; `/glade/p/cisl/hydro/hydrodata` not mounted here |
| CONUS2 `ss_water_table_depth` on candidate HUC masks (Patuxent, etc.) | Same blocker |
| New domain creation | **Deferred by design** (disk risk) |

Reusable Mid-Atlantic RSR snapshot remains in `.tmp_hydrodata/huc8_streamflow_rsr.csv`. This run copied/annotated survivors into `analysis/huc8_headwater_streamflow_rsr.csv`.

---

## Existing-domain benchmarks (φ + WTD)

| Domain | HUC8 | φ (Hamon/CW3E avg yr) | Late WTD p10 / p50 / p90 (m) | frac WTD ∈ [2,20] m | Role |
|--------|------|------------------------|------------------------------|---------------------|------|
| `wolf2` | `08010210` | **0.63** | 0 / **2.2** / 10.5 | 0.51 | Too wet / connected (not Track A) |
| `potomac2` | `02070001` | **0.90** | 0.6 / **39** / 246 | 0.10 | Deep upland tail (not Track A niche) |
| `republican` | `10250003` | **1.22** | spun-up sample: 0.01 / **0.5** / 9 | 0.16 | Arid φ; spun-up WTD **too shallow** for ribbons |
| `ponca` | `10250003` | **1.63** (diff avg yr) | 0.05 / **1.6** / 29 | 0.28 | Same HUC mask; still weak corridor contrast |

**CONUS2 `ss_pressure_head` → WTD** (correct CONUS2 `DZ_M`; selection-style, not spun-up):

| Domain | ss WTD p10 / p50 / p90 | frac [2,20] |
|--------|------------------------|-------------|
| `potomac2` | 0.01 / 31 / 224 | 0.04 |
| `wolf2` | 0 / 1.3 / 8.4 | 0.27 |
| `republican`/`ponca` mask | **2.0 / 20 / 51** | **0.39** |

So HUC `10250003` **looks like Track A on steady-state CONUS2**, and **Track B on climate (φ≫1)** — but **available spun-up years are Wolf-shallow with weak corridor contrast**. Do not treat current republican/ponca runs as a successful arid–ribbon showcase without a clean late-spinup average-year WTD/overland audit (read-only).

CSVs: `huc_selection_wtd_phi_existing.csv`, `huc_selection_existing_domain_metrics.csv`.

---

## Hard-filter screen (Mid-Atlantic + known domains)

Annotated table: `huc_selection_annotated_tracks.csv`.

### Rejects (explicit)

| HUC8 | Why |
|------|-----|
| `02070008` | Corridor (max gage drain ~11 560 mi²); plan forbids |
| `02070010` | Metro / Fall Line corridor |
| `02080109` | Tidal Coastal Plain risk |
| `02080108` / `02080208` | Hampton Roads; RSR ≫ 0.55 |
| `02080110` | Tidal / Tangier; poor RSR |
| `02060002`, `02060003`, `02080206` | RSR > 0.55 (or missing) |
| `02070001` | Keep as existing; **neither** for new Track A (deep median) |
| `08010210` | Existing Wolf; **neither** (too wet) |

### Survivors needing WTD/φ (skill + headwaters OK)

| HUC8 | Name | RSR | Outlet gage | Notes |
|------|------|-----|-------------|-------|
| **`02060006`** | **Patuxent** | **0.52** | `01594440` (~348 mi²) | Best **new Track A** name in current pool; CP native headwaters; **CONUS2 ss_WTD still required** |
| `02080111` | Pocomoke–W. Lower Delmarva | 0.52 | `01485000` | Skill OK; low-relief / tidal-edge risk — backup only |

---

## Portfolio recommendation (two tracks)

Per plan: **best A + best B**, run A before B, **user confirms before `get_domain`**.

### Track A (primary) — provisional pick

**`02060006` Patuxent (new domain if confirmed)**

| Criterion | Assessment |
|-----------|------------|
| Headwaters | Yes (max stream gage drain ~348 mi²) |
| CONUS2 RSR | 0.52 (≤ 0.55) |
| Non-tidal outlet | Plausible at `01594440` (still verify snap to high-overland cell) |
| Intermediate WTD | **Unknown until PIN + ss_WTD mask** (Coastal Plain may be too shallow → Wolf-like) |
| Physiography | Atlantic Coastal Plain — **not** a Valley & Ridge clone of `02070001` |
| Disk | **New domain = high risk** on 89% scratch (~tens of GB/yr × ~70–90 yr if full package) |

**Only create after:** renew HydroData PIN → compute ss_WTD + φ on HUC mask → confirm median ~3–25 m and frac[2,20] ≳ 0.3. If Patuxent fails WTD, expand eastern headwater RSR screen (same PIN) before any `get_domain`.

### Track B (secondary) — disk-safe pick

**Reuse existing `republican` (HUC `10250003`) — do not `get_domain` again**

| Criterion | Assessment |
|-----------|------------|
| φ | **1.22** (avg yr 2010) — meets ≳ 1.2 |
| Ribbons | ss WTD suggests shallow p10 + deeper uplands; **spun-up samples do not** |
| Headwaters | Marginal (gage `06827500` drain ~2740 mi²) |
| CONUS2 RSR | **Not scored** (PIN blocked); domain outlet config `OUTLET_X/Y=66,135` is **out of bounds** for 99×166 grid (real high-flow cell near ~`(131,70)`) |
| Disk | **Already paid** (~5.6 T under `domains/republican`) |

**Gate for calling B “qualified”:** (1) CONUS2 multi-gage RSR ≤ 0.55 after PIN renew, (2) late-spinup average-year map showing stream ribbons vs deeper interfluves, (3) fix outlet/gage pairing before any new drought package. If ribbons fail, B = none qualified (do **not** create a second plains domain while scratch is tight).

---

## Costs (order of magnitude)

| Action | Disk | Compute |
|--------|------|---------|
| Renew PIN + HUC mask metrics only | ~0 (summaries) | small |
| New Patuxent full package (spinup + droughts 1/3/10 + recovery) | **large** (plan ~20–50+ GB/yr × ~70–90 yr) | ~0.7–1.2 h/yr on 4×64 |
| Reuse republican for B analyses | **0 new** if reusing existing years; more if new drought lengths missing | depends on gaps |
| New arid HUC from scratch | **Avoid** while scratch ≥ ~85% | — |

Suggested order if you green-light later: **PIN metrics → confirm Patuxent A → only then any `get_domain` for A → B = republican audit first, new B domain last resort.**

---

## Deliverables written this run

1. `analysis/huc8_headwater_streamflow_rsr.csv` — headwater/skill annotation of available RSR pool  
2. `analysis/huc_selection_annotated_tracks.csv` — Track A/B/reject labels  
3. `analysis/huc_selection_wtd_phi_existing.csv` — φ/WTD for existing domains  
4. `analysis/huc_selection_existing_domain_metrics.csv` — φ from average forcing  
5. This recommendation (user gate)

---

## User gate (needed before any creation)

Please confirm:

1. **Track A:** Proceed with Patuxent (`02060006`) **only after** PIN renew + ss_WTD pass — or name a different eastern headwater priority list for the expanded RSR screen?  
2. **Track B:** Accept **reuse `republican`** (with RSR/ribbon audit) vs declare B unqualified until a different arid HUC is screened?  
3. Explicitly **do not** run `get_domain` until you OK disk budget (scratch ≈ 89% full).
