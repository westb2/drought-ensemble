#!/usr/bin/env python3
"""Shared settings for 3-yr vs 10-yr pumping analysis scripts.

Set ``PUMPING_STRESS_YEARS=10`` in the environment before importing analysis
modules (or call ``apply_10yr()`` then re-import). Figure/summary outputs use
the ``ten_year_`` prefix so 3-yr products are not overwritten.

Recovery length is capped at 5 years in 10-yr mode because
``droughts/short_baseline`` only has 55 years (40 + 10 stress + 5 recovery).
Pump members themselves have a full 10-yr recovery on disk.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")


def stress_years() -> int:
    return int(os.environ.get("PUMPING_STRESS_YEARS", "3"))


def is_10yr() -> bool:
    return stress_years() == 10


def pump_ensemble() -> str:
    return "10_year_pumping_tests" if is_10yr() else "3_year_pumping_tests"


def pump_years() -> int:
    return 10 if is_10yr() else 3


def recovery_years() -> int:
    # short_baseline = 55 yr → 5 recovery years after a 10-yr stress.
    return 5 if is_10yr() else 10


def drought_member() -> str:
    return "10_year_drought" if is_10yr() else "3_year_drought"


def drought_recovery_years() -> int:
    return 5


def fig_tag() -> str:
    return "ten_year_" if is_10yr() else ""


def summary_tag() -> str:
    return "ten_year_" if is_10yr() else ""


def n_years() -> int:
    return 40 + pump_years() + recovery_years()


def out_name(stem: str) -> str:
    """``pumping_foo.png`` → ``ten_year_pumping_foo.png`` in 10-yr mode."""
    tag = fig_tag()
    if not tag:
        return stem
    if stem.startswith("ten_year_"):
        return stem
    if stem.startswith("pumping_"):
        return tag + stem
    if stem.startswith("wolf_pumping_"):
        return tag + stem
    return tag + stem


def summary_path(stem: str) -> Path:
    """``pumping_foo_summary.md`` → ``ten_year_pumping_foo_summary.md``."""
    name = out_name(stem) if not stem.endswith(".md") else out_name(stem)
    if not name.endswith(".md"):
        name = name + ".md" if "." not in name else name
    # stem is like pumping_recovery_timeseries_summary.md
    if stem.endswith(".md"):
        base = stem
        if is_10yr() and not base.startswith("ten_year_"):
            base = "ten_year_" + base
        return ROOT / "analysis" / base
    return ROOT / "analysis" / name
