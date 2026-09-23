import json
from pathlib import Path

SPINUP_YEARS = 40
PUMPING_YEARS = 3
RECOVERY_YEARS = 10

# Full spinup + pumping + recovery (used for recovery / memory analysis).
FULL_RATES = [1e-7, 1e-6, 1e-5, 1e-4]

# Intermediate rates only estimate end-of-stress deficit vs 10-yr drought;
# no recovery years (sequence ends after pumping).
ESTIMATE_RATES = [2e-6, 3e-6, 5e-6, 6e-6]

OUT_DIR = Path(__file__).resolve().parent


def year(wetness="average", pumping_rate_fraction=0.0, irrigation="False"):
    return {
        "wetness": wetness,
        "pumping_rate_fraction": pumping_rate_fraction,
        "irrigation": irrigation,
    }


def rate_label(rate: float) -> str:
    return f"{rate:.0e}".replace("+0", "").replace("+", "").replace("-0", "-")


def write_sequence(rate: float, recovery_years: int) -> None:
    name = f"pumping_{rate_label(rate)}"
    years = (
        [year(pumping_rate_fraction=0.0) for _ in range(SPINUP_YEARS)]
        + [year(pumping_rate_fraction=rate) for _ in range(PUMPING_YEARS)]
        + [year(pumping_rate_fraction=0.0) for _ in range(recovery_years)]
    )
    sequence = {"name": name, "years": years}
    out_path = OUT_DIR / f"{name}.json"
    with open(out_path, "w") as f:
        json.dump(sequence, f, indent=4)
        f.write("\n")
    print(f"wrote {out_path.name} ({len(sequence['years'])} years, recovery={recovery_years})")


for rate in FULL_RATES:
    write_sequence(rate, RECOVERY_YEARS)

for rate in ESTIMATE_RATES:
    write_sequence(rate, recovery_years=0)
