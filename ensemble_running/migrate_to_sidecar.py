#!/usr/bin/env python3
"""Migrate legacy ``processed_output.nc`` → thin sidecar, then optionally delete.

Default mode is **dry-run** (report only). Pass ``--commit`` to write or delete.

Modes
-----
1. **Migrate** (default): extract ``derived_hourly.nc`` from legacy hourly,
   ensure ``processed_output_219h.nc`` exists, rewrite ``file_locations.json``
   to prefer sidecar paths. Does **not** delete.

2. **Delete legacy** (``--delete-legacy``): remove ``processed_output.nc`` only
   when raw + valid sidecar + valid 219h are all present.

Example::

    module load conda && conda activate droughts && source ~/pf_env.sh
    cd /glade/derecho/scratch/bwest/drought-ensemble

    # migrate (dry-run then commit)
    python ensemble_running/migrate_to_sidecar.py --domains wolf2 --ensembles droughts
    python ensemble_running/migrate_to_sidecar.py --domains wolf2 --ensembles droughts --commit

    # delete legacy (dry-run then commit)
    python ensemble_running/migrate_to_sidecar.py --domains wolf2 --delete-legacy
    python ensemble_running/migrate_to_sidecar.py --domains wolf2 --delete-legacy --commit
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ensemble_running.consolidate_to_interval import (
    DEFAULT_INTERVAL,
    collect_hourly_files,
    consolidate_year,
    consolidated_path,
    locations_name,
    write_interval_indexes,
)
from ensemble_running.hourly_year import (
    ONE_YEAR_HOURS,
    LEGACY_HOURLY,
    SIDECAR_NAME,
    _legacy_looks_valid,
    _raw_looks_valid,
    _sidecar_looks_valid,
    _time_size,
    extract_sidecar_from_legacy,
    hourly_ref_path,
    legacy_hourly_path,
    raw_transient_path,
    resolve_year_dir,
    sidecar_path,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("migrate_sidecar")


def _human_bytes(n: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    x = float(n)
    for u in units:
        if x < 1024.0 or u == units[-1]:
            return f"{x:.2f} {u}"
        x /= 1024.0
    return f"{n} B"


def _consolidated_looks_valid(
    year_dir: Path, interval: int = DEFAULT_INTERVAL
) -> bool:
    path = consolidated_path(year_dir, interval)
    if not path.is_file():
        return False
    expected = ONE_YEAR_HOURS // interval
    n = _time_size(path)
    return n == expected


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def unique_year_dirs(hourly_refs: Iterable[str | Path]) -> list[Path]:
    """Deduplicate year directories from ``file_locations.json`` entries."""
    out: list[Path] = []
    seen: set[str] = set()
    for ref in hourly_refs:
        yd = resolve_year_dir(ref).resolve()
        key = str(yd)
        if key not in seen:
            seen.add(key)
            out.append(yd)
    return out


def _prefer_hourly_ref(year_dir: Path, *, validate: bool) -> Path:
    """Sidecar path when available; else legacy. ``validate`` opens NetCDF metadata."""
    year_dir = Path(year_dir)
    if validate:
        return hourly_ref_path(year_dir)
    # Dry-run / fast path: prefer sidecar file presence without opening NetCDF.
    if sidecar_path(year_dir).is_file():
        return sidecar_path(year_dir)
    if legacy_hourly_path(year_dir).is_file():
        return legacy_hourly_path(year_dir)
    return sidecar_path(year_dir)


def rewrite_hourly_indexes(
    root: Path,
    member_files: dict[tuple[str, str, str], list[str]],
    *,
    commit: bool,
    validate: bool | None = None,
) -> int:
    """Rewrite ``file_locations.json`` to prefer valid sidecar paths.

    ``validate`` defaults to ``commit`` (full metadata check when writing).
    Dry-runs use existence-only preference so Lustre is not hammered.
    """
    if validate is None:
        validate = commit
    n_changed = 0
    cache: dict[str, str] = {}
    for (domain, ensemble, member), hourly_list in member_files.items():
        new_list: list[str] = []
        for p in hourly_list:
            yd = resolve_year_dir(p)
            key = str(yd.resolve())
            if key not in cache:
                cache[key] = str(_prefer_hourly_ref(yd, validate=validate))
            new_list.append(cache[key])
        if new_list == hourly_list:
            continue
        n_changed += 1
        dest = (
            root
            / "domains"
            / domain
            / "processed_full_runs"
            / ensemble
            / member
            / "file_locations.json"
        )
        if not commit:
            log.info(
                "dry-run would rewrite %s (%d paths; sidecar preferred where present)",
                dest,
                len(new_list),
            )
            continue
        dest.write_text(json.dumps(new_list, indent=2) + "\n")
        log.info("rewrote %s (%d paths)", dest, len(new_list))
        member_files[(domain, ensemble, member)] = new_list
    return n_changed


def _indexed_219h_years(
    root: Path,
    domains: Iterable[str],
    ensembles: Iterable[str],
    members: Iterable[str] | None,
    interval: int,
) -> set[str]:
    """Year-dir paths listed in any ``file_locations_{interval}h.json``."""
    indexed: set[str] = set()
    name = locations_name(interval)
    for domain in domains:
        for ensemble in ensembles:
            ens_dir = root / "domains" / domain / "processed_full_runs" / ensemble
            if not ens_dir.is_dir():
                continue
            for member_dir in sorted(ens_dir.iterdir()):
                if not member_dir.is_dir():
                    continue
                if members is not None and member_dir.name not in members:
                    continue
                loc = member_dir / name
                if not loc.is_file():
                    continue
                for p in json.loads(loc.read_text()):
                    indexed.add(str(resolve_year_dir(p).resolve()))
    return indexed


def migrate_year(
    year_dir: Path,
    *,
    interval: int,
    commit: bool,
    ensure_219h: bool,
) -> tuple[str, str | None]:
    """Migrate one year. Return (status, detail).

    status: ``skip_ready`` | ``skip_no_legacy`` | ``would_extract`` |
    ``extracted`` | ``would_consolidate`` | ``consolidated`` | ``error``
    """
    year_dir = Path(year_dir)
    try:
        if _sidecar_looks_valid(year_dir) and _raw_looks_valid(year_dir):
            status = "skip_ready"
            detail = None
        elif not legacy_hourly_path(year_dir).is_file():
            return "skip_no_legacy", "no processed_output.nc"
        elif not _legacy_looks_valid(year_dir):
            return "error", "legacy exists but time != 8760 (or unreadable)"
        else:
            if not commit:
                status = "would_extract"
                detail = f"extract {SIDECAR_NAME} from {LEGACY_HOURLY}"
            else:
                out = extract_sidecar_from_legacy(year_dir)
                if out is None or not _sidecar_looks_valid(year_dir):
                    return "error", "sidecar extract failed validation"
                status = "extracted"
                detail = str(out)

        if ensure_219h and not _consolidated_looks_valid(year_dir, interval):
            out_219 = consolidated_path(year_dir, interval)
            if not commit:
                parts = []
                if status == "would_extract":
                    parts.append(f"extract {SIDECAR_NAME}")
                parts.append(f"write {out_219.name}")
                return "would_migrate", "; ".join(parts)
            ref = hourly_ref_path(year_dir)
            consolidate_year(ref, interval, overwrite=False, dry_run=False)
            if not _consolidated_looks_valid(year_dir, interval):
                return "error", "consolidation missing or invalid after write"
            if status == "skip_ready":
                status = "consolidated"
            elif status == "extracted":
                status = "extracted+consolidated"
            detail = str(out_219)

        return status, detail
    except Exception as exc:  # noqa: BLE001
        return "error", f"{type(exc).__name__}: {exc}"


def _migrate_worker(args: tuple) -> tuple[str, str, str | None]:
    year_dir, interval, commit, ensure_219h = args
    status, detail = migrate_year(
        Path(year_dir),
        interval=interval,
        commit=commit,
        ensure_219h=ensure_219h,
    )
    return (year_dir, status, detail)


def delete_legacy_year(
    year_dir: Path,
    *,
    interval: int,
    commit: bool,
    require_indexed: bool,
    indexed_years: set[str] | None,
) -> tuple[str, str | None, int]:
    """Delete legacy hourly if gates pass. Return (status, detail, bytes)."""
    year_dir = Path(year_dir)
    legacy = legacy_hourly_path(year_dir)
    if not legacy.is_file():
        return "skip_no_legacy", None, 0

    size = _file_size(legacy)
    reasons: list[str] = []

    # Cheap existence checks first (Lustre-friendly), then metadata.
    if not sidecar_path(year_dir).is_file():
        reasons.append(f"missing/invalid {SIDECAR_NAME}")
    elif not _sidecar_looks_valid(year_dir):
        reasons.append(f"missing/invalid {SIDECAR_NAME}")

    if not raw_transient_path(year_dir).is_file():
        reasons.append("missing run.out.00001.nc")
    elif not _raw_looks_valid(year_dir):
        reasons.append("raw time != 8760 (or unreadable)")

    cpath = consolidated_path(year_dir, interval)
    if not cpath.is_file():
        reasons.append(f"missing/invalid {cpath.name}")
    elif not _consolidated_looks_valid(year_dir, interval):
        reasons.append(f"missing/invalid {cpath.name}")

    if require_indexed:
        key = str(year_dir.resolve())
        if indexed_years is None or key not in indexed_years:
            reasons.append(f"not in file_locations_{interval}h.json")

    if reasons:
        # Deduplicate while preserving order
        seen: set[str] = set()
        uniq = []
        for r in reasons:
            if r not in seen:
                seen.add(r)
                uniq.append(r)
        return "blocked", "; ".join(uniq), 0

    if not commit:
        return "would_delete", str(legacy), size

    legacy.unlink()
    return "deleted", str(legacy), size


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--root",
        type=Path,
        default=Path("/glade/derecho/scratch/bwest/drought-ensemble"),
        help="Project root",
    )
    p.add_argument(
        "--domains",
        nargs="+",
        default=["wolf2"],
        help="Domains to process",
    )
    p.add_argument(
        "--ensembles",
        nargs="+",
        default=["droughts"],
        help="Ensemble folder names under processed_full_runs",
    )
    p.add_argument(
        "--members",
        nargs="+",
        default=None,
        help="Optional member subset",
    )
    p.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Consolidation interval hours (default {DEFAULT_INTERVAL})",
    )
    p.add_argument(
        "--delete-legacy",
        action="store_true",
        help="Delete processed_output.nc when raw+sidecar+219h gates pass",
    )
    p.add_argument(
        "--commit",
        action="store_true",
        help="Actually write/delete (default is dry-run)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit dry-run (default). Mutually exclusive with --commit",
    )
    p.add_argument(
        "--indexes-only",
        action="store_true",
        help="Only rewrite file_locations.json (and optionally 219h indexes)",
    )
    p.add_argument(
        "--refresh-219h-indexes",
        action="store_true",
        help="Also rewrite file_locations_{interval}h.json from hourly indexes",
    )
    p.add_argument(
        "--no-ensure-219h",
        action="store_true",
        help="In migrate mode, do not create missing consolidated files",
    )
    p.add_argument(
        "--require-indexed",
        action="store_true",
        help="With --delete-legacy, require year in file_locations_{interval}h.json",
    )
    p.add_argument("--workers", type=int, default=1, help="Parallel year workers")
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N unique year dirs (smoke tests)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.commit and args.dry_run:
        log.error("pass only one of --commit or --dry-run")
        return 2
    commit = bool(args.commit)
    if not commit:
        log.info("DRY-RUN (pass --commit to apply)")

    if ONE_YEAR_HOURS % args.interval != 0:
        log.error(
            "interval %d does not divide %d",
            args.interval,
            ONE_YEAR_HOURS,
        )
        return 2

    unique_refs, member_files = collect_hourly_files(
        args.root, args.domains, args.ensembles, args.members
    )
    year_dirs = unique_year_dirs(unique_refs)
    if args.limit is not None:
        year_dirs = year_dirs[: args.limit]

    log.info(
        "found %d unique year dirs across %d member sequences (%s)",
        len(year_dirs),
        len(member_files),
        ", ".join(args.domains),
    )

    if args.indexes_only:
        n = rewrite_hourly_indexes(args.root, member_files, commit=commit)
        if args.refresh_219h_indexes:
            # Re-collect after possible rewrite so 219h indexes follow new refs
            _, member_files = collect_hourly_files(
                args.root, args.domains, args.ensembles, args.members
            )
            write_interval_indexes(
                args.root,
                member_files,
                args.interval,
                dry_run=not commit,
            )
        log.info("indexes-only done (%d member indexes changed)", n)
        return 0

    if args.delete_legacy:
        indexed: set[str] | None = None
        if args.require_indexed:
            indexed = _indexed_219h_years(
                args.root,
                args.domains,
                args.ensembles,
                args.members,
                args.interval,
            )
            log.info(
                "require-indexed: %d year dirs in %s",
                len(indexed),
                locations_name(args.interval),
            )

        counts: dict[str, int] = {}
        bytes_freed = 0
        blocked_samples: list[str] = []
        for yd in year_dirs:
            status, detail, nbytes = delete_legacy_year(
                yd,
                interval=args.interval,
                commit=commit,
                require_indexed=args.require_indexed,
                indexed_years=indexed,
            )
            counts[status] = counts.get(status, 0) + 1
            bytes_freed += nbytes
            if status in ("would_delete", "deleted"):
                log.info("%s %s (%s)", status, detail, _human_bytes(nbytes))
            elif status == "blocked":
                if len(blocked_samples) < 10:
                    blocked_samples.append(f"{yd}: {detail}")
                log.debug("blocked %s: %s", yd, detail)

        log.info("delete-legacy summary: %s", counts)
        if blocked_samples:
            log.info("blocked examples:")
            for s in blocked_samples:
                log.info("  %s", s)
        verb = "freed" if commit else "would free"
        log.info("%s %s across deletable legacy files", verb, _human_bytes(bytes_freed))

        # Prefer sidecar paths in indexes after successful deletes
        if args.limit is not None:
            log.warning(
                "skipped rewriting file_locations.json because --limit=%d",
                args.limit,
            )
        elif commit and counts.get("deleted", 0):
            rewrite_hourly_indexes(args.root, member_files, commit=True)
            if args.refresh_219h_indexes:
                _, member_files = collect_hourly_files(
                    args.root, args.domains, args.ensembles, args.members
                )
                write_interval_indexes(
                    args.root, member_files, args.interval, dry_run=False
                )
        elif not commit:
            rewrite_hourly_indexes(args.root, member_files, commit=False)

        return 0 if counts.get("error", 0) == 0 else 1

    # --- migrate mode ---
    ensure_219h = not args.no_ensure_219h
    counts: dict[str, int] = {}
    failures: list[tuple[str, str]] = []

    tasks = [
        (str(yd), args.interval, commit, ensure_219h) for yd in year_dirs
    ]
    if args.workers <= 1:
        results = [_migrate_worker(t) for t in tasks]
    else:
        results = []
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(_migrate_worker, t): t[0] for t in tasks}
            for fut in as_completed(futs):
                results.append(fut.result())

    for year_dir, status, detail in results:
        counts[status] = counts.get(status, 0) + 1
        if status == "error":
            log.error("%s -> %s", year_dir, detail)
            failures.append((year_dir, detail or "error"))
        elif status not in ("skip_ready", "skip_no_legacy"):
            log.info("%s %s%s", status, year_dir, f" ({detail})" if detail else "")

    log.info("migrate summary: %s", counts)

    if args.limit is not None:
        log.warning(
            "skipped rewriting file_locations.json because --limit=%d; "
            "re-run without --limit after the full migrate",
            args.limit,
        )
    else:
        if not commit and (
            counts.get("would_extract", 0) + counts.get("would_migrate", 0) > 0
        ):
            log.info(
                "dry-run: after --commit, file_locations.json would be rewritten "
                "to prefer derived_hourly.nc for migrated years"
            )
        rewrite_hourly_indexes(args.root, member_files, commit=commit)
        if args.refresh_219h_indexes:
            if commit:
                _, member_files = collect_hourly_files(
                    args.root, args.domains, args.ensembles, args.members
                )
            write_interval_indexes(
                args.root,
                member_files,
                args.interval,
                dry_run=not commit,
            )

    if failures:
        log.error("%d year(s) failed", len(failures))
        return 1
    log.info("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
