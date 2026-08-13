# Local Budyko framing of temporary vs persistent deficits

**Script:** [`budyko_temp_persistent.py`](budyko_temp_persistent.py)  
**Figures:** `analysis/figures/budyko_*.png`  
**Tables:** `budyko_temp_persistent_spearman.csv`, `budyko_temp_persistent_summary.json`

## Definitions

| Quantity | Source |
|----------|--------|
| Temporary / persistent storage | Same as recovery analysis: recovered in recovery yr1 vs remaining |
| Temporary fraction \(f_\mathrm{temp}\) | \(S_\mathrm{temp}/(S_\mathrm{temp}+S_\mathrm{pers})\) |
| Aridity \(\phi\) | Hamon PET / CW3E APCP (average forcing year) |
| Overland participation | Fraction of 219 h steps with \(Q_\mathrm{ol}>1\) m³/h (late-spinup mean) |
| Strata | Stream (top 3% flow); near (≤2 km); upland (dist>5 km + deep WTD tercile); mid = rest |

## Verdict

The temporary/persistent split behaves like a **local, connectivity-weighted Budyko analogue**, but **not** as a classical within-basin climate Budyko:

1. **Between domains**, climate aridity lines up with the story: Wolf is uniformly energy-limited (\(\phi\approx0.64\), high \(f_\mathrm{temp}\)); Potomac sits near the energy/water threshold (\(\phi\approx0.90\), more persistent memory).
2. **Within domains**, \(\phi\) barely varies (esp. Wolf), so cell-scale climate cannot explain temporary vs persistent. **Baseline WTD + overland connectivity** do — the “local energy-limited” end is shallow, flow-connected storage; the “local water-limited” end is deep-WTD upland storage.
3. **Persistent deficit growth with drought length** is strongest in uplands (×3.1–3.6 from 10→50 yr) and weakest in streams (×1.4–2.0) — the slow, recharge-limited branch.

## Key numbers

| Domain | \(\phi\) mean [p05–p95] | P / PET (mm) | Stream \(f_\mathrm{temp}\) 10→50 | Upland \(f_\mathrm{temp}\) 10→50 | Persist growth 50/10 (upland) |
|--------|-------------------------|--------------|----------------------------------|----------------------------------|-------------------------------|
| Potomac | 0.90 [0.62–1.11] | 792 / 703 | 0.66 → 0.57 | 0.27 → 0.14 | ×3.60 |
| Wolf | 0.64 [0.60–0.66] | 1532 / 974 | 0.49 → 0.44 | 0.55 → 0.37 | ×3.13 |

Within-domain Spearman vs \(f_\mathrm{temp}\) (non-stream cells):

- **Wolf:** baseline WTD \(\rho\approx-0.53\); overland flow/participation \(\rho\approx+0.25\)–\(0.30\); \(\phi\) weak.
- **Potomac:** all cellwise \(|\rho|<0.14\) for \(f_\mathrm{temp}\); but **persistent magnitude** strongly anti-correlates with overland (\(\rho\approx-0.48\)).

Pooled hexbins mix domains, so \(\phi\)–\(f_\mathrm{temp}\) \(\rho\approx-0.33\) is mostly the Wolf-vs-Potomac contrast.

## Figures

| File | What it shows |
|------|----------------|
| `budyko_phi_vs_overland_hist.png` | \(\phi\) nearly uniform in Wolf; Potomac spans ~0.6–1.2. Overland participation is the spatially rich axis. |
| `budyko_maps_phi_overland_ftemp.png` | Maps of \(\phi\), participation, \(f_\mathrm{temp}\) (10 & 50 yr). |
| `budyko_hexbin_ftemp_vs_predictors.png` | \(f_\mathrm{temp}\) vs \(\phi\), participation, WTD, stream distance. |
| `budyko_space_ftemp.png` | Local Budyko space \((\phi,\,Q_\mathrm{ol}/P)\) colored by \(f_\mathrm{temp}\). |
| `budyko_stratified_temp_persist_bars.png` | Absolute temp/persist volume by stratum × drought length. |
| `budyko_ftemp_by_stratum.png` | Mean \(f_\mathrm{temp}\) by stratum vs length (clearest landscape test). |
| `budyko_spearman_ftemp.png` | Within-domain Spearman heatmap. |

## Interpretation notes

- Absolute temporary volume is largest in **mid-landscape** because that is most of the area; stream cells are small but (on Potomac) have the highest *fraction* temporary.
- Wolf’s temporary pulse is a **wet-landscape** feature (near/mid), not only the channel mask — consistent with a broader energy-limited, export-connected storage zone.
- Classical Budyko language fits best as: **domain climate sets the baseline regime; local “Budyko” is WTD–overland position along the export vs recharge continuum.**
