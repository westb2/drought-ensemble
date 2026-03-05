import numpy as np
import json

# inches/week
pumping_rates = [0.025]
drought_lengths = [5]
# drought_lengths = [8]


for pumping_rate in pumping_rates:
    for drought_length in drought_lengths:
        sequence_name = f"pumping_{pumping_rate}_drought_{drought_length}"
        sequence_name = sequence_name.replace(".", "_")
        sequence = {"name": sequence_name, "years": []}
        sequence_years = []
        #spinup
        for i in range(3):
            sequence_years.append({"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"})
        #drought
        for i in range(drought_length):
            sequence_years.append({"wetness": "dry", "pumping_rate_fraction": pumping_rate, "irrigation": "False"})
        #recovery
        for i in range(10):
            sequence_years.append({"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"})
        sequence["years"] = sequence_years
        json.dump(sequence, open(f"{sequence_name}.json", "w"))