import os
import numpy as np
import os
from parflow import Run

from parflow.tools.io import read_pfb, read_clm
from parflow.tools.fs import mkdir
from parflow.tools.settings import set_working_directory

import subsettools as st
import hf_hydrodata as hf
import configparser

# define a class called Domain
class Domain:
    def __init__(self, config_file, project_root="/glade/u/home/bwest/drought-ensemble", TESTING=False):
        
        
        self.config_file = config_file
        # if testing, only grab one day of data
        self.TESTING = TESTING
        self.DRY_WETNESS_TYPE = "dry"
        self.WET_WETNESS_TYPE = "wet"
        self.AVERAGE_WETNESS_TYPE = "average"
        self.project_root = project_root
        self.config = self.get_config()
        self.dump_interval = 1
        if self.TESTING:
            self.stop_time = 24
        else:
            self.stop_time = 8760
        # make each item in the config a class attribute
        for key in self.config['DEFAULT']:
            value = self.config.get('DEFAULT', key)
            # Keep certain fields as strings (identifiers, names, etc.)
            string_fields = ['huc_id', 'current_huc_id', 'current_reference_gage', 'name', 'domain_name', 'current_run_name']
            if key in string_fields:
                setattr(self, key, value)
            else:
                # Try to convert numeric values
                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    # Keep as string if conversion fails
                    pass
                setattr(self, key, value)
        
        # Ensure name attribute exists - use domain_name as fallback
        if not hasattr(self, 'name') or not self.name:
            if hasattr(self, 'domain_name') and self.domain_name:
                self.name = self.domain_name
            else:
                raise ValueError("Config file must contain either 'name' or 'domain_name' field")
                
        if TESTING:
            self.directory = os.path.join(self.project_root, "domains", self.name, "testing")
            self.dump_interval = 1
            self.stop_time = 24
        else:
            self.directory = os.path.join(self.project_root, "domains", self.name)
            self.dump_interval = 1
            self.stop_time = 8760
        self.num_output_files = (self.stop_time // self.dump_interval)
        self.inputs_directory = os.path.join(self.directory, "inputs")

    def get_config(self):
        config = configparser.ConfigParser()
        config.read(self.config_file)
        return config

    def get_domain(self):
        if not self.domain_exists(self.DRY_WETNESS_TYPE):
            self.get_domain_year(self.dry_year, self.DRY_WETNESS_TYPE)
        if not self.domain_exists(self.WET_WETNESS_TYPE):
            self.get_domain_year(self.wet_year, self.WET_WETNESS_TYPE)
        if not self.domain_exists(self.AVERAGE_WETNESS_TYPE):
            self.get_domain_year(self.average_year, self.AVERAGE_WETNESS_TYPE)

    def domain_exists(self, wetness_type):
        runname = f"{self.name}_{wetness_type}"
        print(os.path.join(self.inputs_directory, runname))
        return os.path.exists(os.path.join(self.inputs_directory, runname))

    def get_base_run_folder(self, wetness_type):
        return os.path.join(self.inputs_directory, f"{self.name}_{wetness_type}")
    
    def get_domain_folder(self, wetness_type):
        """Alias for get_base_run_folder for backward compatibility"""
        return self.get_base_run_folder(wetness_type)

    def get_domain_year(self, year, wetness_type):
         # You need to register on https://hydrogen.princeton.edu/pin before you can use the hydrodata utilities
        hf.register_api_pin("benjaminwest@arizona.edu", "7343")
        start_year = year
        end_year = year + 1
        runname = f"{self.name}_{wetness_type}"
        print(f"Getting domain for {runname}")
        # provide a way to create a subset from the conus domain (huc, lat/lon bbox currently supported)
        hucs = [self.huc_id]
        # provide information about the datasets you want to access for run inputs using the data catalog
        start_date = f"{start_year}-10-01"
        end_date = f"{end_year}-10-01"
        if self.TESTING:
            end_date = f"{year}-10-02"
        grid = "conus2"
        var_ds = "conus2_domain"
        forcing_ds = "CW3E"
        # cluster topology
        P = self.p
        Q = self.q

        # set the directory paths where you want to write your subset files
        input_dir = self.inputs_directory
        output_dir = self.inputs_directory
        static_write_dir = os.path.join(input_dir, "static")
        mkdir(static_write_dir)
        forcing_dir = os.path.join(input_dir, f"{runname}", "forcing")
        mkdir(forcing_dir)
        pf_out_dir = os.path.join(output_dir, f"{runname}")
        mkdir(pf_out_dir)
        
        # Debug: Print the actual paths being used
        print(f"DEBUG: RUN_DIR = {self.directory}")
        print(f"DEBUG: input_dir = {input_dir}")
        print(f"DEBUG: output_dir = {output_dir}")
        print(f"DEBUG: static_write_dir = {static_write_dir}")
        print(f"DEBUG: forcing_dir = {forcing_dir}")
        print(f"DEBUG: pf_out_dir = {pf_out_dir}")
        # load your preferred template runscript
        reference_run = st.get_template_runscript(grid, "transient", "solid", pf_out_dir)
        ij_bounds, mask = st.define_huc_domain(hucs=hucs, grid=grid)
        # os.environ["PARFLOW_DIR"] = "/Users/ben/parflow_installation/parflow"
        mask_solid_paths = st.write_mask_solid(mask=mask, grid=grid, write_dir=static_write_dir)
        static_paths = st.subset_static(ij_bounds, dataset=var_ds, write_dir=static_write_dir)
        clm_paths = st.config_clm(ij_bounds, start=start_date, end=end_date, dataset=var_ds, write_dir=static_write_dir)
        forcing_paths = st.subset_forcing(
            ij_bounds,
            grid=grid,
            start=start_date,
            end=end_date,
            dataset=forcing_ds,
            write_dir=forcing_dir,
            dataset_version="1.0"
        )
        os.chdir(static_write_dir)
        file_name = "pf_indicator.pfb"
        data = read_pfb(file_name)[7] 
        print(data.shape)

        runscript_path = st.edit_runscript_for_subset(
            ij_bounds,
            runscript_path=reference_run,
            runname="run",
            forcing_dir=forcing_dir,
        )
        st.copy_files(read_dir=static_write_dir, write_dir=pf_out_dir)
        init_press_path = os.path.basename(static_paths["ss_pressure_head"])
        depth_to_bedrock_path = os.path.basename(static_paths["pf_flowbarrier"])

        runscript_path = st.change_filename_values(
            runscript_path=runscript_path,
            init_press=init_press_path,
            depth_to_bedrock = depth_to_bedrock_path
        )
        runscript_path = st.dist_run(
            topo_p=P,
            topo_q=Q,
            runscript_path=runscript_path,
            dist_clim_forcing=True,
        )
        set_working_directory(f"{pf_out_dir}")
        print(f"Setting working directory to {pf_out_dir}")
        # load the specified run script
        run = Run.from_definition(runscript_path)
        run.TimingInfo.StopTime = self.stop_time
        run.TimingInfo.DumpInterval = self.dump_interval
        run.Solver.CLM.MetFileName = "CW3E"
        os.remove(runscript_path)
        runscript_path = runscript_path.replace(".yaml", "")
        run.write(runscript_path, file_format='yaml')
        print(f"Wrote runscript to {runscript_path}")
        print(f"Loaded run with runname: {run.get_name()}")