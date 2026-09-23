#!/usr/bin/env python3
"""One-off audit: every year dir of every watched sequence.

Flags year folders that exist but are not a usable full year: missing raw
NetCDF, unreadable header, or a short time dimension. Read-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import restart_watchdog as rw  # noqa: E402


def main() -> int:
    config = rw.load_config(HERE / "config.yaml")
    root = Path(config["project_root"])

    targets = []
    for entry in config.get("watch", []):
        ensemble = entry["ensemble"]
        seq_dir = root / "run_sequences" / ensemble
        names = entry.get("sequences")
        paths = (
            [seq_dir / f"{n}.json" for n in names]
            if names
            else sorted(seq_dir.glob("*.json"))
        )
        for domain in entry["domains"]:
            for path in paths:
                targets.append((domain, ensemble, path))

    cache: dict[tuple[str, str], tuple[bool, int | None, list[str]]] = {}
    problems: list[str] = []
    n_years = 0

    for domain, ensemble, seq_path in targets:
        seq = rw.json.loads(seq_path.read_text())
        years = seq["years"]
        layer = int(seq.get("pumping_layer", 2))
        raw = root / "domains" / domain / "raw_runs"
        label = f"{domain} / {ensemble} / {seq['name']}"

        for i in range(len(years)):
            h = rw.hash_years(years[: i + 1], layer)
            key = (domain, h)
            if key not in cache:
                d = raw / h
                if not d.is_dir():
                    cache[key] = (False, None, [])
                else:
                    nc = d / "run.out.00001.nc"
                    ntime = rw.netcdf_time_len(nc) if nc.exists() else None
                    extras = [
                        name
                        for name in (
                            "processed_output.nc",
                            "derived_hourly.nc",
                            "processed_output_219h.nc",
                        )
                        if (d / name).exists()
                    ]
                    cache[key] = (True, ntime, extras)
            exists, ntime, extras = cache[key]
            if not exists:
                continue
            n_years += 1
            ok = ntime is not None and (ntime >= 8760 or ntime == 24)
            if not ok:
                problems.append(
                    f"{label} year={i} time={ntime} extras={extras or 'none'} {raw / h}"
                )

    print(f"targets={len(targets)} existing_year_dirs_checked={n_years} "
          f"unique_dirs={len(cache)}")
    if problems:
        print(f"\nPROBLEM YEAR DIRS ({len(problems)}):")
        for p in problems:
            print(f"  {p}")
    else:
        print("\nNo truncated or unreadable year outputs found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
