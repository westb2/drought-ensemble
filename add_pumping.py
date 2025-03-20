import pandas as pd
import shutil
import numpy as np
import parflow as pf
import gila.config as config
import os


'''rate should be in m^3/day and at the grid cell level'''
def add_pumping(run, pumping_rate, run_dir, pumping_rate_fraction=1.,irrigation=False, cropland_index="12"):
    data_accessor = run.data_accessor
    shutil.copyfile(f"{run_dir}/mask.pfb", f"{run_dir}/{run.get_name()}.out.mask.pfb")
    domain_mask = np.where(data_accessor.mask > 0, 1, 0)
    # mask = np.where(data_accessor.mask > 0, 1, np.nan)

    df = pd.read_csv(f"{run_dir}/drv_vegm.dat", sep=' ', skiprows=1)
    df.rename(columns={'Unnamed: 0': 'x', 'Unnamed: 1': 'y',}, inplace=True)
    df["is_cropland"] = df[cropland_index]
    irrigation_mask = np.zeros(domain_mask.shape)
    for index, row in df.iterrows():
        if row["is_cropland"] > 0:
            irrigation_mask[0, int(row["y"])-1, int(row["x"])-1] = 1
    irrigation_mask = irrigation_mask * domain_mask

    nz, ny, nx = data_accessor.shape
    dz = data_accessor.dz
    fluxes = np.zeros((nz, ny, nx))
    # generate a random number between 0 and 2
    #to add wells ~30 meters down we need to add them to the third from the bottom layer
    if irrigation:
        # fluxes[9,:,:] = .3/dz[9]
        fluxes[4,:,:] = -1/dz[4]
    else:
        # if we don't do irrigation estimate the effective pumping rate as 70% of the total
        fluxes[4,:,:] = -.7/dz[4]

    fluxes = fluxes * irrigation_mask
    pumped_area_fraction = calculate_pumped_area_fraction(run_dir, cropland_index)
    actual_pumping_rate = pumping_rate * pumped_area_fraction / pumped_area_fraction
    fluxes = fluxes * pumping_rate * actual_pumping_rate
    if irrigation:
        run = add_irrigation(run, actual_pumping_rate)
    # print(wells[5,20:30,20:30])
    pf.write_pfb(f"{run_dir}/fluxes_on.pfb", fluxes*2.0, p=config.P, q=config.Q, dist=True)
    pf.write_pfb(f"{run_dir}/fluxes_off.pfb", fluxes*0.0, p=config.P, q=config.Q, dist=True)
    fluxes_are_on = True
    for timestep, _ in enumerate(range(0, int(run.TimingInfo.StopTime)+2, int(run.TimeStep.Value))):
        # We apply the pumping for half the day
        if timestep%12 == 0:
            fluxes_are_on = not fluxes_are_on
        timestep_string = str(timestep).zfill(5)
        if fluxes_are_on:
            os.symlink(f"{run_dir}/fluxes_on.pfb", f"{run_dir}/fluxes.{timestep_string}.pfb")
            os.symlink(f"{run_dir}/fluxes_on.pfb.dist", f"{run_dir}/fluxes.{timestep_string}.pfb.dist")
        else:
            os.symlink(f"{run_dir}/fluxes_off.pfb", f"{run_dir}/fluxes.{timestep_string}.pfb")
            os.symlink(f"{run_dir}/fluxes_off.pfb.dist", f"{run_dir}/fluxes.{timestep_string}.pfb.dist")
    run.Solver.EvapTransFileTransient = True
    run.Solver.EvapTrans.FileName = f"{run_dir}/fluxes"
    run.write("run", file_format="yaml")
    return run
    # run.run(working_directory=run_dir)

def calculate_pumped_area_fraction(run_dir, cropland_index):
    domain_mask = pf.read_pfb(f'{run_dir}/mask.pfb')
    landcover_type = pd.read_csv(f"{run_dir}/drv_vegm.dat", sep=' ', skiprows=1)
    landcover_type.rename(columns={'Unnamed: 0': 'x', 'Unnamed: 1': 'y',}, inplace=True)
    landcover_type["is_cropland"] = landcover_type[cropland_index]
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

def add_irrigation(run, pumping_rate):
    # convert pumping rate from m^3/day to mm/s, grid cells are 1000m x 1000m
    # go from m/h to mm/s  = 1/1000/3600
    MM_PER_M = 1000.0
    SECONDS_PER_HOUR = 3600.0
    RETURN_FLOW_FRACTION = 0.3
    FRACTION_OF_DAY_IRRIGATING = 0.5
    CONVERSION_FACTOR = SECONDS_PER_HOUR/MM_PER_M*RETURN_FLOW_FRACTION/FRACTION_OF_DAY_IRRIGATING
    irrigation_rate = pumping_rate*CONVERSION_FACTOR
    run.Solver.CLM.IrrigationTypes = "Drip"
    run.Solver.CLM.IrrigationCycle = "Constant"
    run.Solver.CLM.IrrigationRate = irrigation_rate
    run.Solver.CLM.IrrigationStart = 800
    run.Solver.CLM.IrrigationStop = 2000
    return run