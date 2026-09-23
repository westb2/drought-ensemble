# Handoff: local Budyko framing → next catchment selection

**Audience:** a new agent planning how to **select a new catchment/domain** to test or extend this framing.  
**Date:** August 2026  
**Do not** choose pumping rates unless the user asks; see `pumping-rate-context.md`.

---

## 1. Core framing (what to preserve)

Temporary vs persistent **column storage deficits** after drought can be read as a **local, connectivity-weighted analogue of Budyko energy- vs water-limited regimes**, with **overland-flow participation** (not cell climate φ) as the main within-basin axis.

| Limb | Landscape signature | Deficit behavior | Streamflow implication |
|------|---------------------|------------------|------------------------|
| **Temporary / “energy-limited” / export-connected** | Shallow WTD, high overland participation, near-stream / wet corridors | Recovers in ~recovery year 1; **saturates** with drought length by ~10 yr | Pays for Q during drought; **high-Q / peaks rebound in ~1 yr** once average forcing returns |
| **Persistent / “water-limited” / recharge-limited** | Deep WTD, low K, uplands, low overland | Remains after year 1; **grows** through 50 yr drought | Suppresses low flows / mean Q longer; does **not** permanently break peak generation |

**Important nuance:** Domain-mean climate aridity (φ = PET/P) separates **catchments** (Wolf wetter than Potomac). Within a basin, φ is nearly uniform, so **local ranking is WTD + overland connectivity**, not PET/P maps.

Classical Budyko language is a useful metaphor; mechanistically this is closer to **drought attenuation / baseflow resilience / connected vs buffered recovery** (see literature file).

---

## 2. Evidence already in hand (Potomac + Wolf)

### Domains

| ID | Display | Climate | Role in contrast |
|----|---------|---------|------------------|
| `potomac2` | Potomac | φ≈0.90 (near threshold; some cells φ>1); P≈790 mm | More persistent memory; stream cells high *fraction* temporary; mid/upland hold large absolute persistent volume |
| `wolf2` | Wolf | φ≈0.64 (energy-limited); P≈1530 mm | Higher temporary fraction broadly (near/mid wet landscape); weaker within-domain φ contrast |

### Quantitative takeaways

- Temporary domain totals **saturate** by ~10 yr; persistent keeps growing (50/10 ≈ ×3 in uplands, ×1.4–2 in streams).
- Within-domain Spearman: **Wolf** temporary fraction ↔ shallow WTD (ρ≈−0.53) and overland (+0.25–0.30); **Potomac** cellwise f_temp weak, but persistent *magnitude* anti-correlates with overland (ρ≈−0.48).
- **Outlet high flows:** suppressed during drought; **recovery year 1** restores p90/p99/max (Wolf ≈1; Potomac "overshoot" was measured at the near-dry config outlet (66, 135) and is absent at the mainstem (63, 129) — see `persistent_storage_vs_streamflow_50yr.md` caveat); by year 2 ≈ baseline. After 50-yr Potomac only a mild residual mean/p90 (~0.96 / ~0.90), not indefinite peak suppression.
- Implication: annual Q/P or low-flow non-recovery ≠ failure of the runoff-generating limb; peaks track the temporary limb.
- **Persistent storage vs Q at 50 yr:** deep persistent grows a lot, but outlet Q plateaus mid-drought and does **not** show a clean baseflow collapse in recovery — full note [`persistent_storage_vs_streamflow_50yr.md`](persistent_storage_vs_streamflow_50yr.md).

### Key artifacts

| Path | Content |
|------|---------|
| `analysis/budyko_temp_persistent.py` | Metrics + figures script |
| `analysis/budyko_temp_persistent_summary.md` | Results summary |
| `analysis/figures/budyko_*.png` | Maps, hexbins, strata, Budyko space |
| `analysis/budyko_drought_literature.md` | Literature + streamflow/Q/P robustness + confounders |
| `analysis/redo_recovery_with_50yr.py` | Temp/persist definitions, 1/3/10/50 recovery |
| `analysis/drought_recovery_50yr_summary.md` | Domain-total temp/persist table |
| `analysis/persistent_storage_vs_streamflow_50yr.md` | 50-yr persistent ΔS vs outlet Q / baseflow verdict + ratios JSON |
| `.cursor/skills/drought-ensemble/plotting.md` | Temp/persist map conventions |
| `.cursor/skills/drought-ensemble/pumping-rate-context.md` | HUC screening, CU, geologic triad |

### Definitions (keep consistent)

- Deficit = baseline column storage − drought (m water equiv.).
- **Temporary** = max(deficit_start − deficit_1yr, 0).
- **Persistent** = max(deficit_1yr, 0).
- Streams = top 3% late-spinup baseline mean `overland_flow`.
- Sequence: 40 yr average spinup → dry drought → 5 yr average recovery.

---

## 3. What a *new* catchment is for

Use a third domain to **stress-test or span the framing**, not to duplicate Wolf or Potomac.

### Scientific questions a new domain should help answer

1. Does temporary↔overland / persistent↔deep-WTD hold outside Mid-Atlantic / Appalachian settings?
2. Does domain-mean φ (humid vs arid) change the **mix** of temporary vs persistent the way Wolf vs Potomac suggests?
3. Do **high-Q events still recover in ~1 year** when persistent storage is large (arid / deep aquifer / long memory)?
4. Optional later: with pumping, does human extraction preferentially damage the connected limb (baseflow) while peaks still recover? (Only if user wants pumping; rates are user-chosen.)

### Selection axes (prioritize contrasts)

Pick candidates that move at least **two** of these away from the current pair:

| Axis | Current pair | Useful third domain |
|------|--------------|---------------------|
| **Aridity φ** | Wolf humid; Potomac transitional | Clearly **water-limited** (φ≫1) *or* more humid than Wolf |
| **Overland / wetness structure** | Both have clear stream networks | Sparse channelization, endorheic, or very dense wetland/DRIP-like connectivity |
| **WTD / aquifer memory** | Fractured rock / relatively local systems | Thick sediment / Coastal Plain / large dynamic GW storage (long τ) |
| **K / confinement** | Flow-barrier experiments already on Potomac variants | Strongly contrasting near-surface K or confined vs unconfined |
| **Human confounding (for obs comparison)** | Model droughts are clean (no pump) | If validating Q/P recovery vs gages: prefer **low pumping / low farm-dam** HUCs so observational “non-recovery” papers are less confounded |

### Practical CONUS2 / project constraints

- Prefer HUC8-scale subsets like existing domains (~few thousand 1 km cells); check runtime (~0.7–1.2 h/yr on 4×64) and scratch (~20–100 GB/domain full years).
- Need CW3E average/dry/wet forcing via `Domain.get_domain_year` (subsettools).
- USGS gage on mainstem for streamflow validation (see `usgs-streamflow-validation.md`).
- Existing inventory / shortlists: `republican`, `ponca`, flow_barrier_* , and geologic-diversity triad in `pumping-rate-context.md` (`02070001` / `02070008` / Coastal Plain `02080109` or `02060006`). **Reuse spinup if a domain already has 40 yr average** before proposing brand-new HUCs.
- Jul 2026 CONUS2 streamflow RSR rankings live in pumping-rate-context — use for skill, not as the Budyko-framing criterion alone.

### Suggested contrast targets (for the planning agent)

Rank candidates into buckets; user picks:

1. **Arid / high-φ, still with channel network** — tests whether temporary limb shrinks and persistent dominates; check whether peaks still recover in 1 yr. (`republican`-class plains / western HUC if already partly spun up is attractive.)
2. **Coastal Plain / large GW storage** — tests long persistent memory and baseflow lag while peaks recover (Fall Line / Coastal Plain HUCs already shortlisted for geology).
3. **Metro / high-CU HUC** — only if the science goal includes pumping confounders later; not required for the natural connected-limb test.

Avoid: near-duplicates of South Branch Potomac Valley & Ridge or another small humid Appalachian basin unless the goal is replication.

---

## 4. Minimal analysis package for any new domain

Once spun up and drought members exist (1/3/10 at least; 50 if affordable):

1. Baseline: φ (P, Hamon PET or better), overland participation, WTD, stream mask.
2. Temp/persist storage maps + domain totals vs drought length.
3. Strata: Stream / near / mid / upland (deep WTD) — f_temp and persist growth 50/10.
4. Outlet Q: during drought and recovery years 1–5 — **mean, p90, p99, max** vs baseline (peaks vs body of hydrograph).
5. Optional: compare to Wolf/Potomac in one Budyko-space figure (φ vs Q_ol/P colored by f_temp).

Falsifiers worth stating up front:

- Temporary fraction **uncorrelated** with overland/WTD after controlling for noise.
- High-Q still suppressed after several average recovery years (natural run, no pumping).
- Persistent does **not** grow with drought length in deep-WTD areas.

---

## 5. Literature pointers (do not rediscover from scratch)

Full write-up: **`analysis/budyko_drought_literature.md`**.

Cite-first: Du et al. 2016 (shallow vs deep WT in Budyko space); Condon & Maxwell 2017; Thompson et al. 2017 (lateral redistribution); Van Loon et al. 2024 (memory continuum); Van Lanen drought attenuation; Briggs baseflow resilience; DRIPs; Peterson/Saft runoff non-recovery (**watch human confounders**); Fan / Costa for WTD landscape limbs.

Project niche: temp/persist as local energy/water limbs with overland marker + drought-length scaling + peak recovery in ~1 yr is **not** already standard language in that literature.

---

## 6. Instructions for the planning agent

1. Read this file + `budyko_drought_literature.md` + `pumping-rate-context.md` (HUC/geology shortlists) + domain spinup inventory in `SKILL.md`.
2. Propose a **shortlist of 3–5 HUC8s/domains** with explicit placement on the axes in §3 (φ, overland structure, aquifer memory, K, human confounding).
3. Prefer extending an **already partially spun-up** domain when it fits a contrast bucket.
4. Include rough cost (years to run × h/yr × disk) and a recommended drought-length set (e.g. 1/3/10 first; 50 later).
5. Do **not** set `pumping_rate_fraction` unless the user asks; for a clean test of this framing, **no-pump drought sequences** are the right first experiment.
6. End with a recommended primary pick + why it maximally stresses the framing relative to Potomac and Wolf.

**Selection plan (headwaters + CONUS skill; Track A intermediate-WTD and/or Track B arid ribbons):**  
[`budyko_huc_selection_plan.md`](budyko_huc_selection_plan.md)
