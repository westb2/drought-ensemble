#!/usr/bin/env python3
"""Report which sequence years exist per domain and estimate walltime.

Usage:
  python years_to_run.py <sequence.json> <domain> [<domain> ...]

Example:
  python years_to_run.py run_sequences/5_year_pumping_tests/pumping_1e-6.json potomac2
"""
import hashlib
import json
import sys
from pathlib import Path

H_PER_YEAR = 1.1
STARTUP_H = 0.75
WALLTIME_H = 12.0


def sequence2string(years):
    return "_".join(
        f"{y['wetness']}_{y['pumping_rate_fraction']}_{y['irrigation']}" for y in years
    )


def hash_prefix(years):
    return hashlib.sha256(sequence2string(years).encode()).hexdigest()


PRODUCTION_YEAR_HOURS = 8760
TESTING_YEAR_HOURS = 24


def netcdf_time_len(nc_path: Path):
    try:
        from netCDF4 import Dataset

        with Dataset(str(nc_path), "r") as ds:
            if "time" not in ds.dimensions:
                return None
            return int(len(ds.dimensions["time"]))
    except Exception:
        return None


def year_complete(run_dir: Path) -> bool:
    nc = run_dir / "run.out.00001.nc"
    if nc.exists():
        ntime = netcdf_time_len(nc)
        if ntime is None:
            return False
        return ntime >= PRODUCTION_YEAR_HOURS or ntime == TESTING_YEAR_HOURS
    return (run_dir / "processed_output.nc").exists()


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    seq_path = Path(sys.argv[1])
    domains = sys.argv[2:]
    project_root = seq_path.resolve().parents[2] if "run_sequences" in seq_path.parts else Path.cwd()

    seq = json.loads(seq_path.read_text())
    years = seq["years"]
    print(f"Sequence: {seq_path.name} ({len(years)} years, name={seq.get('name')})\n")

    for domain in domains:
        raw = project_root / "domains" / domain / "raw_runs"
        need = []
        for i, _ in enumerate(years):
            h = hash_prefix(years[: i + 1])
            if not year_complete(raw / h):
                need.append(i)

        est = len(need) * H_PER_YEAR + (STARTUP_H if need and need[0] == 0 else 0)
        status = "complete" if not need else f"need {len(need)} years {need}"
        yr12 = WALLTIME_H / (est / len(need)) if need else float("inf")
        print(f"{domain}: {status}")
        if need:
            print(f"  est {est:.1f}h / {WALLTIME_H}h walltime", end="")
            print(" OK" if est < WALLTIME_H - 1 else " TIGHT")
        print()


if __name__ == "__main__":
    main()
