import os
import sys  
import parflow as pf
import shutil
import numpy as np
import xarray as xr
import json

# Hydrology functions are available but not currently used in this class
# from parflow.tools.hydrology import calculate_surface_storage, calculate_subsurface_storage, \
#     calculate_water_table_depth, calculate_evapotranspiration, calculate_overland_flow_grid

import xarray

class RunOutputReader:
    def __init__(self, run):
        self.run = run
        data_accessor = self.get_data_accessor(self.run.get_output_folders()[0])
        self.domain_attributes = {}

        self.domain_attributes["mask"] = data_accessor.mask
        # make the mask only contain 1s and nans
        self.domain_attributes["mask"] = np.where(self.domain_attributes["mask"] > 0, 1, np.nan)
        # run_def["porosity"] = data_accessor.computed_porosity
        self.domain_attributes["dx"] = data_accessor.dx
        self.domain_attributes["dy"] = data_accessor.dy
        dz_vals = [1.0,0.5,0.25,0.125,0.05,0.025,0.005,0.003,0.0015, 0.0005]
        self.domain_attributes["dz_array"] = np.array(dz_vals).reshape(10, 1, 1)
        self.domain_attributes["specific_storage"] = data_accessor.specific_storage
        self.domain_attributes["porosity"] = data_accessor.computed_porosity
        self.domain_attributes["mannings"] = data_accessor.mannings
        self.domain_attributes["slope_x"] = data_accessor.slope_x
        self.domain_attributes["slope_y"] = data_accessor.slope_y


    def get_data_accessor(self, run_dir):
        data_accessor = pf.Run.from_definition(f'{run_dir}/run.yaml').data_accessor
        shutil.copyfile(f'{run_dir}/mannings.pfb', f'{run_dir}/run.out.mannings.pfb')
        return data_accessor

    def read_output(self, save_to_file=False):
        pressure_files = []
        saturation_files = []
        output_folders = self.run.get_output_folders()
        
        for _, output_folder in zip(self.run.sequence["years"], output_folders):
            # data_accessor = self.get_data_accessor(output_folder)
            pressure_files.extend([f'{output_folder}/run.out.press.{str(timestep).zfill(5)}.pfb' for timestep in range(1, self.run.domain.num_output_files+1)])
            saturation_files.extend([f'{output_folder}/run.out.satur.{str(timestep).zfill(5)}.pfb' for timestep in range(1, self.run.domain.num_output_files+1)])
        
        pressure = pf.read_pfb_sequence(pressure_files)
        saturation = pf.read_pfb_sequence(saturation_files)
        # convert to xarray
        mask = xarray.DataArray(self.domain_attributes["mask"], dims=["z", "y", "x"],
                        coords={"z": range(self.domain_attributes["mask"].shape[0]), 
                        "y": range(self.domain_attributes["mask"].shape[1]), 
                        "x": range(self.domain_attributes["mask"].shape[2])})
        pressure = xarray.DataArray(pressure, dims=["time", "z", "y", "x"],
                        coords={"time": range(0,self.run.domain.num_output_files*self.run.number_of_years, 1), 
                        "z": range(pressure.shape[1]), 
                        "y": range(pressure.shape[2]), 
                        "x": range(pressure.shape[3])})*mask
        saturation = xarray.DataArray(saturation, dims=["time", "z", "y", "x"],
                        coords={"time": range(0,self.run.domain.num_output_files*self.run.number_of_years, 1), 
                        "z": range(saturation.shape[1]), 
                        "y": range(saturation.shape[2]), 
                        "x": range(saturation.shape[3])})*mask

        mannings = xarray.DataArray(self.domain_attributes["mannings"], dims=["z", "y", "x"],
                        coords={"z": range(self.domain_attributes["mannings"].shape[0]), 
                        "y": range(self.domain_attributes["mannings"].shape[1]), 
                        "x": range(self.domain_attributes["mannings"].shape[2])})*mask

        porosity = xarray.DataArray(self.domain_attributes["porosity"], dims=["z", "y", "x"],
                        coords={"z": range(self.domain_attributes["porosity"].shape[0]), 
                        "y": range(self.domain_attributes["porosity"].shape[1]), 
                        "x": range(self.domain_attributes["porosity"].shape[2])})*mask


        data_array = xarray.Dataset({"pressure": pressure, "saturation": saturation, "mask": mask, "mannings": mannings}, attrs={"sequence_name": self.run.sequence["name"]})
        data_array.info()
        # save to netcdf
        # pressure.to_netcdf(f'{self.run.get_output_folders()[0]}/run.out.pressure.nc')
        if save_to_file:
            os.makedirs(f'{self.run.output_root}/processed_full_runs', exist_ok=True)
            output_path = f'{self.run.output_root}/{self.run.domain.name}/processed_full_runs/{self.run.sequence["name"]}'
            os.makedirs(output_path, exist_ok=True)
            data_array.to_netcdf(os.path.join(output_path, "run.out.nc"))
            json.dump(self.run.sequence, open(os.path.join(output_path, "sequence.json"), "w"))
            print(f"Saved condensed output to {output_path}")
        return data_array
