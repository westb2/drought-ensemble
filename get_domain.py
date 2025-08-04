import numpy as np
import os
from parflow import Run

from parflow.tools.io import read_pfb, read_clm
from parflow.tools.fs import mkdir
from parflow.tools.settings import set_working_directory
import subsettools as st
import hf_hydrodata as hf

# import config

def get_domain(config):
    # You need to register on https://hydrogen.princeton.edu/pin before you can use the hydrodata utilities
    hf.register_api_pin("benjaminwest@arizona.edu", "7343")
    start_year = config.CURRENT_START_YEAR
    end_year = config.CURRENT_END_YEAR
    runname = f"{config.DOMAIN_NAME}"
    print(runname)

    # provide a way to create a subset from the conus domain (huc, lat/lon bbox currently supported)
    hucs = [config.CURRENT_HUC_ID]
    # provide information about the datasets you want to access for run inputs using the data catalog
    start = config.CURRENT_START_DATE
    end = config.CURRENT_END_DATE
    grid = "conus2"
    var_ds = "conus2_domain"
    forcing_ds = "CW3E"
    # cluster topology
    P = config.P
    Q = config.Q

    # set the directory paths where you want to write your subset files
    home = os.path.expanduser("~/Documents/Github")
    base_dir = os.path.join(home, "drought-ensemble/domains")
    input_dir = os.path.join(base_dir, "inputs", f"{runname}")
    output_dir = os.path.join(base_dir, "outputs")
    static_write_dir = os.path.join(input_dir, "static")
    mkdir(static_write_dir)
    forcing_dir = os.path.join(input_dir, "forcing")
    mkdir(forcing_dir)
    pf_out_dir = os.path.join(output_dir, f"{runname}")
    mkdir(pf_out_dir)
    # load your preferred template runscript
    reference_run = st.get_template_runscript(grid, "transient", "solid", pf_out_dir)
    ij_bounds, mask = st.define_huc_domain(hucs=hucs, grid=grid)
    os.environ["PARFLOW_DIR"] = "/Users/ben/parflow_installation/parflow"
    mask_solid_paths = st.write_mask_solid(mask=mask, grid=grid, write_dir=static_write_dir)
    static_paths = st.subset_static(ij_bounds, dataset=var_ds, write_dir=static_write_dir)
    clm_paths = st.config_clm(ij_bounds, start=start, end=end, dataset=var_ds, write_dir=static_write_dir)
    forcing_paths = st.subset_forcing(
        ij_bounds,
        grid=grid,
        start=start,
        end=end,
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
        runname=runname,
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
    

    print(pf_out_dir)

    # load the specified run script
    run = Run.from_definition(runscript_path)
    run.TimingInfo.StopTime = 8760
    run.TimingInfo.DumpInterval = 24
    run.Solver.CLM.MetFileName = "CW3E"
    os.remove(runscript_path)
    runscript_path = runscript_path.replace(".yaml", "")
    
    # run.name = runname.replace(".yaml", "")
    run.write(runscript_path, file_format='yaml')
    print(runscript_path)

    print(f"Loaded run with runname: {run.get_name()}")

    # The following line is setting the run just for 10 hours for testing purposes
   
    # run.run()



