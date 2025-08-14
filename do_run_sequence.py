


DRY = "D" 
AVERAGE = "A"
WET = "W"

def run_sequence_to_string(run_sequence):
    year_types = [run["year_type"] for run in run_sequence]
    pumping_rates = [run["pumping_rate_fraction"] for run in run_sequence]
    irrigation_flags = [run["irrigation"] for run in run_sequence]
    year_types_str = "".join(year_types)
    pumping_rates_str = "_".join([str(rate) for rate in pumping_rates])
    irrigation_str = "irrigation" + "_".join(["T" if flag else "F" for flag in irrigation_flags])
    return " ".join([year_types_str, pumping_rates_str, irrigation_str])

run_sequence = [
    {"year_type": DRY, "pumping_rate_fraction": 0.0, "irrigation": False},
    {"year_type": AVERAGE, "pumping_rate_fraction": 0.0, "irrigation": False},
    {"year_type": WET, "pumping_rate_fraction": 0.0, "irrigation": False},
    {"year_type": DRY, "pumping_rate_fraction": 0.5, "irrigation": False},
    {"year_type": AVERAGE, "pumping_rate_fraction": 0.5, "irrigation": False},
    {"year_type": WET, "pumping_rate_fraction": 0.5, "irrigation": False},
    ]


def do_run_sequence(run_sequence, domain):
    run_sequence
