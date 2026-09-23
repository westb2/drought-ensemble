#!/usr/bin/env python3
"""Periodic restart watchdog for drought-ensemble PBS runs.

Designed to run on Casper (or an interactive node with GLADE + PBS), not on
the NCAR cron host. Cron should only `qsub` the companion PBS script.

Default mode is report-only. Pass ``--apply`` to delete safe tip incompletes
and resubmit. See README.md in this directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

# Tip-year NetCDFs are read while ParFlow writes them on Lustre. HDF5 must be
# told not to take file locks, or the scan can block on the writer. Set before
# netCDF4/HDF5 is first imported (imports are lazy in netcdf_time_len).
os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")


HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "config.yaml"
LOGS_DIR = HERE / "logs"
# Written by this script after every completed scan (Casper side).
CYCLE_HEARTBEAT = LOGS_DIR / "last_cycle.txt"
# Written by cron_driver.sh after every submit attempt (cron host side).
CRON_STATUS = LOGS_DIR / "last_status.txt"
# Written by this script; read by --decide-submit / cron_driver to skip idle Casper jobs.
WAKE_STATE = LOGS_DIR / "wake_state.txt"
# --decide-submit exit codes for cron_driver.sh
DECIDE_SUBMIT = 0
DECIDE_SKIP = 10


# ---------------------------------------------------------------------------
# Sequence hashing (mirrors classes/Run.py without importing ParFlow)
# ---------------------------------------------------------------------------


def sequence2string(years: Sequence[dict], pumping_layer: int = 2) -> str:
    sequence_string = "_".join(
        f"{y['wetness']}_{y['pumping_rate_fraction']}_{y['irrigation']}" for y in years
    )
    if pumping_layer != 2:
        has_pumping = any(float(y["pumping_rate_fraction"]) > 0.0 for y in years)
        if has_pumping:
            sequence_string = f"{sequence_string}_pumping_layer_{pumping_layer}"
    return sequence_string


def hash_years(years: Sequence[dict], pumping_layer: int = 2) -> str:
    return hashlib.sha256(sequence2string(years, pumping_layer).encode()).hexdigest()


# Hourly production year vs TESTING Domain.stop_time.
PRODUCTION_YEAR_HOURS = 8760
TESTING_YEAR_HOURS = 24
_TIME_LEN_RE = re.compile(
    r"time\s*=\s*UNLIMITED\s*;\s*//\s*\((\d+)\s+currently\)"
)


def output_file_present(run_dir: Path) -> bool:
    return (run_dir / "run.out.00001.nc").exists() or (run_dir / "processed_output.nc").exists()


def netcdf_time_len(nc_path: Path) -> Optional[int]:
    """Header-only time length, or None if the file is unreadable.

    The tip year is often being written by a running ParFlow job, so this must
    never block on an HDF5 lock and must treat any read failure as "unknown".
    Unknown reads only ever mark a year incomplete, and deletes are already
    refused while a job is active on the domain.
    """
    try:
        from netCDF4 import Dataset

        with Dataset(str(nc_path), "r") as ds:
            if "time" not in ds.dimensions:
                return None
            return int(len(ds.dimensions["time"]))
    except Exception:
        proc = run_cmd(["ncdump", "-h", str(nc_path)], timeout=120)
        if proc is None or proc.returncode != 0 or not proc.stdout:
            return None
        match = _TIME_LEN_RE.search(proc.stdout)
        if match:
            return int(match.group(1))
        match = re.search(r"\btime\s*=\s*(\d+)\s*;", proc.stdout)
        if match:
            return int(match.group(1))
        return None


def year_complete(run_dir: Path, *, check_time: bool = True) -> bool:
    """Same criterion as years_to_run.py / incomplete-year-cleanup tip check.

    A ``run.out.00001.nc`` that exists but has fewer than a full year of
    timesteps is truncated (walltime/node kill) and is not complete.
    """
    nc = run_dir / "run.out.00001.nc"
    if nc.exists():
        if not check_time:
            return True
        ntime = netcdf_time_len(nc)
        if ntime is None:
            return False
        return ntime >= PRODUCTION_YEAR_HOURS or ntime == TESTING_YEAR_HOURS
    return (run_dir / "processed_output.nc").exists()


# ---------------------------------------------------------------------------
# Config / PBS helpers
# ---------------------------------------------------------------------------


def load_config(path: Path) -> dict:
    text = path.read_text()
    if path.suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required for .yaml configs (conda activate droughts)")
        return yaml.safe_load(text)
    return json.loads(text)


def run_cmd(
    cmd: Sequence[str], check: bool = False, timeout: Optional[float] = None
) -> Optional[subprocess.CompletedProcess]:
    """Run a command; return None if it exceeds ``timeout`` seconds."""
    try:
        return subprocess.run(
            list(cmd),
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None


class QstatError(RuntimeError):
    """Raised when PBS state cannot be determined (fail closed for deletes)."""


def parse_qstat_jobs(user: Optional[str] = None, server: str = "@desched1") -> List[dict]:
    """Return [{id, name, state}, ...] for the user's Derecho jobs.

    Raises QstatError if PBS cannot be queried. Callers must not delete when
    this fails — an empty job list must not be treated as "nothing running".
    """
    user = user or os.environ.get("USER", "")
    # qstat -f -u USER @desched1
    proc = run_cmd(["qstat", "-f", "-u", user, server])
    if proc.returncode != 0 and not proc.stdout:
        # Fallback: local default server (already on Derecho login)
        proc = run_cmd(["qstat", "-f", "-u", user])
    if proc.returncode != 0 and not proc.stdout.strip():
        raise QstatError(
            f"qstat failed (rc={proc.returncode}): {(proc.stderr or proc.stdout or '').strip()}"
        )
    jobs: List[dict] = []
    current: Dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if line.startswith("Job Id:"):
            if current:
                jobs.append(current)
            current = {"id": line.split(":", 1)[1].strip()}
        elif "Job_Name" in line and "=" in line:
            current["name"] = line.split("=", 1)[1].strip()
        elif "job_state" in line and "=" in line:
            current["state"] = line.split("=", 1)[1].strip()
    if current:
        jobs.append(current)
    # Successful qstat with zero jobs is OK (empty queue). A truncated/garbled
    # response with Job Id lines but no states is not.
    for job in jobs:
        if "name" not in job or "state" not in job:
            raise QstatError(f"incomplete qstat record: {job}")
    return jobs


def is_safe_raw_run_dir(path: Path, project_root: Path) -> bool:
    """Only allow deletes under domains/<domain>/raw_runs/<64-hex>/."""
    try:
        resolved = path.resolve()
        root = (project_root / "domains").resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return False
    parts = resolved.parts
    if "raw_runs" not in parts:
        return False
    # .../domains/<domain>/raw_runs/<hash>
    if resolved.parent.name != "raw_runs":
        return False
    h = resolved.name
    if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        return False
    return resolved.is_dir()


def acquire_watchdog_lock(lock_path: Path) -> Optional[int]:
    """Non-blocking exclusive lock; returns fd or None if another watchdog holds it."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    os.ftruncate(fd, 0)
    os.write(fd, f"{os.getpid()} {os.uname().nodename}\n".encode())
    return fd


def tip_has_downstream_dependents(
    tip: YearStatus, statuses: Sequence[TargetStatus], domain: str
) -> bool:
    """True if any assessed sequence on this domain has a later year dir after tip.hash.

    During shared spinup prefixes, later year hashes coincide across ensembles, so
    this also protects unwatched progress that reused the same hash path.
    """
    for st in statuses:
        if st.domain != domain:
            continue
        for ys in st.years:
            if ys.hash != tip.hash:
                continue
            if any(later.exists for later in st.years if later.index > ys.index):
                return True
    return False


# ---------------------------------------------------------------------------
# Tombstones — stop cascade peel of a year chain across cron cycles
# ---------------------------------------------------------------------------


def tombstone_dir(project_root: Path, domain: str) -> Path:
    """Hidden dir beside raw_runs hashes (does not recreate deleted year folders)."""
    return project_root / "domains" / domain / "raw_runs" / ".watchdog_tombstones"


def sequence_tombstone_path(
    project_root: Path, domain: str, ensemble: str, sequence_name: str
) -> Path:
    safe = f"{domain}__{ensemble}__{sequence_name}.json"
    return tombstone_dir(project_root, domain) / safe


def load_tombstone(path: Path) -> dict:
    if not path.is_file():
        return {"deletes": []}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"deletes": []}
    if not isinstance(data, dict):
        return {"deletes": []}
    data.setdefault("deletes", [])
    return data


def record_tip_delete(
    project_root: Path,
    *,
    domain: str,
    ensemble: str,
    sequence_name: str,
    tip: YearStatus,
) -> Path:
    """Append a delete record + per-hash marker. Call only after successful rmtree."""
    from datetime import datetime, timezone

    tdir = tombstone_dir(project_root, domain)
    tdir.mkdir(parents=True, exist_ok=True)
    seq_path = sequence_tombstone_path(project_root, domain, ensemble, sequence_name)
    data = load_tombstone(seq_path)
    entry = {
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "year_index": tip.index,
        "hash": tip.hash,
        "path": str(tip.path),
        "ensemble": ensemble,
        "sequence": sequence_name,
    }
    data["deletes"].append(entry)
    data["domain"] = domain
    data["ensemble"] = ensemble
    data["sequence"] = sequence_name
    seq_path.write_text(json.dumps(data, indent=2) + "\n")
    # Per-hash breadcrumb (survives even if sequence file is edited)
    (tdir / f"{tip.hash}.json").write_text(json.dumps(entry, indent=2) + "\n")
    return seq_path


def tombstone_blocks_delete(
    project_root: Path,
    *,
    domain: str,
    ensemble: str,
    sequence_name: str,
    tip: YearStatus,
    safety: dict,
) -> Optional[str]:
    """Return a block reason, or None if this tip delete is allowed.

    Prevents cascade peel: after deleting year N, refuse deleting year < N for the
    same sequence (the failure mode that can empty a tree over many cron cycles).

    Also stops after max_tip_deletes_per_year_index deletes of the same year
    (default 1): one auto-restart after first walltime/tip failure; a second
    failure on that same year is treated as likely repeatable and left alone.
    """
    path = sequence_tombstone_path(project_root, domain, ensemble, sequence_name)
    data = load_tombstone(path)
    deletes = data.get("deletes") or []
    if not deletes:
        return None

    prior_indices = [int(d["year_index"]) for d in deletes if "year_index" in d]
    if not prior_indices:
        return None

    max_prior = max(prior_indices)
    if safety.get("block_backward_tip_deletes", True) and tip.index < max_prior:
        return (
            f"tombstone cascade guard: already deleted year {max_prior} for this "
            f"sequence; refusing earlier tip year {tip.index} "
            f"(clear {path} to override)"
        )

    same_year_count = sum(1 for i in prior_indices if i == tip.index)
    max_same = int(safety.get("max_tip_deletes_per_year_index", 1))
    if same_year_count >= max_same:
        return (
            f"stuck_same_year: year {tip.index} already tip-deleted {same_year_count} "
            f"time(s) (max {max_same}); refusing further auto-restart "
            f"(clear {path} to override)"
        )

    unique_years = {int(d["year_index"]) for d in deletes if "year_index" in d}
    prospective = set(unique_years)
    prospective.add(tip.index)
    max_unique = int(safety.get("max_unique_tip_years_deleted_per_sequence", 10))
    if len(prospective) > max_unique:
        return (
            f"tombstone budget: would delete {len(prospective)} distinct year indices "
            f"(max {max_unique}) for this sequence; clear {path} to override"
        )
    return None


def list_stuck_same_year_targets(project_root: Path, config: Optional[dict] = None) -> List[dict]:
    """Scan tombstones for sequences blocked by repeated same-year tip failures."""
    stuck: List[dict] = []
    domains_root = project_root / "domains"
    if not domains_root.is_dir():
        return stuck
    max_same = 1
    if config:
        max_same = int((config.get("safety") or {}).get("max_tip_deletes_per_year_index", 1))
    for domain_dir in sorted(domains_root.iterdir()):
        tdir = domain_dir / "raw_runs" / ".watchdog_tombstones"
        if not tdir.is_dir():
            continue
        for path in sorted(tdir.glob("*__*.json")):
            data = load_tombstone(path)
            deletes = data.get("deletes") or []
            counts: Dict[int, int] = {}
            for d in deletes:
                if "year_index" not in d:
                    continue
                yi = int(d["year_index"])
                counts[yi] = counts.get(yi, 0) + 1
            for yi, n in sorted(counts.items()):
                if n >= max_same:
                    stuck.append(
                        {
                            "domain": data.get("domain") or domain_dir.name,
                            "ensemble": data.get("ensemble"),
                            "sequence": data.get("sequence"),
                            "year_index": yi,
                            "tip_deletes": n,
                            "tombstone": str(path),
                            "last_utc": next(
                                (
                                    d.get("utc")
                                    for d in reversed(deletes)
                                    if int(d.get("year_index", -1)) == yi
                                ),
                                None,
                            ),
                        }
                    )
    return stuck

# ---------------------------------------------------------------------------
# Heartbeat — detect a pipeline that silently stopped running at all
# ---------------------------------------------------------------------------


def _now_epoch() -> int:
    from datetime import datetime, timezone

    return int(datetime.now(timezone.utc).timestamp())


def _utc_stamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_kv_file(path: Path) -> Dict[str, str]:
    """Parse the simple key=value status files written here and by cron_driver.sh."""
    out: Dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        for line in path.read_text().splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                out[key.strip()] = value.strip()
    except OSError:
        return {}
    return out


def write_cycle_heartbeat(*, mode: str, deleted: int, submitted: int, stuck: int) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    CYCLE_HEARTBEAT.write_text(
        f"epoch={_now_epoch()}\n"
        f"utc={_utc_stamp()}\n"
        f"mode={mode}\n"
        f"deleted={deleted}\n"
        f"submitted={submitted}\n"
        f"stuck={stuck}\n"
    )


def _job_id_aliases(job_id: str) -> set:
    """PBS may show 7217032.desched1 or 7217032 — treat both as the same job."""
    jid = str(job_id).strip()
    if not jid:
        return set()
    return {jid, jid.split(".", 1)[0]}


def build_wake_state(
    *,
    statuses: Sequence[TargetStatus],
    deleted: Sequence[str],
    submitted: Sequence[str],
    planned_delete_count: int,
    planned_submit_count: int,
    apply: bool,
    quota_blocks: bool,
    no_submit: bool,
    max_idle_hours: float,
) -> Dict[str, str]:
    """Decide whether the next cron tick must start Casper (dirty) or may wait.

    dirty=0 while watched Derecho jobs are still Q/R — cron rechecks via qstat and
    only wakes Casper when a watched job leaves the queue (or max idle elapses).
    """
    watch_ids: List[str] = []
    seen: set = set()
    for st in statuses:
        jid = (st.active_job or {}).get("id")
        if jid and jid not in seen:
            watch_ids.append(str(jid))
            seen.add(str(jid))
    for jid in submitted:
        if jid and jid not in seen:
            watch_ids.append(str(jid))
            seen.add(str(jid))

    deletes_pending = planned_delete_count > len(deleted)
    if apply and planned_submit_count > 0:
        submits_pending = no_submit or quota_blocks or len(submitted) < planned_submit_count
    elif not apply and planned_submit_count > 0:
        submits_pending = True
    else:
        submits_pending = False
    if not apply and planned_delete_count > 0:
        deletes_pending = True

    actionable = deletes_pending or submits_pending
    if actionable:
        reason = "actionable_work"
    elif watch_ids:
        reason = "watching_jobs"
    elif any(st.needs_work for st in statuses):
        reason = "non_actionable_needs_work"
    else:
        reason = "clean"

    return {
        "dirty": "1" if actionable else "0",
        "reason": reason,
        "job_ids": ",".join(watch_ids),
        "epoch": str(_now_epoch()),
        "utc": _utc_stamp(),
        "max_idle_hours": str(max_idle_hours),
    }


def write_wake_state(fields: Dict[str, str], path: Path = WAKE_STATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"dirty={fields.get('dirty', '1')}",
        f"reason={fields.get('reason', 'unknown')}",
        f"job_ids={fields.get('job_ids', '')}",
        f"epoch={fields.get('epoch', str(_now_epoch()))}",
        f"utc={fields.get('utc', _utc_stamp())}",
        f"max_idle_hours={fields.get('max_idle_hours', '24')}",
    ]
    path.write_text("\n".join(lines) + "\n")


def decide_casper_submit(
    wake: Dict[str, str],
    current_job_ids: Optional[Iterable[str]],
    now: Optional[int] = None,
) -> Tuple[bool, str]:
    """Return (should_submit_casper, reason).

    ``current_job_ids is None`` means qstat failed — fail open (submit).
    """
    now_epoch = int(now if now is not None else _now_epoch())
    if not wake:
        return True, "no_wake_state"
    if wake.get("dirty") == "1":
        return True, f"dirty:{wake.get('reason', 'unknown')}"
    try:
        max_idle = float(wake.get("max_idle_hours", 24))
    except ValueError:
        max_idle = 24.0
    try:
        age_h = (now_epoch - int(wake["epoch"])) / 3600.0
    except (KeyError, ValueError):
        return True, "bad_wake_epoch"
    if age_h >= max_idle:
        return True, f"max_idle:{max_idle:.0f}h"

    watched = [x.strip() for x in wake.get("job_ids", "").split(",") if x.strip()]
    if not watched:
        return False, f"skip:{wake.get('reason', 'clean')}"

    if current_job_ids is None:
        return True, "qstat_unavailable"

    present: set = set()
    for jid in current_job_ids:
        present |= _job_id_aliases(str(jid))
    for jid in watched:
        if _job_id_aliases(jid).isdisjoint(present):
            return True, f"job_left_queue:{jid}"
    return False, "skip:watching_jobs_still_present"


def run_decide_submit(
    *,
    wake_path: Path = WAKE_STATE,
    current_job_ids: Optional[Sequence[str]] = None,
    probe_qstat: bool = True,
) -> Tuple[int, str]:
    """CLI helper for cron: exit DECIDE_SUBMIT or DECIDE_SKIP with a one-line reason."""
    wake = read_kv_file(wake_path)
    ids: Optional[List[str]]
    if current_job_ids is not None:
        ids = list(current_job_ids)
    elif probe_qstat:
        try:
            ids = [j["id"] for j in parse_qstat_jobs() if j.get("id")]
        except QstatError:
            ids = None
    else:
        ids = []
    submit, reason = decide_casper_submit(wake, ids)
    return (DECIDE_SUBMIT if submit else DECIDE_SKIP), reason


def check_heartbeat(config: Optional[dict] = None) -> dict:
    """Report whether cron decides and Casper scans are still happening.

    Cron may skip Casper when wake_state is clean, so completed-scan age is
    allowed up to ``max_idle_scan_hours`` (forced wake interval). Cron status
    must still refresh on the shorter ``max_heartbeat_age_hours`` cadence.
    """
    max_cron_age_h = 12.0
    max_cycle_age_h = 24.0
    if config:
        safety = config.get("safety") or {}
        max_cron_age_h = float(safety.get("max_heartbeat_age_hours", 12))
        max_cycle_age_h = float(
            safety.get("max_idle_scan_hours", safety.get("max_heartbeat_age_hours", 24))
        )
    now = _now_epoch()

    def age_hours(data: Dict[str, str]) -> Optional[float]:
        try:
            return (now - int(data["epoch"])) / 3600.0
        except (KeyError, ValueError):
            return None

    cron = read_kv_file(CRON_STATUS)
    cycle = read_kv_file(CYCLE_HEARTBEAT)
    wake = read_kv_file(WAKE_STATE)
    cron_age = age_hours(cron)
    cycle_age = age_hours(cycle)

    problems: List[str] = []
    if not cron:
        problems.append(f"no cron status file at {CRON_STATUS} (cron driver never ran?)")
    else:
        if cron.get("result") != "ok":
            problems.append(f"last cron submit FAILED: {cron.get('detail', 'unknown')}")
        if cron_age is not None and cron_age > max_cron_age_h:
            problems.append(f"last cron submit was {cron_age:.1f}h ago (>{max_cron_age_h:.0f}h)")

    if not cycle:
        problems.append(
            f"no completed scan recorded at {CYCLE_HEARTBEAT} (Casper job never ran?)"
        )
    elif cycle_age is not None and cycle_age > max_cycle_age_h:
        problems.append(
            f"last completed scan was {cycle_age:.1f}h ago (>{max_cycle_age_h:.0f}h idle max)"
        )

    return {
        "healthy": not problems,
        "problems": problems,
        "cron": cron,
        "cron_age_hours": cron_age,
        "cycle": cycle,
        "cycle_age_hours": cycle_age,
        "wake": wake,
        "max_age_hours": max_cron_age_h,
        "max_cycle_age_hours": max_cycle_age_h,
    }


def parse_scratch_free_tib(gladequota_text: str) -> Optional[float]:
    """Parse free TiB on /glade/derecho/scratch/<user> from gladequota output."""
    for line in gladequota_text.splitlines():
        if "/glade/derecho/scratch/" not in line:
            continue
        # Space Used Quota %Full #Files — units like "26.61 TiB" "30.00 TiB"
        m = re.search(
            r"/glade/derecho/scratch/\S+\s+(\d+(?:\.\d+)?)\s*([KMGT]i?B)\s+(\d+(?:\.\d+)?)\s*([KMGT]i?B)",
            line,
        )
        if not m:
            continue
        used, used_u, quota, quota_u = m.groups()

        def to_tib(val: str, unit: str) -> float:
            v = float(val)
            u = unit.upper().replace("IB", "B")
            scale = {"B": 1 / 1024**4, "KB": 1 / 1024**3, "MB": 1 / 1024**2, "GB": 1 / 1024, "TB": 1}
            # gladequota prints TiB
            if "TI" in unit.upper() or unit.upper() == "TB":
                return v
            if "GI" in unit.upper() or unit.upper() == "GB":
                return v / 1024.0
            return v * scale.get(u, 0.0)

        return to_tib(quota, quota_u) - to_tib(used, used_u)
    return None


def scratch_free_tib() -> Optional[float]:
    proc = run_cmd(["gladequota"])
    if proc.returncode != 0 and not proc.stdout:
        return None
    return parse_scratch_free_tib(proc.stdout)


# ---------------------------------------------------------------------------
# Status model
# ---------------------------------------------------------------------------


@dataclass
class YearStatus:
    index: int
    hash: str
    path: Path
    exists: bool
    complete: bool


@dataclass
class TargetStatus:
    domain: str
    ensemble: str
    sequence_name: str
    sequence_path: Path
    years: List[YearStatus]
    tip_incomplete: Optional[YearStatus] = None
    mid_incomplete: List[YearStatus] = field(default_factory=list)
    missing_years: List[int] = field(default_factory=list)
    needs_work: bool = False
    blocked_reason: Optional[str] = None
    active_job: Optional[dict] = None


def job_name_for(domain: str, ensemble: str, sequence_name: str) -> str:
    return f"{domain}_{ensemble}_{sequence_name}"


def assess_sequence(
    project_root: Path,
    domain: str,
    ensemble: str,
    sequence_path: Path,
) -> TargetStatus:
    seq = json.loads(sequence_path.read_text())
    years_spec = seq["years"]
    pumping_layer = int(seq.get("pumping_layer", 2))
    name = seq["name"]
    raw = project_root / "domains" / domain / "raw_runs"

    year_statuses: List[YearStatus] = []
    for i in range(len(years_spec)):
        h = hash_years(years_spec[: i + 1], pumping_layer)
        path = raw / h
        exists = path.is_dir()
        # Cheap file-presence for prefixes; time-length is checked on the tip.
        complete = output_file_present(path) if exists else False
        year_statuses.append(
            YearStatus(index=i, hash=h, path=path, exists=exists, complete=complete)
        )

    last_existing = next((ys for ys in reversed(year_statuses) if ys.exists), None)
    if last_existing is not None:
        last_existing.complete = year_complete(last_existing.path)

    tip_incomplete = None
    mid_incomplete: List[YearStatus] = []
    missing: List[int] = []

    for ys in year_statuses:
        later_exist = any(later.exists for later in year_statuses[ys.index + 1 :])
        if not ys.exists:
            missing.append(ys.index)
        elif not ys.complete:
            if later_exist:
                mid_incomplete.append(ys)
            else:
                tip_incomplete = ys  # highest index wins as we walk forward

    needs = bool(missing or tip_incomplete or mid_incomplete)

    return TargetStatus(
        domain=domain,
        ensemble=ensemble,
        sequence_name=name,
        sequence_path=sequence_path,
        years=year_statuses,
        tip_incomplete=tip_incomplete,
        mid_incomplete=mid_incomplete,
        missing_years=missing,
        needs_work=needs,
    )


def iter_watch_targets(config: dict, project_root: Path) -> Iterable[Tuple[str, str, Path]]:
    for entry in config.get("watch") or []:
        ensemble = entry["ensemble"]
        domains = entry["domains"]
        seq_dir = project_root / "run_sequences" / ensemble
        if not seq_dir.is_dir():
            print(f"WARNING: missing ensemble folder {seq_dir}", file=sys.stderr)
            continue
        if entry.get("sequences"):
            names = list(entry["sequences"])
            paths = [seq_dir / (n if n.endswith(".json") else f"{n}.json") for n in names]
        else:
            paths = sorted(seq_dir.glob("*.json"))
        for domain in domains:
            for path in paths:
                if not path.is_file():
                    print(f"WARNING: missing sequence {path}", file=sys.stderr)
                    continue
                yield domain, ensemble, path


def apply_job_guards(
    status: TargetStatus,
    jobs: List[dict],
    safety: dict,
) -> None:
    wanted = job_name_for(status.domain, status.ensemble, status.sequence_name)
    for job in jobs:
        if job.get("name") == wanted and job.get("state") in {"R", "Q", "H", "S"}:
            status.active_job = job
            if safety.get("skip_if_queued_or_running", True):
                status.blocked_reason = f"active job {job.get('id')} state={job.get('state')}"
            return


def domain_has_running_job(domain: str, jobs: List[dict]) -> bool:
    prefix = f"{domain}_"
    return any(j.get("state") == "R" and str(j.get("name", "")).startswith(prefix) for j in jobs)


def gb_per_year(config: dict, domain: str) -> float:
    table = (config.get("quota") or {}).get("gb_per_year") or {}
    return float(table.get(domain, table.get("default", 50)))


def estimate_new_years_gb(status: TargetStatus, config: dict) -> float:
    """Estimate disk for years that still need to run (missing + tip redo)."""
    indices = set(status.missing_years)
    if status.tip_incomplete:
        indices.add(status.tip_incomplete.index)
    # After tip delete, that year is "new" again; later missing years too.
    # Shared complete prefixes are not counted.
    n = len(indices)
    return n * gb_per_year(config, status.domain)


def build_pbs_script(
    *,
    project_root: Path,
    domain: str,
    ensemble: str,
    sequence_path: Path,
    sequence_name: str,
    pbs_cfg: dict,
    testing: bool,
) -> str:
    job = job_name_for(domain, ensemble, sequence_name)
    walltime = pbs_cfg.get("walltime", "12:00:00")
    account = pbs_cfg.get("account", "UPRI0032")
    queue = pbs_cfg.get("queue", "main@desched1")
    select = pbs_cfg.get("select", "4:ncpus=64:mpiprocs=64")
    mail = pbs_cfg.get("mail", "")
    out_dir = project_root / pbs_cfg.get("pbs_output_dir", "ensemble_running/pbs_outputs")
    mail_lines = ""
    if mail:
        mail_lines = f"#PBS -m bae\n#PBS -M {mail}\n"
    return f"""#!/bin/bash
#PBS -N {job}
#PBS -A {account}
#PBS -q {queue}
{mail_lines}#PBS -l walltime={walltime}
#PBS -l select={select}
#PBS -j oe
module load conda
conda activate droughts
cd {out_dir}
source ~/pf_env.sh
python3 ../run_sequence_on_domain.py {domain} {sequence_path} {project_root} {ensemble} {testing}
"""


def submit_job(script_text: str, dry_run: bool) -> Optional[str]:
    if dry_run:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".pbs", delete=False) as fh:
        fh.write(script_text)
        path = fh.name
    try:
        proc = run_cmd(["qsub", path])
        if proc.returncode != 0:
            print(f"qsub failed: {proc.stderr or proc.stdout}", file=sys.stderr)
            return None
        return proc.stdout.strip()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def dir_size_gb(path: Path) -> float:
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += (Path(root) / name).stat().st_size
                except OSError:
                    pass
    except OSError:
        return 0.0
    return total / (1024**3)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Watch list config (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete safe tip incompletes and qsub restarts (default: dry-run report)",
    )
    parser.add_argument(
        "--no-delete",
        action="store_true",
        help="With --apply, submit only; never rm tip folders",
    )
    parser.add_argument(
        "--no-submit",
        action="store_true",
        help="With --apply, allow deletes but do not qsub",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write machine-readable summary JSON",
    )
    parser.add_argument(
        "--list-stuck",
        action="store_true",
        help="Print sequences blocked by repeated same-year tip failures and exit",
    )
    parser.add_argument(
        "--heartbeat",
        action="store_true",
        help="Report whether cron submits and Casper scans are still happening, then exit",
    )
    parser.add_argument(
        "--decide-submit",
        action="store_true",
        help=(
            "Cron helper: exit 0 to qsub Casper, 10 to skip. Uses wake_state.txt + "
            "lightweight qstat (stdlib only; no PyYAML)."
        ),
    )
    parser.add_argument(
        "--current-job-ids",
        default=None,
        help="Comma-separated job ids for --decide-submit (skip live qstat; tests)",
    )
    parser.add_argument(
        "--wake-state",
        type=Path,
        default=WAKE_STATE,
        help="Path to wake_state.txt (default: logs/wake_state.txt)",
    )
    args = parser.parse_args(argv)

    # Must run before load_config: cron host may lack PyYAML.
    if args.decide_submit:
        injected = None
        if args.current_job_ids is not None:
            injected = [x.strip() for x in args.current_job_ids.split(",") if x.strip()]
        code, reason = run_decide_submit(
            wake_path=args.wake_state,
            current_job_ids=injected,
            probe_qstat=injected is None,
        )
        print(reason)
        return code

    config = load_config(args.config)
    project_root = Path(config.get("project_root") or HERE.parents[1]).resolve()
    safety = config.get("safety") or {}
    pbs_cfg = config.get("pbs") or {}
    quota_cfg = config.get("quota") or {}

    if args.heartbeat:
        hb = check_heartbeat(config)
        if hb["healthy"]:
            print(
                f"watchdog healthy: last cron submit {hb['cron_age_hours']:.1f}h ago, "
                f"last completed scan {hb['cycle_age_hours']:.1f}h ago"
            )
        else:
            print("watchdog UNHEALTHY:")
            for problem in hb["problems"]:
                print(f"  - {problem}")
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(json.dumps(hb, indent=2))
        return 0 if hb["healthy"] else 1

    if args.list_stuck:
        stuck = list_stuck_same_year_targets(project_root, config)
        if not stuck:
            print("No stuck_same_year tombstones found.")
            return 0
        print(f"stuck_same_year targets ({len(stuck)}):")
        for s in stuck:
            print(
                f"  {s['domain']} / {s['ensemble']} / {s['sequence']} "
                f"year={s['year_index']} tip_deletes={s['tip_deletes']} "
                f"last={s['last_utc']} tombstone={s['tombstone']}"
            )
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(json.dumps({"stuck_same_year": stuck}, indent=2))
        return 0

    # TESTING flag from ensemble_running/config.py without importing side effects
    testing = False
    cfg_py = project_root / "ensemble_running" / "config.py"
    if cfg_py.is_file():
        for line in cfg_py.read_text().splitlines():
            if line.strip().startswith("TESTING"):
                testing = "True" in line.split("=", 1)[-1]
                break

    lock_fd = None
    if args.apply:
        lock_path = HERE / "logs" / "watchdog.apply.lock"
        lock_fd = acquire_watchdog_lock(lock_path)
        if lock_fd is None:
            print(f"Another apply watchdog holds {lock_path}; exiting without changes")
            return 0

    try:
        return _main_after_lock(args, config, project_root, safety, pbs_cfg, quota_cfg, testing)
    finally:
        if lock_fd is not None:
            try:
                import fcntl

                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)


def _main_after_lock(args, config, project_root, safety, pbs_cfg, quota_cfg, testing) -> int:
    try:
        jobs = parse_qstat_jobs()
        qstat_ok = True
        qstat_error = None
    except QstatError as exc:
        jobs = []
        qstat_ok = False
        qstat_error = str(exc)

    free_tib = scratch_free_tib()
    min_free = float(quota_cfg.get("min_free_tib", 1.5))

    print(f"project_root={project_root}")
    print(f"mode={'APPLY' if args.apply else 'DRY-RUN'}")
    if qstat_ok:
        print(f"derecho jobs seen: {len(jobs)}")
    else:
        print(f"derecho jobs seen: UNAVAILABLE ({qstat_error})")
        print("FAIL CLOSED: refusing all deletes/submits without PBS state")
    if free_tib is None:
        print("scratch free: (could not parse gladequota)")
    else:
        print(f"scratch free: {free_tib:.2f} TiB (min required for submit: {min_free:.2f})")
    print()

    if not qstat_ok:
        max_idle = float(safety.get("max_idle_scan_hours", 24))
        write_wake_state(
            {
                "dirty": "1",
                "reason": "qstat_failed",
                "job_ids": "",
                "epoch": str(_now_epoch()),
                "utc": _utc_stamp(),
                "max_idle_hours": str(max_idle),
            }
        )
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(
                json.dumps({"mode": "aborted", "reason": "qstat_failed", "error": qstat_error}, indent=2)
            )
        return 2

    statuses: List[TargetStatus] = []
    for domain, ensemble, seq_path in iter_watch_targets(config, project_root):
        st = assess_sequence(project_root, domain, ensemble, seq_path)
        apply_job_guards(st, jobs, safety)
        if st.mid_incomplete and not st.blocked_reason:
            paths = ", ".join(str(m.path) for m in st.mid_incomplete)
            st.blocked_reason = f"mid-sequence incomplete (not auto-deleting): {paths}"
        statuses.append(st)

    deletes: List[Tuple[TargetStatus, YearStatus]] = []
    submits: List[TargetStatus] = []
    reports: List[dict] = []

    for st in statuses:
        tip = st.tip_incomplete
        complete = all(y.exists and y.complete for y in st.years) and not st.mid_incomplete
        line = f"{st.domain} / {st.ensemble} / {st.sequence_name}"
        if complete:
            print(f"OK      {line}")
            reports.append({"target": line, "status": "complete"})
            continue

        detail_parts = []
        if tip:
            detail_parts.append(f"tip_incomplete year={tip.index} {tip.path}")
        if st.missing_years:
            detail_parts.append(f"missing_years={st.missing_years}")
        if st.mid_incomplete:
            detail_parts.append(f"mid_incomplete={[m.index for m in st.mid_incomplete]}")
        if st.blocked_reason:
            detail_parts.append(f"blocked={st.blocked_reason}")
        print(f"NEED    {line}")
        for part in detail_parts:
            print(f"        {part}")

        tombstone_reason = None
        if tip is not None:
            tombstone_reason = tombstone_blocks_delete(
                project_root,
                domain=st.domain,
                ensemble=st.ensemble,
                sequence_name=st.sequence_name,
                tip=tip,
                safety=safety,
            )

        can_delete = (
            tip is not None
            and safety.get("delete_tip_incompletes", True)
            and not args.no_delete
            and not (
                safety.get("no_delete_while_domain_running", True)
                and domain_has_running_job(st.domain, jobs)
            )
            and st.active_job is None
            and not st.mid_incomplete
            and is_safe_raw_run_dir(tip.path, project_root)
            and not tip_has_downstream_dependents(tip, statuses, st.domain)
            and tombstone_reason is None
        )
        # If tip incomplete but domain has R job, block delete
        if tip and safety.get("no_delete_while_domain_running", True) and domain_has_running_job(
            st.domain, jobs
        ):
            if not st.blocked_reason:
                st.blocked_reason = "domain has Running job; refusing tip delete"
            can_delete = False
        if tip and tip_has_downstream_dependents(tip, statuses, st.domain):
            if not st.blocked_reason:
                st.blocked_reason = "tip hash has downstream year dirs; refusing delete"
            can_delete = False
        if tip and not is_safe_raw_run_dir(tip.path, project_root):
            if not st.blocked_reason:
                st.blocked_reason = f"refusing delete of unsafe path {tip.path}"
            can_delete = False
        if tip and tombstone_reason:
            if not st.blocked_reason:
                st.blocked_reason = tombstone_reason
            can_delete = False
            print(f"        blocked={tombstone_reason}")

        if tip and can_delete and not any(t.path == tip.path for _, t in deletes):
            deletes.append((st, tip))

        can_submit = (
            st.needs_work
            and st.active_job is None
            and not st.blocked_reason
            and not st.mid_incomplete
        )
        # After planned tip delete, missing includes that year — OK to submit
        if tip and not can_delete and tip.exists and not tip.complete:
            can_submit = False
            if not st.blocked_reason:
                st.blocked_reason = "tip incomplete but not safe to delete"
            print(f"        blocked={st.blocked_reason}")

        if can_submit:
            submits.append(st)

        reports.append(
            {
                "target": line,
                "status": "needs_work",
                "tip_incomplete": str(tip.path) if tip else None,
                "missing_years": st.missing_years,
                "blocked": st.blocked_reason,
                "will_delete": str(tip.path) if tip and can_delete else None,
                "will_submit": can_submit,
                "est_gb": estimate_new_years_gb(st, config),
            }
        )

    # Quota gate for submits
    est_total_gb = sum(estimate_new_years_gb(st, config) for st in submits)
    print()
    print(f"planned tip deletes: {len(deletes)}")
    for st, tip in deletes:
        print(f"  rm -rf {tip.path}  (~{dir_size_gb(tip.path):.1f} GB)")
    print(f"planned submits: {len(submits)} (est ~{est_total_gb:.0f} GB new)")
    for st in submits:
        print(
            f"  qsub {job_name_for(st.domain, st.ensemble, st.sequence_name)} "
            f"(est {estimate_new_years_gb(st, config):.0f} GB)"
        )

    quota_blocks = free_tib is not None and free_tib < min_free
    if quota_blocks:
        print(f"\nQUOTA GATE: free {free_tib:.2f} TiB < min {min_free:.2f} TiB — submits skipped")

    max_submits = int(safety.get("max_submits_per_cycle", 20))
    if len(submits) > max_submits:
        print(f"capping submits at max_submits_per_cycle={max_submits}")
        submits = submits[:max_submits]

    max_deletes = int(safety.get("max_deletes_per_cycle", 8))
    if len(deletes) > max_deletes:
        print(
            f"REFUSING deletes: {len(deletes)} > max_deletes_per_cycle={max_deletes} "
            "(possible logic bug); submits also skipped"
        )
        deletes = []
        submits = []

    deleted: List[str] = []
    submitted: List[str] = []

    if args.apply:
        if not args.no_delete:
            for st, tip in deletes:
                path = tip.path
                if not is_safe_raw_run_dir(path, project_root):
                    print(f"SKIP unsafe path {path}", file=sys.stderr)
                    continue
                # Re-check completeness immediately before rm (TOCTOU)
                if year_complete(path):
                    print(f"SKIP {path} — became complete since scan")
                    continue
                # Re-check tombstone (another cycle may have written)
                reason = tombstone_blocks_delete(
                    project_root,
                    domain=st.domain,
                    ensemble=st.ensemble,
                    sequence_name=st.sequence_name,
                    tip=tip,
                    safety=safety,
                )
                if reason:
                    print(f"SKIP {path} — {reason}")
                    continue
                print(f"deleting {path}")
                shutil.rmtree(path)
                marker = record_tip_delete(
                    project_root,
                    domain=st.domain,
                    ensemble=st.ensemble,
                    sequence_name=st.sequence_name,
                    tip=tip,
                )
                print(f"  tombstone -> {marker}")
                deleted.append(str(path))
        if not args.no_submit and not quota_blocks:
            out_dir = project_root / pbs_cfg.get("pbs_output_dir", "ensemble_running/pbs_outputs")
            out_dir.mkdir(parents=True, exist_ok=True)
            for st in submits:
                script = build_pbs_script(
                    project_root=project_root,
                    domain=st.domain,
                    ensemble=st.ensemble,
                    sequence_path=st.sequence_path,
                    sequence_name=st.sequence_name,
                    pbs_cfg=pbs_cfg,
                    testing=testing,
                )
                jid = submit_job(script, dry_run=False)
                print(f"submitted {job_name_for(st.domain, st.ensemble, st.sequence_name)} -> {jid}")
                if jid:
                    submitted.append(jid)
        elif args.apply and not args.no_submit and quota_blocks:
            print("skipping submits due to quota gate")
    else:
        print("\nDry-run only. Re-run with --apply to delete tips and submit.")

    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "free_tib": free_tib,
        "deleted": deleted,
        "submitted": submitted,
        "planned_deletes": [str(tip.path) for _, tip in deletes],
        "planned_submits": [
            job_name_for(st.domain, st.ensemble, st.sequence_name) for st in submits
        ],
        "reports": reports,
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(summary, indent=2))
        print(f"wrote {args.json_out}")

    write_cycle_heartbeat(
        mode=summary["mode"],
        deleted=len(deleted),
        submitted=len(submitted),
        stuck=len(list_stuck_same_year_targets(project_root, config)),
    )

    max_idle = float(safety.get("max_idle_scan_hours", 24))
    wake = build_wake_state(
        statuses=statuses,
        deleted=deleted,
        submitted=submitted,
        planned_delete_count=len(deletes),
        planned_submit_count=len(submits),
        apply=bool(args.apply),
        quota_blocks=bool(quota_blocks),
        no_submit=bool(args.no_submit),
        max_idle_hours=max_idle,
    )
    write_wake_state(wake)
    print(
        f"wake_state dirty={wake['dirty']} reason={wake['reason']} "
        f"job_ids={wake['job_ids'] or '(none)'} max_idle_h={wake['max_idle_hours']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
