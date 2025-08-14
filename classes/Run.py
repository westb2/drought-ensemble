import hashlib
import os
import shutil
import parflow as pf
import numpy as np
import pandas as pd
import json

# define a class called Run
class Run:
    def __init__(self, sequence_file=None, sequence=None, domain=None):
        self.TESTING = domain.TESTING if domain else False
        if sequence_file:
            self.sequence = self.get_sequence_from_file(sequence_file)
        elif sequence:
            if isinstance(sequence, str):
                self.sequence = self.get_sequence_from_file(sequence)
            else:
                self.sequence = sequence
        else:
            raise ValueError("Either sequence_file or sequence must be provided")
        self.number_of_years = len(self.sequence)
        self.domain = domain
        self.run_dir = self.get_run_folder()
        # Don't call get_output_folders() during initialization to avoid recursion


    def get_output_folders(self):
        output_folders = []
        for year in range(self.number_of_years):
            sub_sequence = self.sequence[:year+1]
            # Calculate run folder directly without creating a new Run object
            run_folder = self.get_run_folder_from_sequence(sub_sequence)
            output_folders.append(run_folder)
        return output_folders

    def get_sequence_from_file(self, sequence_file):
        with open(sequence_file, 'r') as file:
            sequence = json.load(file)["years"]
        return sequence


    def sequence2string(self, sequence):
        return "_".join([f"{year['wetness']}_{year['pumping_rate_fraction']}_{year['irrigation']}" for year in sequence])


    def hash_sequence(self, sequence):
        return hashlib.sha256(self.sequence2string(sequence).encode()).hexdigest()

    def get_run_folder_from_sequence(self, sequence):
        return os.path.join(self.domain.directory, "runs", self.hash_sequence(sequence))

    def get_run_folder(self):
        return self.get_run_folder_from_sequence(self.sequence)

    def run_exists(self):
        return os.path.exists(self.get_run_folder_from_sequence(self.sequence))   

    def get_initial_pressure_file(self):
        previous_run = Run(sequence=self.sequence[:-1], domain=self.domain)
        # left justify to get the last timestamp with up to 4 0s
        ending_timestamp = str(int(self.domain.num_output_files)).zfill(5)
        return os.path.join(previous_run.run_dir, f"run.out.press.{ending_timestamp}.pfb")


    def run_full_sequence(self):
        self.domain.get_domain()
        for year in range(len(self.sequence)):
            sub_run = Run(sequence=self.sequence[:year+1], domain=self.domain)
            if not sub_run.run_exists():
                if year>0:
                    sub_run.run_year(INITIAL_PRESSURE_FILE = sub_run.get_initial_pressure_file())
                else:
                    sub_run.run_year()
        print(f"Running {self.sequence2string(self.sequence)}")

    
    def run_year(self, flux_cycling=False, pumping_layer=4, flux_time_series=False, 
            years = 1, INITIAL_PRESSURE_FILE=None):
        # os.chdir(f"/Users/ben/Documents/GitHub/drought-ensemble/{run_dir}")
        # for now set consumptive use to 1 inch per week
        # TODO figure out if this is the right number
        run_specs = self.sequence[-1]
        irrigation = run_specs["irrigation"] == "True"
        pumping_rate_fraction = run_specs["pumping_rate_fraction"]
        year_wetness = run_specs["wetness"]
        shutil.copytree(f"{self.domain.get_base_run_folder(year_wetness)}", self.run_dir)
        os.chdir(self.run_dir)
        # Write the sequence to a file
        with open("sequence.json", "w") as f:
            json.dump(self.sequence, f)
        shutil.copyfile(self.domain.config_file, f"{self.run_dir}/config_at_time_of_run.ini")
        if irrigation:
            os.remove("./drv_vegp.dat")
            shutil.copyfile("./drv_vegp_for_irrigation.dat", "./drv_vegp.dat")
        model = pf.Run.from_definition("./run.yaml")
        model.TimingInfo.StartCount = 0
        if pumping_rate_fraction > 0.0:
            model = self.add_pumping_to_model(model,
                            pumping_rate_fraction=pumping_rate_fraction, 
                            irrigation=irrigation, flux_cycling=flux_cycling, 
                            pumping_layer=pumping_layer, flux_time_series=flux_time_series,
                            start_time=0, end_time=self.domain.stop_time * years)
        model.run_dir = os.getcwd()
        model.TimingInfo.DumpInterval = self.domain.dump_interval
        model.Solver.CLM.CLMDumpInterval = self.domain.dump_interval
        model.TimingInfo.StopTime = self.domain.stop_time
        if INITIAL_PRESSURE_FILE is not None:
            model.Geom.domain.ICPressure.FileName = INITIAL_PRESSURE_FILE
            # run.ICPressure.FileFormat = "ParFlowBinary"
        model.write("run", file_format="yaml")
        model.run()


    def add_pumping_to_model(self, model, pumping_rate_fraction=1.,
                    irrigation=False, flux_cycling=False, pumping_layer=2, flux_time_series=False,
                    start_time=0, end_time=8760):
        data_accessor = model.data_accessor
        shutil.copyfile(f"{self.run_dir}/mask.pfb", f"{self.run_dir}/{model.get_name()}.out.mask.pfb")
        domain_mask = np.where(data_accessor.mask > 0, 1, 0)
        # mask = np.where(data_accessor.mask > 0, 1, np.nan)
        pumping_layer = 2
        df = pd.read_csv(f"{self.run_dir}/drv_vegm.dat", sep=' ', skiprows=1)
        df.rename(columns={'Unnamed: 0': 'x', 'Unnamed: 1': 'y',}, inplace=True)
        df["is_cropland"] = df["12"] + df["14"]
        irrigation_mask = np.zeros(domain_mask.shape)
        for index, row in df.iterrows():
            if row["is_cropland"] > 0:
                irrigation_mask[0, int(row["y"])-1, int(row["x"])-1] = 1
        irrigation_mask = irrigation_mask * domain_mask

        nz, ny, nx = data_accessor.shape
        dz = data_accessor.dz
        print(f"dz: {dz}")
        fluxes = np.zeros((nz, ny, nx))
        # generate a random number between 0 and 2
        #to add wells ~30 meters down we need to add them to the third from the bottom layer
        if irrigation:
            # if we are doing irrigation because we estimate based off consumptive use we need to do more pumping
            fluxes[pumping_layer,:,:] = -1.3/dz[pumping_layer]
        else:
            fluxes[pumping_layer,:,:] = -1.0/dz[pumping_layer]

        fluxes = fluxes * irrigation_mask
        pumped_area_fraction = self.calculate_pumped_area_fraction("12")
        actual_pumping_rate = 1.0 * pumped_area_fraction * pumping_rate_fraction
        fluxes = fluxes * actual_pumping_rate
        print(f"actual pumping rate: {actual_pumping_rate}")
        if irrigation:
            model = self.add_irrigation_to_model(model, actual_pumping_rate)
        # print(wells[5,20:30,20:30])
        # pf.write_pfb(f"{self.run_dir}/fluxes_on.pfb", fluxes*1.0, p=config.P, q=config.Q, dist=True)
        # if not flux_cycling:
            # if flux_time_series:
            #     print("WHOOPS NONONONONONONON\n")
            #     pf.write_pfb(f"{self.run_dir}/fluxes.pfb", fluxes*1.0, p=config.P, q=config.Q, dist=True)
            #     for timestep, _ in enumerate(range(start_time, end_time, int(run.TimeStep.Value))):
            #         timestep_string = str(timestep).zfill(5)
            #         os.symlink(f"{self.run_dir}/fluxes.pfb", f"{self.run_dir}/fluxes.{timestep_string}.pfb")
            #         os.symlink(f"{self.run_dir}/fluxes.pfb.dist", f"{self.run_dir}/fluxes.{timestep_string}.pfb.dist")
            #     run.Solver.EvapTransFileTransient = True
            #     run.Solver.EvapTrans.FileName = f"{self.run_dir}/fluxes"
            # else:
        pf.write_pfb(f"{self.run_dir}/fluxes_on.pfb", fluxes*1.0, p=self.domain.P, q=self.domain.Q, dist=True)
        model.Solver.EvapTransFile = True
        model.Solver.EvapTrans.FileName = f"{self.run_dir}/fluxes_on.pfb"
        # else:
        #     pf.write_pfb(f"{run_dir}/fluxes_off.pfb", fluxes*0.0, p=config.P, q=config.Q, dist=True)
        #     fluxes_are_on = True
        #     pf.write_pfb(f"{run_dir}/fluxes_on.pfb", fluxes*2.0, p=config.P, q=config.Q, dist=True)
        #     for timestep, _ in enumerate(range(0, int(run.TimingInfo.StopTime)+2, int(run.TimeStep.Value))):
        #         # We apply the pumping for half the day
        #         if timestep%12 == 0:
        #             fluxes_are_on = not fluxes_are_on
        #         timestep_string = str(timestep).zfill(5)
        #         if fluxes_are_on:
        #             pf.write_pfb(f"{run_dir}/fluxes.{timestep_string}.pfb", fluxes*2.0, p=config.P, q=config.Q, dist=True)
        #             # os.symlink(f"{run_dir}/fluxes_on.pfb", f"{run_dir}/fluxes.{timestep_string}.pfb")
        #             # os.symlink(f"{run_dir}/fluxes_on.pfb.dist", f"{run_dir}/fluxes.{timestep_string}.pfb.dist")
        #         else:
        #             pf.write_pfb(f"{run_dir}/fluxes.{timestep_string}.pfb", fluxes*0.0, p=config.P, q=config.Q, dist=True)
        #             # os.symlink(f"{run_dir}/fluxes_off.pfb", f"{run_dir}/fluxes.{timestep_string}.pfb")
        #             # os.symlink(f"{run_dir}/fluxes_off.pfb.dist", f"{run_dir}/fluxes.{timestep_string}.pfb.dist")
        #     run.Solver.EvapTransFileTransient = True
        #     run.Solver.EvapTrans.FileName = f"{run_dir}/fluxes"
        model.write("run_with_pumping", file_format="yaml")
        return model
        # run.run(working_directory=run_dir)

    def calculate_pumped_area_fraction(self, cropland_index="12"):
        # TODO switch to below
        # from parflow.tools.io import read_pfb,write_pfb, read_clm
        # ucrb_mask = read_pfb('/hydrodata/temp/UCRB_nj/FromCheyenne/UCRB_spinup/WY2003_spinup/inputs_master/mask.pfb')
        # surf_mask = ucrb_mask.squeeze()
        # ucrb_cropland = (vegm[:,:,16] +vegm[:,:,18]  ) * surf_mask 
        domain_mask = pf.read_pfb(f'{self.run_dir}/mask.pfb')
        landcover_type = pd.read_csv(f"{self.run_dir}/drv_vegm.dat", sep=' ', skiprows=1)
        landcover_type.rename(columns={'Unnamed: 0': 'x', 'Unnamed: 1': 'y',}, inplace=True)
        landcover_type["is_cropland"] = landcover_type["12"] + landcover_type["14"]
        irrigation_mask = np.zeros(domain_mask.shape)
        for _, row in landcover_type.iterrows():
            if row["is_cropland"] > 0:
                irrigation_mask[0, int(row["y"])-1, int(row["x"])-1] = 1
        irrigation_mask = irrigation_mask * domain_mask
        pumped_area = irrigation_mask.sum()
        total_area = domain_mask[0].sum()
        pumped_area_fraction = pumped_area/total_area
        print(f"total area: {total_area}")
        print(f"pumped area: {pumped_area}")
        print(f"pumped area fraction: {pumped_area_fraction}")
        return pumped_area_fraction

    def add_irrigation_to_model(self, model, pumping_rate):
        # convert pumping rate from m^3/day to mm/s, grid cells are 1000m x 1000m
        # go from m/h to mm/s  = 1/1000/3600
        MM_PER_M = 1000.0
        SECONDS_PER_HOUR = 3600.0
        RETURN_FLOW_FRACTION = 0.3
        FRACTION_OF_DAY_IRRIGATING = 0.5
        CONVERSION_FACTOR = SECONDS_PER_HOUR/MM_PER_M*RETURN_FLOW_FRACTION/FRACTION_OF_DAY_IRRIGATING
        irrigation_rate = pumping_rate*CONVERSION_FACTOR
        model.Solver.CLM.IrrigationTypes = "Drip"
        model.Solver.CLM.IrrigationCycle = "Constant"
        model.Solver.CLM.IrrigationRate = irrigation_rate
        model.Solver.CLM.IrrigationStart = 800
        model.Solver.CLM.IrrigationStop = 2000
        return model