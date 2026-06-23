# CONUS2 depth to bedrock (Shangguan)

HydroData / subsettools expose the Shangguan et al. depth-to-bedrock product on the CONUS2 grid as:

| HydroData variable | ParFlow input | Source file on HydroData |
|--------------------|---------------|-------------------------|
| `pf_flowbarrier`   | FlowBarrierZ / depth to bedrock | `CONUS2.0.Shangguan_200m_FBZ.pfb` |

Dataset: `conus2_domain`, grid: `conus2` (1 km, 4442 × 3256 × 10 layers).

There is **no separate dataset name** containing “Shangguan” in the HydroData catalog besides this variable. Global 250 m DTB from the paper is not served as a separate gridded product here; CONUS2 uses the HydroFrame regridded 200 m flow-barrier field.

**CONUS1** (`conus1_domain`) does **not** include `pf_flowbarrier` (subsettools docs: omit it for CONUS1).

## Files in this directory

- `pf_flowbarrier.pfb` — full CONUS2 download via `subsettools.subset_static(..., var_list=("pf_flowbarrier",))`
- `CONUS2.0.Shangguan_200m_FBZ.pfb` — symlink to the same file (HydroData filename)

## Re-download (subsettools)

```python
import subsettools as st

ij_bounds = (0, 0, 4442, 3256)
st.subset_static(
    ij_bounds,
    dataset="conus2_domain",
    write_dir=".",
    var_list=("pf_flowbarrier",),
)
```
