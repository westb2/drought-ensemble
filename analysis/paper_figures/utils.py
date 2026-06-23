import xarray as xr
import os   
import parflow as pf
import plotly.express as px
from parflow.tools.hydrology import calculate_overland_flow_grid, calculate_subsurface_storage, calculate_water_table_depth
import numpy as np
import shutil
import json
import plotly.io as pio


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


def read_simulation_data(ensemble_name, ensemble_member, domain):
    root_dir = "/glade/derecho/scratch/bwest/drought-ensemble"
    files = json.load(open(f"{root_dir}/domains/{domain}/processed_full_runs/{ensemble_name}/{ensemble_member}/file_locations.json"))
    data = xr.open_mfdataset(files, concat_dim="time", combine="nested")
    # reindex the time dimension to follow the index
    data = data.assign_coords(  
        time=np.arange(len(data.time), dtype=np.float64) / ONE_YEAR
    )
    data = data.rename({"subsurface_storage": "storage"})
    return data.isel(time=slice(0, None))

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