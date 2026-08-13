# Near-surface vs deep storage shielding

Near-surface = CONUS2 layers **z≥6** (top **2 m**, GWMM unconfined). Deep = **z&lt;6**.

**Claim tested:** places whose drought losses stay near the surface regenerate those losses on precip pulses *during* drought, so the losses remain temporary and the column is shielded from persistent (deep) drawdown.

Script: `analysis/shallow_deep_shielding.py`

## Aggregate: temporary ≈ near-surface, persistent ≈ deep

| Domain | Drought | % of temporary in near-surface | % of persistent in deep |
|--------|---------|-------------------------------:|------------------------:|
| Potomac | 1 / 3 / 10 / 50 yr | 80 / 80 / 80 / 78% | 43 / 52 / 74 / **92%** |
| Wolf | 1 / 3 / 10 / 50 yr | **100 / 99 / 97 / 94%** | **94 / 97 / 98 / 99%** |

Temporary volume **saturates** by ~3–10 yr (Wolf ≈125×10⁶ m³; Potomac ≈80×10⁶ m³), almost all near-surface. Persistent volume **keeps growing**, and that growth is almost entirely deep (Wolf 50-yr persistent ≈216×10⁶ m³ deep vs 3×10⁶ near-surface).

![Temporary vs persistent partitioned into near-surface and deep](drought-ensemble/analysis/figures/shallow_deep_temp_persist_partition.png)

![Layer recovery profile for 10-year drought](drought-ensemble/analysis/figures/shallow_deep_layer_recovery_profile_10yr.png)

Year-1 recovery fraction ≈1 in the top 2 m, ≪1 below.

## Spatial (10-yr)

![Near-surface vs deep deficits and temporary fraction maps](drought-ensemble/analysis/figures/shallow_deep_spatial_10yr.png)

Bottom two rows are nearly interchangeable: **fraction of deficit in near-surface** vs **temporary fraction**. Spearman (non-stream cells with deficit):

| Domain | ρ(f_near-surface, f_temp) | ρ(deep, persistent) | ρ(near-surface, temporary) |
|--------|--------------------------:|--------------------:|---------------------------:|
| Potomac | 0.85 | 0.93 | 0.84 |
| Wolf | 0.99 | 0.99 | 0.97 |

Wolf’s map is mostly near-surface / temporary; Potomac’s uplands are deep / persistent, with near-surface temporary limbs along flow-connected corridors — same geography as the Budyko local framing.

## Mid-drought regeneration

![Mid-drought near-surface regeneration vs deep drawdown](drought-ensemble/analysis/figures/shallow_deep_mid_drought_regen.png)

![Drought year 5 precip and storage pulse response](drought-ensemble/analysis/figures/shallow_deep_mid_drought_year_pulse.png)

Near-surface ΔS oscillates toward zero every year of the drought; deep ΔS ratchets down. In drought year 5 of 10, near-surface tracks P while deep stays flat.

10-yr pooled 219 h windows (stats; see also year-pulse figure):

| Domain | Wet-window ΔS near-surface | Wet-window ΔS deep | ρ(P, ΔS_ns) | ρ(P, ΔS_deep) |
|--------|---------------------------:|-------------------:|------------:|--------------:|
| Potomac | +72×10⁶ m³ | −0.2×10⁶ m³ | 0.75 | 0.00 |
| Wolf | +21×10⁶ m³ | −0.2×10⁶ m³ | 0.68 | −0.02 |

## Read with Budyko framing

Local energy-limited / high-overland cells are the near-surface temporary limb: they “pay” drought with a regenerating skin of storage. Local water-limited / deep-WTD cells drain below 2 m; those losses never see the pulse recovery and become the persistent aggregate.
