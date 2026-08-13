# Pumping: shallow/deep + fast-loss proxies (no recovery yet)

**Date:** August 2026  
**Script:** [`pumping_shallow_deep_proxies.py`](pumping_shallow_deep_proxies.py)  

Recovery years are not on disk, so temporary/persistent cannot be defined
from recovery year 1. This early look asks whether **near-surface (fast /
regenerating)** vs **deep (slow / accumulating)** losses still diverge under
pumping — where extraction is applied at **layer 2 (deep)**, including in
high water-availability cells.

## Proxies

| Proxy | Definition |
|-------|------------|
| Near-surface / deep deficit | End-pump column deficit split at 2 m (z≥6 vs z<6) |
| Mid-pump regen | Near-surface ΔS pulses with average-year P; deep ΔS ratchets |
| Fast / temp proxy | Mean mid-year near-surface rebound (max − year-start) |
| Persist-like proxy | Mean deep net loss per pump year |

Note: the drought-style onset-spike (project slow branch to t=0) is ~0 under
pumping — deficit grows from near zero — so seasonal rebound is the useful
fast-loss stand-in until recovery years exist.

## Figures

- [pumping_shallow_deep_mid_pump_regen.png](figures/pumping_shallow_deep_mid_pump_regen.png)
- [pumping_shallow_deep_mid_pump_year_pulse.png](figures/pumping_shallow_deep_mid_pump_year_pulse.png)
- [pumping_shallow_deep_end_deficit_partition.png](figures/pumping_shallow_deep_end_deficit_partition.png)
- [pumping_fast_regen_vs_deep_drawdown.png](figures/pumping_fast_regen_vs_deep_drawdown.png)
- [pumping_shallow_deep_spatial_end_yr3.png](figures/pumping_shallow_deep_spatial_end_yr3.png)

## End-of-pump depth partition (% of deficit in deep)

| Domain | Rate | End yr 1 % deep | End yr 3 % deep |
|--------|------|----------------:|----------------:|
| Potomac | 1e-07 | 80 | 91 |
| Potomac | 1e-06 | 96 | 98 |
| Potomac | 1e-05 | 98 | 99 |
| Potomac | 1e-04 | 100 | 100 |
| Wolf | 1e-07 | 71 | 86 |
| Wolf | 1e-06 | 94 | 96 |
| Wolf | 1e-05 | 96 | 97 |
| Wolf | 1e-04 | 99 | 99 |

## Mid-pump wet-window ΔS (pooled 219 h; 1e-5 m/h)

| Domain | Wet ΔS near-surface | Wet ΔS deep | ρ(P, ΔS_ns) | ρ(P, ΔS_deep) |
|--------|--------------------:|------------:|------------:|--------------:|
| Potomac | +0.4×10⁶ m³ | -7.1×10⁶ m³ | 0.62 | -0.01 |
| Wolf | +0.3×10⁶ m³ | -2.7×10⁶ m³ | 0.28 | -0.03 |

## Mid-year regen vs deep drawdown (10⁶ m³ / year mean)

| Domain | Rate | NS mid-year rebound | Deep net loss / yr |
|--------|------|--------------------:|-------------------:|
| Potomac | 1e-07 | 0.06 | 2.7 |
| Potomac | 1e-06 | 0.62 | 27.1 |
| Potomac | 1e-05 | 5.50 | 276.4 |
| Potomac | 1e-04 | 11.41 | 3055.6 |
| Wolf | 1e-07 | 0.06 | 1.0 |
| Wolf | 1e-06 | 0.50 | 9.8 |
| Wolf | 1e-05 | 4.16 | 103.2 |
| Wolf | 1e-04 | 11.47 | 1192.9 |

## Takeaways (early)

- **Potomac** mid-pump (1e-5): wet-window near-surface ΔS +0.4×10⁶ m³ vs deep -7.1×10⁶ m³ (ρ(P,ns)=0.62, ρ(P,deep)=-0.01).
- **Potomac** end-yr3 deficit is 91–100% deep across rates (extraction at layer 2; contrast drought where temporary ≈ near-surface).
- **Wolf** mid-pump (1e-5): wet-window near-surface ΔS +0.3×10⁶ m³ vs deep -2.7×10⁶ m³ (ρ(P,ns)=0.28, ρ(P,deep)=-0.03).
- **Wolf** end-yr3 deficit is 86–99% deep across rates (extraction at layer 2; contrast drought where temporary ≈ near-surface).
- **Potomac** (1e-5): mean near-surface mid-year rebound 5.5×10⁶ m³ vs deep net loss 276×10⁶ m³/yr — regenerating skin is tiny beside the deep ratchet.
- **Wolf** (1e-5): mean near-surface mid-year rebound 4.2×10⁶ m³ vs deep net loss 103×10⁶ m³/yr — regenerating skin is tiny beside the deep ratchet.
- Drought-style onset spike ≈ 0 under pumping (deficit grows from ~0); seasonal near-surface rebound is the better temporary proxy until recovery runs.

## Reproduce

```bash
conda activate /glade/work/bwest/conda-envs/droughts
source ~/pf_env.sh
cd /glade/derecho/scratch/bwest/drought-ensemble
python analysis/pumping_shallow_deep_proxies.py
```
