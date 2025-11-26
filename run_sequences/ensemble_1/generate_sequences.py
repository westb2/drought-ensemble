import numpy as np
import json

drought_lengths = [1,2,3,5,8]
# drought_lengths = [8]

sequence = []
sequence_name = "baseline"
sequence = {"name": sequence_name, "years": []}
sequence_years = []
#spinup
for i in range(3):
    sequence_years.append({"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"})
#drought
for i in range(3):
    sequence_years.append({"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"})
#recovery
for i in range(10):
    sequence_years.append({"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"})
sequence["years"] = sequence_years

json.dump(sequence, open(f"{sequence_name}.json", "w"))

for drought_length in drought_lengths:
    sequence_name = f"{drought_length}_year_drought"
    sequence = {"name": sequence_name, "years": []}
    sequence_years = []
    #spinup
    for i in range(3):
        sequence_years.append({"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"})
    #drought
    for i in range(drought_length):
        sequence_years.append({"wetness": "dry", "pumping_rate_fraction": 0.0, "irrigation": "False"})
    #recovery
    for i in range(10):
        sequence_years.append({"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"})
    sequence["years"] = sequence_years
    json.dump(sequence, open(f"{sequence_name}.json", "w"))