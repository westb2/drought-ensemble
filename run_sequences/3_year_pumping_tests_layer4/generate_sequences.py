#!/usr/bin/env python3
"""Layer-4 pumping tests: 40 spinup + 3 pump + 10 recovery at 1e-5."""
import json
from pathlib import Path

SPINUP_YEARS = 40
PUMPING_YEARS = 3
RECOVERY_YEARS = 10
PUMPING_RATE = 1e-5
PUMPING_LAYER = 4
OUT_DIR = Path(__file__).resolve().parent


def year(pumping_rate_fraction=0.0):
    return {
        "wetness": "average",
        "pumping_rate_fraction": pumping_rate_fraction,
        "irrigation": "False",
    }


sequence = {
    "name": "pumping_1e-5_layer4",
    "pumping_layer": PUMPING_LAYER,
    "years": (
        [year(0.0) for _ in range(SPINUP_YEARS)]
        + [year(PUMPING_RATE) for _ in range(PUMPING_YEARS)]
        + [year(0.0) for _ in range(RECOVERY_YEARS)]
    ),
}
out = OUT_DIR / f"{sequence['name']}.json"
out.write_text(json.dumps(sequence, indent=4) + "\n")
print(f"wrote {out.name} ({len(sequence['years'])} years, layer={PUMPING_LAYER})")
