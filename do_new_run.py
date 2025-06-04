import os
import shutil
import parflow as pf
from add_pumping import add_pumping

def do_run(domain_name, run_name, pumping_rate_fraction, run_dir, config, 
           irrigation=False, flux_cycling=False, pumping_layer=2, flux_time_series=True, 
           years = 1):
    os.chdir(f"/Users/ben/Documents/GitHub/drought-ensemble/{run_dir}")
    domains_folder = "../domains/outputs"

    shutil.rmtree(f"{domains_folder}/{domain_name}_{run_name}", ignore_errors=True)
    shutil.copytree(f"{domains_folder}/{domain_name}", f"{domains_folder}/{domain_name}_{run_name}")
    os.chdir(f"{domains_folder}/{domain_name}_{run_name}")
    if irrigation:
        os.remove("./drv_vegp.dat")
        shutil.copyfile("./drv_vegp_for_irrigation.dat", "./drv_vegp.dat")
    run = pf.Run.from_definition(f"./{domain_name}.yaml")
    if pumping_rate_fraction > 0.0:
        run = add_pumping(run, config.GRID_CELL_CONSUMPTIVE_USE_M_PER_HOUR ,
                           ".", pumping_rate_fraction=pumping_rate_fraction, 
                           irrigation=irrigation, flux_cycling=flux_cycling, 
                           pumping_layer=pumping_layer, flux_time_series=flux_time_series)
    run.run_dir = os.getcwd()
    run.TimingInfo.DumpInterval = 1
    run.TimingInfo.TimeStep = 1
    run.run()