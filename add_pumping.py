import pandas as pd
import shutil
import numpy as np
import parflow as pf
import gila.config as config
import os


'''rate should be in m^3/day and at the grid cell level'''
def add_pumping(run, pumping_rate, run_dir, pumping_fraction=1.,irrigation=False):
    data_accessor = run.data_accessor
    shutil.copyfile(f"{run_dir}/mask.pfb", f"{run_dir}/{run.get_name()}.out.mask.pfb")
    domain_mask = np.where(data_accessor.mask > 0, 1, 0)
    # mask = np.where(data_accessor.mask > 0, 1, np.nan)

    df = pd.read_csv(f"{run_dir}/drv_vegm.dat", sep=' ', skiprows=1)
    df.rename(columns={'Unnamed: 0': 'x', 'Unnamed: 1': 'y',}, inplace=True)
    df["is_cropland"] = df["12"]+df["14"]
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
        fluxes[9,:,:] = .3/dz[9]
        fluxes[4,:,:] = -1/dz[4]
    else:
        # if we don't do irrigation estimate the effective pumping rate as 70% of the total
        fluxes[4,:,:] = -.7/dz[4]

    fluxes = fluxes * irrigation_mask
    fluxes = fluxes * pumping_rate * pumping_fraction
    # print(wells[5,20:30,20:30])
    pf.write_pfb(f"{run_dir}/fluxes_on.pfb", fluxes*2.0, p=config.P, q=config.Q, dist=True)
    pf.write_pfb(f"{run_dir}/fluxes_off.pfb", fluxes*0.0, p=config.P, q=config.Q, dist=True)
    fluxes_are_on = True
    for timestep, _ in enumerate(range(0, int(run.TimingInfo.StopTime)+2, int(run.TimeStep))):
        # We apply the pumping for half the day
        if timestep%12 == 0:
            fluxes_are_on = not fluxes_are_on
        timestep_string = str(timestep).zfill(5)
        if fluxes_are_on:
            os.symlink(f"{run_dir}/fluxes_on.pfb", f"{run_dir}/fluxes.{timestep_string}.pfb")
        else:
            os.symlink(f"{run_dir}/fluxes_off.pfb", f"{run_dir}/fluxes.{timestep_string}.pfb")
    run.Solver.EvapTransFileTransient = True
    run.Solver.EvapTrans.FileName = f"{run_dir}/fluxes.pfb"
    run.write("run", file_format="yaml")
    # run.run(working_directory=run_dir)