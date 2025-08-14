import os
import shutil
import parflow as pf
from .add_pumping import add_pumping

def do_run(domain_name, run_dir, pumping_rate_fraction, 
           irrigation=False, flux_cycling=False, pumping_layer=4, flux_time_series=False, 
           years = 1, initial_pressure_file=None,):
    # os.chdir(f"/Users/ben/Documents/GitHub/drought-ensemble/{run_dir}")
    # for now set consumptive use to 1 inch per week
    # TODO figure out if this is the right number
    GRID_CELL_CONSUMPTIVE_USE_M_PER_HOUR = 0.00015119
    domains_folder = "/Users/ben/Documents/GitHub/drought-ensemble/domains/outputs"

    shutil.copytree(f"{domains_folder}/{domain_name}", run_dir)
    os.chdir(run_dir)
    if irrigation:
        os.remove("./drv_vegp.dat")
        shutil.copyfile("./drv_vegp_for_irrigation.dat", "./drv_vegp.dat")
    TIME_STEPS_PER_YEAR = 8760
    START_COUNT = 0
    DUMP_INTERVAL = 24 * 5
    run = pf.Run.from_definition("./run.yaml")
    run.TimingInfo.StartCount = START_COUNT
    if pumping_rate_fraction > 0.0:
        run = add_pumping(run, GRID_CELL_CONSUMPTIVE_USE_M_PER_HOUR ,
                        ".", pumping_rate_fraction=pumping_rate_fraction, 
                        irrigation=irrigation, flux_cycling=flux_cycling, 
                        pumping_layer=pumping_layer, flux_time_series=flux_time_series,
                        start_time=0, end_time=TIME_STEPS_PER_YEAR * years)
    run.run_dir = os.getcwd()
    run.TimingInfo.DumpInterval = DUMP_INTERVAL
    run.Solver.CLM.CLMDumpInterval = DUMP_INTERVAL
    run.TimingInfo.StopTime = TIME_STEPS_PER_YEAR
    if initial_pressure_file is not None:
        run.Geom.domain.ICPressure.FileName = initial_pressure_file
        # run.ICPressure.FileFormat = "ParFlowBinary"
    run.write("run", file_format="yaml")
    run.run()