import json
from pathlib import Path

SPINUP_YEARS = 40
RECOVERY_YEARS = 10
DROUGHT_LENGTHS = [1, 3, 10, 50]
OUT_DIR = Path(__file__).resolve().parent


def year(wetness="average", pumping_rate_fraction=0.0, irrigation="False"):
    return {
        "wetness": wetness,
        "pumping_rate_fraction": pumping_rate_fraction,
        "irrigation": irrigation,
    }


# Long all-average baseline matching longest drought + recovery
baseline = {
    "name": "baseline",
    "years": [year() for _ in range(SPINUP_YEARS + 50 + RECOVERY_YEARS)],
}
with open(OUT_DIR / "baseline.json", "w") as f:
    json.dump(baseline, f, indent=4)
    f.write("\n")
print(f"wrote baseline.json ({len(baseline['years'])} years)")

for drought_length in DROUGHT_LENGTHS:
    name = f"{drought_length}_year_drought"
    sequence = {
        "name": name,
        "years": (
            [year() for _ in range(SPINUP_YEARS)]
            + [year(wetness="dry") for _ in range(drought_length)]
            + [year() for _ in range(RECOVERY_YEARS)]
        ),
    }
    out_path = OUT_DIR / f"{name}.json"
    with open(out_path, "w") as f:
        json.dump(sequence, f, indent=4)
        f.write("\n")
    print(f"wrote {out_path.name} ({len(sequence['years'])} years)")
