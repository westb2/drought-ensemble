import json
from pathlib import Path

SPINUP_YEARS = 40
PUMPING_YEARS = 10
RECOVERY_YEARS = 10

# Full decade grid (with recovery) — already queued for potomac2/wolf2.
FULL_RATES = [1e-7, 1e-6, 1e-5, 1e-4]

# Extrapolation brackets for 10-yr drought-matched rate (no recovery).
# Potomac priority: 5e-7, 2e-6; Wolf priority: 2e-6, 3e-6, 5e-6.
BRACKET_RATES = [5e-7, 2e-6, 3e-6, 5e-6]

# Domain-specific rates matching 10-yr drought end-of-stress deficit
# (analysis/matched_deficit_10yr_summary.md). With full 10-yr recovery.
MATCHED_RATES = {
    "potomac2": 8.64e-7,
    "wolf2": 2.49e-6,
}

OUT_DIR = Path(__file__).resolve().parent


def year(wetness="average", pumping_rate_fraction=0.0, irrigation="False"):
    return {
        "wetness": wetness,
        "pumping_rate_fraction": pumping_rate_fraction,
        "irrigation": irrigation,
    }


def rate_label(rate: float) -> str:
    """Compact scientific label, e.g. 1e-7 or 8.64e-7."""
    one = f"{rate:.0e}".replace("+0", "").replace("+", "").replace("-0", "-")
    if abs(float(one) - rate) / max(abs(rate), 1e-30) > 0.02:
        return f"{rate:.2e}".replace("+0", "").replace("+", "").replace("-0", "-")
    return one


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

for rate in BRACKET_RATES:
    write_sequence(rate, recovery_years=0)

for rate in MATCHED_RATES.values():
    write_sequence(rate, RECOVERY_YEARS)
