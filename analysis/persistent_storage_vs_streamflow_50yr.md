# Persistent storage vs streamflow (50-year droughts)

**Date:** August 2026  
**Question:** After 50-year droughts, is there finally enough persistent storage loss to affect streamflow — especially baseflow?  
**Verdict:** Persistent deep storage grows a lot; outlet streamflow does **not** track that growth. Only a **mild residual** remains in recovery, and it is **not** a clean baseflow collapse.

> **Caveat (22 Sep 2026):** Potomac outlet numbers here were taken at the config outlet (66, 135), a near-dry side cell (~0.07 mm/yr vs 180 mm/yr at the mainstem (63, 129)). The Potomac "yr-1 overshoot" (~1.2×) does not appear at the mainstem (10-yr yr 1 ≈ −4.8%, 50-yr ≈ −5.9%; recovery yrs 2–5 −0.6% / −1.5%). The storage conclusions stand; re-derive the Potomac Q ratios with `analysis/outlet_flow.py` before citing them. See [`potomac_sensitivity_attribution_summary.md`](potomac_sensitivity_attribution_summary.md).

Related: [`drought_recovery_50yr_summary.md`](drought_recovery_50yr_summary.md), [`shallow_deep_shielding_summary.md`](shallow_deep_shielding_summary.md), [`budyko_local_framing_handoff.md`](budyko_local_framing_handoff.md).

---

## Theory being tested

| Limb | Expectation for Q |
|------|-------------------|
| Temporary / near-surface / connected | Pays for drought Q; **peaks rebound in ~1 recovery year** |
| Persistent / deep / recharge-limited | Should eventually suppress **low flows / baseflow / mean Q** once large enough |

---

## What 50 years do to storage

Domain totals (temporary / persistent, 10⁶ m³; from recovery yr-1 split):

| Domain | 10-yr | 50-yr |
|--------|-------|-------|
| Potomac | 88 / 126 | 92 / **418** |
| Wolf | 127 / 76 | 133 / **216** |

- Temporary **saturates** by ~10 yr.
- Persistent keeps growing (~×3 from 10→50). Growth is almost entirely **deep** (z&lt;6 / below 2 m): Potomac ~92% of 50-yr persistent in deep; Wolf ~99%.
- 5 years of average recovery **do not** erase the 50-yr ΔS memory.

Figures: `figures/drought_exploratory/fifty_year_drought_streamflow_storage.png`, `figures/drought_exploratory/drought_recovery_totals_and_anomalies.png`, shallow/deep partition in `shallow_deep_shielding_summary.md`.

---

## What that does (and does not) do to streamflow

### During the drought

Outlet Q **steps down** when dry forcing starts and then **plateaus**. Storage continues to ratchet down for decades **without** a matching gradual decline in outlet flow. Accumulating deep losses are largely **decoupled from Q** mid-drought.

### Recovery (outlet Q / same-phase baseline)

Cached ratios: [`figures/_data/outlet_flow_recovery_ratios_50yr.json`](figures/_data/outlet_flow_recovery_ratios_50yr.json).

| Domain | Recovery yr1 | Recovery yr2–5 |
|--------|--------------|----------------|
| **Wolf** 50-yr | mean ~0.89×, **p50 ~0.59×**, p90/max ≈1 | ~0.99× (essentially back) |
| **Potomac** 50-yr | mean ~1.21×, p90 overshoots (~1.53×) | mean ~0.95–0.96×, p90 ~0.80–0.88× lingering |

Compared with shorter droughts: peaks still recover in ~1 yr everywhere. The only clearer leftover at 50 yr is Potomac’s mild mean/p90 residual through year 5.

### Baseflow caveat

- Outlet **p10 ≈ 0** on baseline → low-flow ratios are undefined; we cannot score classical “baseflow” from outlet percentiles alone.
- ΔQ troughs near zero partly reflect that floor, not proof that low flows are healthy.
- Closest “body of hydrograph lags peaks” signal: Wolf recovery-yr1 **median** suppression, gone by year 2.
- A proper baseflow test needs subsurface discharge to channels (or another non-zero low-flow index), not outlet p10.

### Flow-regime partition (recovery years 2–5)

Among wet baseline timesteps (Qb > 0), split into low / mid / high terciles and ask where the **negative ΔQ volume** sits after the year-1 rebound. Numbers in [`figures/_data/baseflow_streamflow_partition_50yr.json`](figures/_data/baseflow_streamflow_partition_50yr.json); figure [`figures/drought_exploratory/fifty_year_streamflow_baseflow_partition.png`](figures/drought_exploratory/fifty_year_streamflow_baseflow_partition.png).

| Domain | Drought | Low tercile share of −ΔQ | Mid | High |
|--------|---------|--------------------------|-----|------|
| Potomac | 50-yr | **9%** | 27% | **64%** |
| Wolf | 50-yr | **6%** | 39% | **55%** |

- Fractional hit can look larger in the low tercile (Potomac low r_mean ≈ 0.90 vs high ≈ 0.97), but those timesteps carry little water, so they do **not** dominate the residual ΔQ.
- Most of the leftover streamflow deficit volume is on **high baseline-flow** steps — the opposite of “mostly baseflow.”
- Wolf’s residual after year 1 is only ~1% of mean Q anyway (10-yr and 50-yr look alike).

---

## Potomac follow-up: is residual Q just slow near-surface recovery?

Potomac near-surface ΔS recovers over ~4–5 years (not Wolf’s instant snap-back). Does that explain the 50-yr Q residual?

**No.** Near-surface recovery is almost the same after 10-yr and 50-yr droughts; only 50-yr keeps a Q hit. Figures: [`potomac_ns_vs_q_recovery_contrast.png`](figures/drought_exploratory/potomac_ns_vs_q_recovery_contrast.png), [`potomac_ns_storage_vs_streamflow_recovery.png`](figures/drought_exploratory/potomac_ns_storage_vs_streamflow_recovery.png); data [`potomac_ns_storage_vs_streamflow_recovery.json`](figures/_data/potomac_ns_storage_vs_streamflow_recovery.json).

| Recovery year | 10-yr NS ΔS (10⁶ m³) | 10-yr Q/base | 50-yr NS ΔS | 50-yr Q/base |
|---------------|---------------------:|-------------:|------------:|-------------:|
| 1 | −52 (93% of eod) | 1.25 | −53 (91%) | 1.21 |
| 2 | −25 (45%) | **1.00** | −25 (43%) | **0.96** |
| 5 | −4 (8%) | **1.00** | −4 (7%) | **0.97** |

- End-of-drought near-surface deficit is nearly identical (−56 vs −58); deep is not (−111 vs −405).
- By year 2, 10-yr Q is fully back while NS is still ~45% drawn down → Q does **not** wait on NS.
- By year 5, NS is ~93% recovered in both cases, but 50-yr mean Q is still ~3% low → the residual **persists after NS is largely gone**.
- Annual dQ–NS correlations look strong only because both trend with recovery time; the 10-vs-50 contrast is the identification.

---

## Interpretation

1. **50-yr strengthens the storage story** — deep persistent memory is real and large.
2. **50-yr also strengthens the shielding / connected-limb story** — Q does not follow the deep drain.
3. Theory was right that **peaks** track the temporary limb (fast recovery).
4. Theory that persistent losses would **mainly show up as baseflow damage** is **denied** for the volume of residual ΔQ: only a mild Potomac mean/p90 residue exists, and that residue’s mass sits mostly in high-flow timesteps, not low-flow ones.
5. Potomac’s slow near-surface recovery does **not** explain that residue: NS paths match at 10 and 50 yr; Q residue is 50-yr-only and outlasts NS recovery.

---

## How to refresh the Q ratios

```bash
conda activate /glade/work/bwest/conda-envs/droughts
cd /glade/derecho/scratch/bwest/drought-ensemble
# Re-run the inline script that wrote figures/_data/outlet_flow_recovery_ratios_50yr.json
# (or extend redo_recovery_with_50yr.py to emit mean/p50/p90/p99/max ratios).
```

Potomac 50-yr recovery years sit past `short_baseline`; ratios remap onto short-baseline years 50–54 (same convention as storage recovery plots).
