import numpy as np
import json

pumping_rate = 0.01
pumping_heights = [2, 3, 4]
pumping_duration = 5

for pumping_height in pumping_heights:
    sequence_name = f"pumping_{pumping_rate}_height_{pumping_height}"
    sequence_name = sequence_name.replace(".", "_")
    sequence = {"name": sequence_name, "years": []}
    sequence_years = []
    sequence["pumping_layer"] = pumping_height
    #spinup
    for i in range(3):
        sequence_years.append({"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"})
    #drought
    for i in range(5):
        sequence_years.append({"wetness": "average", "pumping_rate_fraction": pumping_rate, "irrigation": "False"})
    #recovery
    for i in range(3):
        sequence_years.append({"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"})
    sequence["years"] = sequence_years
    json.dump(sequence, open(f"{sequence_name}.json", "w"))

sequence_name = "baseline"
sequence = {"name": sequence_name, "years": []}
sequence_years = []
#spinup
for i in range(11):
    sequence_years.append({"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"})
sequence["years"] = sequence_years
json.dump(sequence, open(f"{sequence_name}.json", "w"))