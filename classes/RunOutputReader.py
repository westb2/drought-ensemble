import os
import sys  
import parflow as pf
import shutil
import numpy as np
import xarray as xr
import json

# Hydrology functions are available but not currently used in this class
from parflow.tools.hydrology import calculate_surface_storage, calculate_subsurface_storage, \
    calculate_water_table_depth, calculate_evapotranspiration, calculate_overland_flow_grid

import xarray

class RunOutputReader:
    def __init__(self, run):
        self.run = run
        self.processed_output_folder = self.run.processed_output_path


    def calculate_subsurface_storage_wrapper(self, porosity, pressure, saturation, specific_storage, dx, dy, mask):
        """Wrapper to make mask a positional argument"""
        dz = np.array([1.0, 0.5, 0.25, 0.125, 0.05, 0.025, 0.005, 0.003, 0.0015, 0.0005])  # 1D array of layer thicknesses
        dz = dz * 200
        return calculate_subsurface_storage(porosity, pressure, saturation, specific_storage, dx, dy, dz, mask=mask)


    def calculate_overland_flow_wrapper(self, pressure, slopex, slopey, mannings, dx, dy, mask):
        """Wrapper to make mask a positional argument"""
        return calculate_overland_flow_grid(pressure, slopex, slopey, mannings, dx, dy, mask=mask)


    def read_output_netcdf(self, save_to_file=False):
        output_folders = self.run.get_output_folders()
        datasets = []
        for output_folder in output_folders:
            
            data = xarray.open_dataset(os.path.join(output_folder, f"run.out.00001.nc"))
            datasets.append(data)


        data_array = xarray.concat(datasets, dim="time", combine_attrs="no_conflicts")
        run_input_data = xarray.open_dataset(os.path.join(output_folders[0], f"run.out.00000.nc"))
        data_array["mask"] = run_input_data.mask.isel(time=0)
        data_array["mannings"] = run_input_data.mannings.isel(time=0)
        data_array["porosity"] = run_input_data.porosity.isel(time=0)
        data_array["specific_storage"] = run_input_data.specific_storage.isel(time=0)
        data_array["DZ_Multiplier"] = run_input_data.DZ_Multiplier.isel(time=0)
        data_array["slopex"] = run_input_data.slopex.isel(time=0)
        data_array["slopey"] = run_input_data.slopey.isel(time=0)
        data_array["perm_x"] = run_input_data.perm_x.isel(time=0)
        data_array["perm_y"] = run_input_data.perm_y.isel(time=0)
        data_array["perm_z"] = run_input_data.perm_z.isel(time=0)


        overland_flow = xr.apply_ufunc(
            self.calculate_overland_flow_wrapper,
            data_array.pressure,           # (time, z, y, x)
            data_array.slopex,             # (y, x)
            data_array.slopey,             # (y, x)
            data_array.mannings,           # (y, x)
            1000,                    # scalar dx
            1000,                    # scalar dy
            data_array.mask,               # (z, y, x)
            input_core_dims=[['z', 'y', 'x'], ['y', 'x'], ['y', 'x'], ['y', 'x'], [], [], ['z', 'y', 'x']],
            output_core_dims=[['y', 'x']],
            vectorize=True
        )
        data_array["overland_flow"] = overland_flow

        subsurface_storage = xr.apply_ufunc(
            self.calculate_subsurface_storage_wrapper,
            data_array.porosity,           # (z, y, x)
            data_array.pressure,           # (time, z, y, x)
            data_array.saturation,         # (time, z, y, x)
            data_array.specific_storage,   # (z, y, x)
            1000,                    # scalar dx
            1000,                    # scalar dy
            data_array.mask,               # (z, y, x)
            input_core_dims=[['z', 'y', 'x'], ['z', 'y', 'x'], ['z', 'y', 'x'], ['z', 'y', 'x'], [], [], ['z', 'y', 'x']],
            output_core_dims=[['z', 'y', 'x']],  # Changed from ['y', 'x'] to ['z', 'y', 'x']
            vectorize=True
        )
        data_array["subsurface_storage"] = subsurface_storage

        data_array.info()
        if save_to_file:
            output_path = f'{self.run.processed_output_path}'
            os.makedirs(output_path, exist_ok=True)
            json.dump(self.run.sequence, open(os.path.join(output_path, "sequence.json"), "w"))
            
            # Ensure all variables are saved by setting unlimited_dims explicitly
            data_array.to_netcdf(os.path.join(output_path, "run.out.nc"))
            print(f"Saved condensed output to {output_path}")
        return data_array



    def get_data_accessor(self, run_dir):
        data_accessor = pf.Run.from_definition(f'{run_dir}/run.yaml').data_accessor
        shutil.copyfile(f'{run_dir}/mannings.pfb', f'{run_dir}/run.out.mannings.pfb')
        return data_accessor

    def read_output(self, save_to_file=False):
        if self.run.netcdf_output:
            return self.read_output_netcdf(save_to_file)
        else:
            return self.read_output_pfb(save_to_file)

    def read_output_pfb(self, save_to_file=False):
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

        self.domain_attributes["storage"] = data_accessor.storage

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
            output_path = f'{self.run.processed_output_path}'
            os.makedirs(output_path, exist_ok=True)
            data_array.to_netcdf(os.path.join(output_path, "run.out.nc"))
            json.dump(self.run.sequence, open(os.path.join(output_path, "sequence.json"), "w"))
            data_array.to_netcdf(os.path.join(output_path, "run.out.nc"))
            print(f"Saved condensed output to {output_path}")
        return data_array
