import xarray as xr
import os   
import parflow as pf
import plotly.express as px
from parflow.tools.hydrology import calculate_overland_flow_grid, calculate_subsurface_storage, calculate_water_table_depth
import numpy as np
import shutil
import json
import plotly.io as pio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ensemble_running.hourly_year import close_hourly_year, open_hourly_year, open_hourly_paths


ONE_YEAR = 8760
SIMULATION_START_YEAR = 9
SIMULATION_START_TIME = ONE_YEAR*SIMULATION_START_YEAR
PERTURBATION_START_YEAR = 10
PERTURBATION_START_TIME = ONE_YEAR*PERTURBATION_START_YEAR
PUMPING_END_YEAR = 15
PUMPING_END_TIME = ONE_YEAR*PUMPING_END_YEAR
RECOVERY_DURATION_YEARS = 10
PUMPING_RECOVERY_END_YEAR = PUMPING_END_YEAR + RECOVERY_DURATION_YEARS
PUMPING_RECOVERY_END_TIME = ONE_YEAR*PUMPING_RECOVERY_END_YEAR



# Potomac outlet
DOMAIN = "potomac_without_flow_barrier"
DOMAIN_2 = "potomac"
OUTLET_X = 66
OUTLET_Y = 135


def _file_locations(ensemble_name, ensemble_member, domain, start_year=0, interval=None):
    """Load ordered yearly NetCDF paths for an ensemble member.

    Parameters
    ----------
    interval : int or None
        If None, use hourly ``file_locations.json`` (``derived_hourly.nc`` or
        legacy ``processed_output.nc``). If an int (e.g. 219), use
        ``file_locations_{interval}h.json`` written by
        ``ensemble_running/consolidate_to_interval.py``.
    """
    root_dir = "/glade/derecho/scratch/bwest/drought-ensemble"
    name = (
        "file_locations.json"
        if interval is None
        else f"file_locations_{int(interval)}h.json"
    )
    loc_path = (
        f"{root_dir}/domains/{domain}/processed_full_runs/"
        f"{ensemble_name}/{ensemble_member}/{name}"
    )
    with open(loc_path) as f:
        return json.load(f)[start_year:]


def read_simulation_data(
    ensemble_name, ensemble_member, domain, start_year=0, interval=None
):
    """Open processed yearly outputs as a lazy xarray Dataset.

    Parameters
    ----------
    start_year : int
        Skip year files before this index (0-based). Time coords still count
        from the full-sequence origin, so year 40 is hour 40*ONE_YEAR even if
        earlier files were not opened.
    interval : int or None
        If None, open hourly products via ``file_locations.json`` (raw+sidecar
        merge, or legacy ``processed_output.nc``). If set (e.g. 219), open
        consolidated files via ``file_locations_{interval}h.json``. Time is
        still expressed in fractional years using
        ``steps_per_year = ONE_YEAR // interval`` (or ``ONE_YEAR`` when
        ``interval`` is None).
    """
    files = _file_locations(
        ensemble_name, ensemble_member, domain, start_year, interval=interval
    )
    if interval is None:
        data = open_hourly_paths(files)
    else:
        data = xr.open_mfdataset(files, concat_dim="time", combine="nested")
    steps_per_year = ONE_YEAR if interval is None else ONE_YEAR // int(interval)
    data = data.assign_coords(
        time=start_year + np.arange(len(data.time), dtype=np.float64) / steps_per_year
    )
    if "subsurface_storage" in data:
        data = data.rename({"subsurface_storage": "storage"})
    return data


def read_storage_outlet_series(
    ensemble_name,
    ensemble_member,
    domain,
    start_year=0,
    interval=2190,
    outlet_x=OUTLET_X,
    outlet_y=OUTLET_Y,
):
    """Year-by-year domain storage + outlet flow (small in-memory series).

    Opens one processed year at a time and only the needed variables, so long
    drought records stay cheap. ``interval`` is hours between samples
    (default ~quarterly).
    """
    files = _file_locations(ensemble_name, ensemble_member, domain, start_year)
    times = []
    storage = []
    outlet = []

    for year_offset, path in enumerate(files):
        ds = open_hourly_year(path)
        try:
            stor_name = (
                "subsurface_storage" if "subsurface_storage" in ds else "storage"
            )
            t_idx = np.arange(0, ds.sizes["time"], interval)
            stor = (
                ds[stor_name]
                .isel(time=t_idx)
                .sum(dim=("x", "y", "z"), skipna=True)
                .values
            )
            flow = (
                ds["overland_flow"]
                .isel(time=t_idx, x=outlet_x, y=outlet_y)
                .values
            )
        finally:
            close_hourly_year(ds)
        times.append(start_year + year_offset + t_idx / ONE_YEAR)
        storage.append(np.asarray(stor, dtype=np.float64))
        outlet.append(np.asarray(flow, dtype=np.float64))

    time = np.concatenate(times)
    return xr.Dataset(
        {
            "storage": ("time", np.concatenate(storage)),
            "outlet_flow": ("time", np.concatenate(outlet)),
        },
        coords={"time": time},
    )

def read_perturbation_data(ensemble_name, ensemble_member, domain, perturbation_length_years):
    data = read_simulation_data(ensemble_name, ensemble_member, domain)
    data = data.sel(year=slice(PERTURBATION_START_YEAR, PERTURBATION_START_YEAR + perturbation_length_years))
    return data

def read_recovery_data(ensemble_name, ensemble_member, domain, perturbation_length_years):
    data = read_simulation_data(ensemble_name, ensemble_member, domain)
    RECOVERY_START_YEAR = PERTURBATION_START_YEAR + perturbation_length_years
    RECOVERY_END_YEAR = RECOVERY_START_YEAR + RECOVERY_DURATION_YEARS
    data = data.sel(year=slice(RECOVERY_START_YEAR, RECOVERY_END_YEAR))
    return data
