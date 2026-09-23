"""Simultaneous 10-yr drought + domain-matched pumping.

Stress years use dry forcing AND the domain-specific pumping rate that matches
10-yr drought end-of-stress storage deficit (see matched_deficit_10yr_summary.md).

Submit pairing only (do not cross rates across domains):
  potomac2 -> pumping_8.64e-7_drought_10
  wolf2    -> pumping_2.49e-6_drought_10
"""
import json
from pathlib import Path

SPINUP_YEARS = 40
DROUGHT_YEARS = 10
RECOVERY_YEARS = 10

# Domain-specific rates matching 10-yr drought end-of-stress deficit
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


def write_sequence(rate: float) -> None:
    name = f"pumping_{rate_label(rate)}_drought_{DROUGHT_YEARS}"
    years = (
        [year() for _ in range(SPINUP_YEARS)]
        + [
            year(wetness="dry", pumping_rate_fraction=rate)
            for _ in range(DROUGHT_YEARS)
        ]
        + [year() for _ in range(RECOVERY_YEARS)]
    )
    sequence = {"name": name, "years": years}
    out_path = OUT_DIR / f"{name}.json"
    with open(out_path, "w") as f:
        json.dump(sequence, f, indent=4)
        f.write("\n")
    print(f"wrote {out_path.name} ({len(sequence['years'])} years)")


for rate in MATCHED_RATES.values():
    write_sequence(rate)
