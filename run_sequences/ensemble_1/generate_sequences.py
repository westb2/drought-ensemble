import numpy as np
import json

drought_lengths = [1,2,3,5,8]

sequence = []
#spinup
for i in range(3):
    sequence.append({"year_type": "A", "pumping_rate_fraction": 0.0, "irrigation": False})
#drought
for i in range(3):
    sequence.append({"year_type": "A", "pumping_rate_fraction": 0.0, "irrigation": False})
#recovery
for i in range(30):
    sequence.append({"year_type": "A", "pumping_rate_fraction": 0.0, "irrigation": False})

json.dump(sequence, open("baseline.json", "w"))

for drought_length in drought_lengths:
    sequence = []
    #spinup
    for i in range(3):
        sequence.append({"year_type": "A", "pumping_rate_fraction": 0.0, "irrigation": False})
    #drought
    for i in range(drought_length):
        sequence.append({"year_type": "D", "pumping_rate_fraction": 0.0, "irrigation": False})
    #recovery
    for i in range(30):
        sequence.append({"year_type": "A", "pumping_rate_fraction": 0.0, "irrigation": False})
    json.dump(sequence, open(f"{drought_length}_year_drought.json", "w"))