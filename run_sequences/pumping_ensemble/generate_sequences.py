import numpy as np
import json

pumping_rates = [0.00001, 0.0001, 0.001]
# drought_lengths = [8]



for pumping_rate in pumping_rates:
    if pumping_rate == 0.0:
        sequence_name = "baseline"
    else:
        sequence_name = f"pumping_{pumping_rate}"
    sequence_name = sequence_name.replace(".", "_")
    sequence = {"name": sequence_name, "years": []}
    sequence_years = []
    #spinup
    for i in range(10):
        sequence_years.append({"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"})
    #drought
    for i in range(5):
        sequence_years.append({"wetness": "average", "pumping_rate_fraction": pumping_rate, "irrigation": "False"})
    #recovery
    for i in range(5):
        sequence_years.append({"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"})
    sequence["years"] = sequence_years
    json.dump(sequence, open(f"{sequence_name}.json", "w"))