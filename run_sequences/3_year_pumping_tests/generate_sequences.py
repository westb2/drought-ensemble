import json
from pathlib import Path

SPINUP_YEARS = 40
PUMPING_YEARS = 3
PUMPING_RATES = [1e-7, 1e-6, 1e-5, 1e-4]

OUT_DIR = Path(__file__).resolve().parent


def year(wetness="average", pumping_rate_fraction=0.0, irrigation="False"):
    return {
        "wetness": wetness,
        "pumping_rate_fraction": pumping_rate_fraction,
        "irrigation": irrigation,
    }


def rate_label(rate: float) -> str:
    return f"{rate:.0e}".replace("+0", "").replace("+", "").replace("-0", "-")


for rate in PUMPING_RATES:
    name = f"pumping_{rate_label(rate)}"
    sequence = {
        "name": name,
        "years": (
            [year(pumping_rate_fraction=0.0) for _ in range(SPINUP_YEARS)]
            + [year(pumping_rate_fraction=rate) for _ in range(PUMPING_YEARS)]
        ),
    }
    out_path = OUT_DIR / f"{name}.json"
    with open(out_path, "w") as f:
        json.dump(sequence, f, indent=4)
        f.write("\n")
    print(f"wrote {out_path.name} ({len(sequence['years'])} years)")
