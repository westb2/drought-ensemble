import os
import shutil
import parflow as pf
from .add_pumping import add_pumping

def do_run(domain_name, run_name, pumping_rate_fraction, run_dir, config, 
           irrigation=False, flux_cycling=False, pumping_layer=2, flux_time_series=False, 
           years = 1, initial_pressure_file=None):
    os.chdir(f"/Users/ben/Documents/GitHub/drought-ensemble/{run_dir}")
    domains_folder = "../domains/outputs"

    shutil.rmtree(f"{domains_folder}/{domain_name}_{run_name}", ignore_errors=True)
    shutil.copytree(f"{domains_folder}/{domain_name}", f"{domains_folder}/{domain_name}_{run_name}")
    os.chdir(f"{domains_folder}/{domain_name}_{run_name}")
    if irrigation:
        os.remove("./drv_vegp.dat")
        shutil.copyfile("./drv_vegp_for_irrigation.dat", "./drv_vegp.dat")
    for i in range(years):
        TIME_STEPS_PER_YEAR = 8760
        OUTPUTS_PER_YEAR = 73
        START_COUNT = i * OUTPUTS_PER_YEAR
        run = pf.Run.from_definition(f"./{domain_name}.yaml")
        run.TimingInfo.StartCount = START_COUNT
        if pumping_rate_fraction > 0.0:
            run = add_pumping(run, config.GRID_CELL_CONSUMPTIVE_USE_M_PER_HOUR ,
                            ".", pumping_rate_fraction=pumping_rate_fraction, 
                            irrigation=irrigation, flux_cycling=flux_cycling, 
                            pumping_layer=pumping_layer, flux_time_series=flux_time_series,
                            start_time=0, end_time=TIME_STEPS_PER_YEAR * years)
        run.run_dir = os.getcwd()
        DUMP_INTERVAL = 24 * 5
        run.TimingInfo.DumpInterval = DUMP_INTERVAL
        run.Solver.CLM.CLMDumpInterval = DUMP_INTERVAL
        run.TimingInfo.StopTime = TIME_STEPS_PER_YEAR
        if i == 0:
            if initial_pressure_file is not None:
                run.Geom.domain.ICPressure.FileName = initial_pressure_file
                # run.ICPressure.FileFormat = "ParFlowBinary"
        if i>0:
            timestamp = str(START_COUNT).zfill(5)
            run.Geom.domain.ICPressure.FileName = f"./{domain_name}.out.press.{timestamp}.pfb"
            # run.ICPressure.FileFormat = "ParFlowBinary"
        run.write("final_run_config", file_format="yaml")
        run.run()