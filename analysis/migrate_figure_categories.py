#!/usr/bin/env python3
"""One-time (and re-runnable) migration of figures/ into category subfolders.

Moves PNGs into drought_final / pumping_final / *_exploratory, decks into
``decks/``, json/csv into ``_data/``, html/pdf reports into ``_reports/``,
``_tmp_*`` into ``_scratch/``, and ``_pumping_*_cache`` dirs under ``_cache/``.

Safe to re-run: skips if destination already exists and matches size.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis.figure_paths import (  # noqa: E402
    CATEGORIES,
    FIG_ROOT,
    ensure_category_dirs,
    fig_path,
    reload_categories,
)

SKIP_NAMES = {
    "FIGURE_CATEGORIES.yaml",  # lives in analysis/, not here
}
SKIP_DIRS_AT_ROOT = set(CATEGORIES) | {
    "decks",
    "_data",
    "_reports",
    "_cache",
    "_scratch",
}


def _move(src: Path, dst: Path, *, dry: bool) -> str:
    if not src.exists():
        return "missing"
    if src.resolve() == dst.resolve():
        return "same"
    if dst.exists():
        if src.is_file() and dst.is_file() and src.stat().st_size == dst.stat().st_size:
            if not dry:
                src.unlink()
            return "dedupe-removed-src" if not dry else "would-dedupe"
        return "dst-exists-skip"
    if dry:
        return "would-move"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return "moved"


def migrate(*, dry: bool = False) -> None:
    reload_categories()
    ensure_category_dirs()
    counts: dict[str, int] = {}

    # Cache directories
    for cache_name in ("_pumping_219h_cache", "_pumping_zone_219h_cache"):
        src = FIG_ROOT / cache_name
        dst = FIG_ROOT / "_cache" / cache_name
        if src.is_dir():
            status = _move(src, dst, dry=dry)
            counts[status] = counts.get(status, 0) + 1
            print(f"  [{status}] {cache_name}/ → _cache/{cache_name}/")

    # no50/ stay as exploratory nesting under drought_exploratory
    no50 = FIG_ROOT / "no50"
    if no50.is_dir():
        dst = FIG_ROOT / "drought_exploratory" / "no50"
        status = _move(no50, dst, dry=dry)
        counts[status] = counts.get(status, 0) + 1
        print(f"  [{status}] no50/ → drought_exploratory/no50/")

    for src in sorted(FIG_ROOT.iterdir()):
        if src.name in SKIP_DIRS_AT_ROOT or src.name in SKIP_NAMES:
            continue
        if src.is_dir():
            continue  # only known dirs handled above
        if not src.is_file():
            continue

        dst = fig_path(src.name, mkdir=False)
        status = _move(src, dst, dry=dry)
        counts[status] = counts.get(status, 0) + 1
        rel = dst.relative_to(FIG_ROOT)
        print(f"  [{status}] {src.name} → {rel}")

    print("\nSummary:", dict(sorted(counts.items())))


def main():
    dry = "--dry-run" in sys.argv
    print(f"Migrating {FIG_ROOT} ({'dry-run' if dry else 'live'})…")
    migrate(dry=dry)


if __name__ == "__main__":
    main()
