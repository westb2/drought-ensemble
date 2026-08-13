# Plan: select HUCs for intermediate-WTD and/or arid–ribbon showcases

**Goal:** Select **one or both** of two complementary headwaters catchments that validate well in ParFlow CONUS2 and showcase the local Budyko / temporary–persistent framing:

| Track | Catchment type | Primary job |
|-------|----------------|-------------|
| **A — Intermediate WTD** | Water table mass in the **sensitive intermediate zone** | Best **theory discriminator** (limbs tip with drought length; peaks vs mean split) |
| **B — Arid ribbons** | Domain **water-limited (φ≫1)** but **energy-limited / connected spots near streams** | Best **classical-Budyko contrast** (local limbs inside a dry sea) |

**Recommendation:** Prefer **Track A as the primary new domain**. Add **Track B** if budget allows (or if A cannot be found with good RSR). Do not treat Mid-Atlantic corridor HUCs (`02070008`) as substitutes — headwaters rule still applies.

**Related:** `budyko_local_framing_handoff.md`, `budyko_drought_literature.md`, prior plan replaced by this file, `pumping-rate-context.md`.

**Out of scope for v1:** choosing `pumping_rate_fraction`. First runs = no-pump drought/recovery.

---

## 0. Why two tracks (decision from framing discussion)

- **Track A** maximizes where your distinctive predictions are sharpest: many cells sit near the connected↔disconnected threshold, so 1→10→50 yr drought should **expand persistent area**; overland/WTD beat climate-only and distance-only; peaks recover in ~1 yr while low flows lag. CONUS skill usually safer.
- **Track B** maximizes the **cartoon and T1 test**: whole basin looks water-limited, yet temporary deficits and peak recovery still hug stream corridors. Risk: thin temporary limb, ephemeral channels, weaker CONUS RSR — keep only if skill passes.

Existing anchors (late-spinup column WTD, recovery analyses):

| Domain | φ (approx) | WTD p10 / p50 / p90 | Role already filled |
|--------|------------|---------------------|---------------------|
| `wolf2` | ~0.64 humid | ~0 / **2.2** / 11 m | Too wet / connected — high f_temp widely |
| `potomac2` | ~0.90 transitional | ~0.6 / **39** / 247 m | Deep uplands already; mixed limbs |

Track A should **not** clone Wolf (too shallow) or merely deepen Potomac’s already-deep tail. Target a basin whose **central mass** of cells sits in an intermediate band with clear corridor↔upland contrast.

---

## 1. Framing predictions both tracks must test

| ID | Prediction |
|----|------------|
| P1 | Temporary ↔ high overland / shallow WTD |
| P2 | Persistent grows with drought length in deep / low-overland cells; temporary saturates |
| P3 | Domain φ sets mix; local connectivity ranks cells |
| P4 | High-Q (p90/p99/max) recovers in ~1 recovery year |
| P5 | Peak recovery ≠ full annual Q/P or baseflow recovery |

### Competing theories (same for both tracks)

| ID | Theory | Track that stresses it most |
|----|--------|------------------------------|
| T1 | Domain-mean classical Budyko only | **B** (arid) + A within-basin maps |
| T2 | Uniform single-store memory | **A** (two timescales + spatial tip) |
| T3 | Distance / HAND only | Both (partial out WTD/overland) |
| T4 | Geology / K only | Both |
| T5 | Permanent Q/P regime shift (peaks stay dead) | **A** especially; **B** if peaks still recover from thin ribbons |
| T6 | Only humans cause non-recovery | Both (no-pump runs) |

---

## 2. Hard filters (both tracks)

Fail any → reject.

1. **Headwaters HUC8** — no major upstream mainstem through-flow (exclude `02070008`-class corridors). Gage drainage ≈ HUC mask.
2. **CONUS2 streamflow RSR ≲ 0.55** (prefer ≲ 0.50); method as in `pumping-rate-context.md`. **Expand screen beyond Mid-Atlantic CSV.**
3. **USGS outlet gage** snappable to high overland cell; adequate record.
4. **Non-tidal / non-estuarine** outlet.
5. **Feasible size** (~1k–6k cells preferred); flag huge plains disks.
6. **Low CU** for v1 natural test (high-CU = later experiment).

---

## 3. Track-specific soft criteria

### Track A — Intermediate / sensitive WTD (primary)

Operational targets using CONUS2 `ss_water_table_depth` on the HUC mask (tune after first screen if needed):

| Metric | Target | Rationale |
|--------|--------|-----------|
| Median WTD | roughly **3–25 m** | Between Wolf (~2 m) and Potomac median (~39 m) |
| Fraction of active cells with WTD ∈ **[2, 20] m** | **high** (prefer ≳ 30–40%) | Mass in “tipping” band |
| WTD p10 | ≲ **2 m** | Retain connected corridors |
| WTD p90 | ≳ **15–30 m** (not necessarily Potomac’s 200 m+) | Real upland disconnect possible |
| Overland / channel contrast | Clear stream network + dry interfluves | Needed for P1 maps |
| Domain φ | Prefer **not** a Wolf clone; mild humid→subhumid OK | A is not mainly a φ experiment |
| Physiography | Prefer **non–Valley & Ridge clone** of `02070001` | Coastal Plain headwaters, Piedmont source basin, plateau, etc. |

**Score high if:** drought length is expected to move a large fraction of cells across stream-connected vs upland-persistent behavior.

### Track B — Arid with energy-limited ribbons (secondary)

| Metric | Target | Rationale |
|--------|--------|-----------|
| Domain φ | **≳ 1.2–1.5** (clearly water-limited) | T1 contrast vs Wolf/Potomac |
| Near-stream WTD | Shallow ribbons still present (p10 ≲ 2–5 m along channels) | Local energy-limited spots |
| Overland | Ephemeral OK **if** CONUS2 still has usable channel structure and RSR passes | Ribbons must be real in the model |
| Temporary limb expectation | Thin but nonzero | If temporary≈0 everywhere, B fails as a showcase |
| Human confounding | Especially low farm-dam / pumping if comparing to obs Q/P stories | Clean ribbon signal |

**Reject B if:** RSR fails, or CONUS2 shows no shallow-WT / overland corridors (uniform deep desert).

---

## 4. Screening workflow

### Step 1 — One expanded skill table
Build `huc8_headwater_streamflow_rsr.csv` for headwater HUC8s (eastern US + selected Interior/plains/mountain sources). Keep RSR ≲ 0.55.

### Step 2 — Split survivors into Track A vs B pools
Annotate each keep with:

- φ (P vs PET)
- CONUS2 ss_WTD: p10, p50, p90, fraction in [2, 20] m
- Physiography, CU depth, existing `domains/` spinup
- Assign **A**, **B**, **both**, or **neither** (neither = good skill but wrong WTD/φ niche — e.g. another Wolf)

### Step 3 — Rank within each track
- **A:** maximize (fraction in intermediate band × corridor contrast × not Potomac/Wolf clone × RSR).
- **B:** maximize (φ × evidence of stream ribbons × RSR); heavily penalize missing ribbons.

### Step 4 — Choose portfolio

| Budget | Selection |
|--------|-----------|
| **One domain only** | **Best Track A** |
| **Two domains** | Best **A** + best **B** |
| **A unavailable** (no intermediate + RSR) | Best **B** that still has ribbons; note weaker theory-discrimination |

### Step 5 — User gate
Present A pick, B pick (or “B none qualified”), costs; wait for confirmation before `get_domain`.

**2026-08-13 disk-safe execution:** screening outputs + provisional A/B picks are in [`budyko_huc_selection_recommendation.md`](budyko_huc_selection_recommendation.md). No `get_domain` run (scratch ~89% full; HydroData PIN expired).

---

## 5. Pre-screen notes on known names

| Candidate | Likely track | Notes |
|-----------|--------------|-------|
| `02070008` | — | Fail headwaters |
| `02060006` Patuxent / CP native HW | **A?** | Check median WTD + headwaters purity + non-tidal gage; RSR ~0.52 |
| `02080109` Nanticoke | Weak A / reject | Tidal / low-relief risk |
| `republican` / `ponca` (`10250003`) | **B?** | Score RSR first; arid φ likely; ribbons must exist in CONUS2 |
| New search | **A** priority | Headwaters with ss_WTD median in intermediate band + good RSR |
| New search | **B** backup | φ≫1 headwaters with channel WTD ribbons + RSR |

---

## 6. Experiments once domains exist

Same package for A and B (definitions unchanged):

1. Temp/persist maps, strata, length scaling (1/3/10; 50 if memory long).  
2. Spearman/hexbin: f_temp vs overland, WTD, dist, φ, K.  
3. Outlet mean vs p90/p99/max through recovery.  
4. Three- (or four-) domain Budyko-space figure with Wolf + Potomac + A [+ B].

### Track-specific success looks like

**Track A**

- Large area with intermediate baseline WTD; f_temp drops and persistent area grows as drought lengthens.  
- Peaks back by recovery yr1–2; mean/low flow still suppressed when persistent is large.  
- Overland+WTD explain f_temp better than φ or distance alone.

**Track B**

- Domain φ water-limited; temporary deficits **confined to stream ribbons**; uplands almost all persistent.  
- Despite arid climate, **high-Q still recovers in ~1 yr** from those ribbons (strong anti-T5 result).  
- If temporary limb is undetectable, B was a bad pick — say so.

### Falsifiers (either track)

- No overland/WTD structure in temp/persist.  
- High-Q suppressed for years under average recovery forcing (no pump).  
- Persistent does not grow with length in deep/low-overland cells.

---

## 7. Cost sketch

Per new domain (order of magnitude, 4×64 ranks):

- 40 yr spinup + baseline overlap + droughts 1/3/10 + 5 yr recovery ≈ **~70–90 unique years** if little reuse.  
- ~0.7–1.2 h/yr; disk wolf-scale ~20 GB/yr to potomac-scale ~50+ GB/yr (plains larger).  
- **Two-track portfolio ≈ 2×** unless one reuses existing spinup (`republican` only if it qualifies as B).

Suggested order: **spin up / drought Track A first**; only then B.

---

## 8. Deliverables before domain creation

1. Expanded headwater RSR CSV.  
2. Annotated table with Track A/B labels + WTD/φ metrics.  
3. Recommended **A primary** (+ **B optional**), with costs and why each beats Wolf/Potomac for its job.  
4. Explicit list of rejects (corridor skill champs, tidal CP, no-ribbon arid, Wolf clones).

---

## 9. Decision rule

```text
hard filters → pool
annotate φ + ss_WTD → label A / B / both / neither
IF budget == 1: pick best A (else best B with ribbons)
IF budget >= 2: pick best A AND best B
user A before B in the run queue
user confirms → get_domain → no-pump droughts 1/3/10 (+50 if warranted)
```
