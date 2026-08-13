# Persistent storage vs streamflow (50-year droughts)

**Date:** August 2026  
**Question:** After 50-year droughts, is there finally enough persistent storage loss to affect streamflow — especially baseflow?  
**Verdict:** Persistent deep storage grows a lot; outlet streamflow does **not** track that growth. Only a **mild residual** remains in recovery, and it is **not** a clean baseflow collapse.

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

Figures: `figures/fifty_year_drought_streamflow_storage.png`, `figures/drought_recovery_totals_and_anomalies.png`, shallow/deep partition in `shallow_deep_shielding_summary.md`.

---

## What that does (and does not) do to streamflow

### During the drought

Outlet Q **steps down** when dry forcing starts and then **plateaus**. Storage continues to ratchet down for decades **without** a matching gradual decline in outlet flow. Accumulating deep losses are largely **decoupled from Q** mid-drought.

### Recovery (outlet Q / same-phase baseline)

Cached ratios: [`figures/outlet_flow_recovery_ratios_50yr.json`](figures/outlet_flow_recovery_ratios_50yr.json).

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

---

## Interpretation

1. **50-yr strengthens the storage story** — deep persistent memory is real and large.
2. **50-yr also strengthens the shielding / connected-limb story** — Q does not follow the deep drain.
3. Theory was right that **peaks** track the temporary limb (fast recovery).
4. Theory that persistent losses would **mainly show up as baseflow damage** is **not strongly supported** here: residual Q effects exist but are subtle, clearest as Potomac mean/p90 residue, not a dramatic baseflow fingerprint.

---

## How to refresh the Q ratios

```bash
conda activate /glade/work/bwest/conda-envs/droughts
cd /glade/derecho/scratch/bwest/drought-ensemble
# Re-run the inline script that wrote figures/outlet_flow_recovery_ratios_50yr.json
# (or extend redo_recovery_with_50yr.py to emit mean/p50/p90/p99/max ratios).
```

Potomac 50-yr recovery years sit past `short_baseline`; ratios remap onto short-baseline years 50–54 (same convention as storage recovery plots).
