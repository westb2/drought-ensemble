import parflow as pf
import pandas as pd
import numpy as np
import shutil
import plotly.express as px


def load_variable(loading_function, time, data_accessor):
    data_accessor.time = time
    return loading_function(data_accessor)

def load_run(data_accessor, outlet_yx, num_timesteps=8760, read_interval=24):
    (outlet_y, outlet_x) = outlet_yx
    run_def = {}
    run_def["mask"] = np.where(data_accessor.mask > 0, 1, np.nan)
    run_def["porosity"] = data_accessor.computed_porosity
    run_def["dx"] = data_accessor.dx
    run_def["dy"] = data_accessor.dy
    dz_vals = [1.0,0.5,0.25,0.125,0.05,0.025,0.005,0.003,0.0015, 0.0005]
    # dz_vals.reverse()
    print(run_def["mask"].shape)
    mask = np.ones([10, run_def["mask"].shape[1], run_def["mask"].shape[2]])
    dz = np.ones([10, run_def["mask"].shape[1], run_def["mask"].shape[2]])

    run_def["mask"] = mask


    run_def["specific_storage"] = data_accessor.specific_storage
    run_data = pd.DataFrame()
    run_data["time"] = np.arange(0, num_timesteps, read_interval)
    run_data["pressure"] = np.array(load_variable(lambda x: data_accessor.pressure, time, data_accessor)*run_def["mask"] for time in run_data.time)
    run_data["overland_flow"] = np.array(load_variable(lambda x: data_accessor.overland_flow_grid(), time, data_accessor) for time in run_data.time)
    run_data["outlet_flow"] = np.array(load_variable(lambda x: data_accessor.overland_flow_grid()[outlet_y, outlet_x], time, data_accessor) for time in run_data.time)
    run_data["saturation"] = np.array(load_variable(lambda x: data_accessor.pressure, time, data_accessor)*run_def["mask"] for time in run_data.time)
    run_data["subsurface_storage"] = np.array(load_variable(lambda x: data_accessor.subsurface_storage, time, data_accessor)*run_def["mask"] for time in run_data.time)
    run_data["surface_storage"] = np.array(load_variable(lambda x: data_accessor.surface_storage, time, data_accessor)*run_def["mask"][0] for time in run_data.time)
    run_data["wtd"] = np.array(load_variable(lambda x: data_accessor.wtd, time, data_accessor)*run_def["mask"][0] for time in run_data.time)
    run_data["total_storage"] = run_data["subsurface_storage"].apply(np.nansum) + run_data["surface_storage"].apply(np.nansum)
    run_data["water_required_to_recover"] = run_data["total_storage"][0]-run_data["total_storage"]
    # run_data["__precip"] = np.array(load_variable(lambda x: data_accessor.clm_forcing_apcp, time, data_accessor)*run_def["mask"][0] for time in run_data.time)
    # run_data["precip"] = run_data["__precip"].apply(np.nansum)

    return run_data

def get_data_accessor(domain_name, run_name):
    runs_folder = "../domains/outputs"
    run_dir = runs_folder + f"/{run_name}"
    data_accessor = pf.Run.from_definition(f'{run_dir}/{domain_name}.pfidb').data_accessor
    shutil.copyfile(f'{run_dir}/mannings.pfb', f'{run_dir}/{domain_name}.out.mannings.pfb')
    return data_accessor

def plot_variable_for_each_run(variable_name, runs, title=None, x_scale=24.0*365.0,
                                y_scale=1.0, x_label='Time (years)', y_label=None):
    if title is None:
        title = f'{variable_name} over time'
    df = pd.DataFrame()

    # Loop through each run and add the water_required_to_recover data to the new DataFrame
    for run_name, run_data in runs.items():
        df[run_name] = run_data[variable_name][1:]/y_scale

    # Add the time column
    df['time'] = runs['baseline']['time']/x_scale

    # Melt the DataFrame to long format for plotting
    melted_df = df.melt(id_vars='time', var_name='Run', value_name=variable_name)

    # Plot the data
    fig = px.line(melted_df, x='time', y=variable_name, color='Run',
                   title=title, template="simple_white").update_layout(
                       xaxis_title=x_label, yaxis_title=y_label)
    fig.show()