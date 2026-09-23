# Restart watchdog (NCAR cron → Casper → Derecho)

Unattended tip-cleanup and resubmit for drought-ensemble ParFlow jobs.

Cron on `cron.hpc.ucar.edu` only submits a **Casper** job. That job runs
`restart_watchdog.py`, which may delete safe incomplete **tip** year folders and
`qsub` Derecho restarts. The cron host is memory-capped (~1 GB) and is not
where the scan runs.

Apply is **on** (`WATCHDOG_APPLY=1` in `watchdog.pbs`). Set it to `0` for
report-only Casper jobs.

Installed crontab (cron host):

```
15 */3 * * * /glade/derecho/scratch/bwest/drought-ensemble/ensemble_running/watchdog/cron_driver.sh
```

Watch list is `config.yaml` (`watch:`). Currently: `potomac2` and `wolf2` ×
`3_year_pumping_tests` and `3_year_pumping_tests_layer4`.

## Layout

| File | Role |
|------|------|
| `cron_driver.sh` | Cron-safe: PATH, lock, preflight, `qsub` Casper, status + email |
| `watchdog.pbs` | Casper job: conda + `restart_watchdog.py --apply` |
| `restart_watchdog.py` | Scan, tombstones, quota gate, optional delete + Derecho `qsub` |
| `config.yaml` | Watch list and safety knobs |
| `audit_year_outputs.py` | Read-only sweep: every year dir of every watch target, flags short/unreadable output |
| `logs/` | Driver log, heartbeats, scan logs, Casper PBS stdout |

## Why not a Derecho login-node daemon

Login-node long-lived processes get killed. NCAR’s supported path is
[cron.hpc.ucar.edu](https://ncar-hpc-docs.readthedocs.io/en/latest/compute-systems/additional-resources/cron/):
a thin trigger that starts work on Casper/Derecho.

## Pipeline

```
cron (every 3h at :15)
  cron_driver.sh
    restart_watchdog.py --decide-submit   # wake_state + light qstat
      skip → write last_status skipped (no Casper)
      else → qsub casper@casper-pbs watchdog.pbs
         conda activate droughts
         restart_watchdog.py --apply
            qstat @desched1, gladequota, scan watch list
            maybe rm tip / qsub Derecho
            write wake_state.txt (dirty + watched job ids)
```

Cron still fires every 3 h, but Casper only starts when:

| Condition | Action |
|-----------|--------|
| No `wake_state.txt` yet | Submit (bootstrap) |
| `dirty=1` (actionable work left) | Submit |
| A watched Derecho job id left Q/R | Submit |
| Scan older than `max_idle_scan_hours` (24 h) | Submit |
| Clean / only watching jobs still present | **Skip** Casper |

Heartbeats:

| File | Writer | Meaning |
|------|--------|---------|
| `logs/last_status.txt` | `cron_driver.sh` | Last cron decide/submit (`result=ok` or `fail`) |
| `logs/last_cycle.txt` | `restart_watchdog.py` | Last completed scan (Casper actually ran) |
| `logs/wake_state.txt` | `restart_watchdog.py` | Dirty flag + job ids for cron skip logic |

`--heartbeat`: cron status must stay fresh (`max_heartbeat_age_hours`, 12 h). Completed
scans may be older while Casper is skipped, up to `max_idle_scan_hours` (24 h).

## Commands

From `drought-ensemble/` (login node or Casper, `conda activate droughts`):

```bash
python3 ensemble_running/watchdog/restart_watchdog.py              # dry-run report
python3 ensemble_running/watchdog/restart_watchdog.py --apply      # delete+submit
python3 ensemble_running/watchdog/restart_watchdog.py --heartbeat  # pipeline alive?
python3 ensemble_running/watchdog/restart_watchdog.py --list-stuck # same-year holds
python3 ensemble_running/watchdog/restart_watchdog.py --decide-submit  # cron: 0=qsub, 10=skip
```

Cron-like selftest (must use `env -i`, not interactive SSH PATH):

```bash
ssh cron.hpc.ucar.edu
env -i /bin/bash /glade/derecho/scratch/bwest/drought-ensemble/ensemble_running/watchdog/cron_driver.sh --selftest
```

Logs: `ensemble_running/watchdog/logs/` (`cron_driver.log`, `watchdog_*.log`,
`summary_*.json`, Casper `*.casper-pbs.OU`).

## Safety

- Skip a domain/ensemble/sequence that already has a matching job in `R`/`Q`/`H`/`S`.
- Delete **only tip incompletes**: folder exists, no usable full-year
  `run.out.00001.nc` (missing, unreadable, or time length &lt; 8760 / ≠ 24)
  / no `processed_output.nc`, and no later year dirs for that sequence.
- Never auto-delete mid-sequence incompletes.
- Refuse tip deletes on a domain while any job **named `<domain>_*`** is `R`
  (shared-hash risk). Jobs named e.g. `migrate_potomac_droughts` do **not**
  match this guard.
- `qstat` failure → fail **closed** (no deletes/submits).
- Apply flock so overlapping Casper jobs do not both delete.
- Delete path must be `domains/<domain>/raw_runs/<64-hex>/`.
- Re-check completeness immediately before `rm`.
- Skip Derecho submits if scratch free < `quota.min_free_tib` (1.5 TiB).
- Cap: 20 submits/cycle; refuse **all** deletes+submits if more than 8 tips
  would be deleted (possible logic bug).

### Tombstones

After each successful tip delete:

`domains/<domain>/raw_runs/.watchdog_tombstones/`

- `<hash>.json` — breadcrumb for that folder
- `<domain>__<ensemble>__<sequence>.json` — history for that target

Rules:

- Refuse deleting year index **&lt; highest already-deleted year** (cascade peel).
- Same year: **one** tip delete then stop (`max_tip_deletes_per_year_index: 1`).
  A second death on that year is treated as a repeatable error; folder is left
  for inspection. Clear the sequence JSON to allow another auto-restart.
- At most **10** distinct year indices deleted per sequence
  (`max_unique_tip_years_deleted_per_sequence`). Walltime kills that move
  forward still work until that budget.

`--list-stuck` reports sequences held by the same-year rule.

## Disk cleanup (`migrate_to_sidecar.py`) vs watchdog

Typical migrate job (`--domains potomac2 --ensembles droughts --delete-legacy`)
does **not** race the current watch list:

- Migrate only removes legacy `processed_output.nc` after `run.out.00001.nc`,
  sidecar, and 219h all exist. Watchdog completeness still sees `run.out.00001.nc`.
- Layer-4 pumping hashes diverge at year 40; droughts migrate does not delete
  those folders.
- Shared spinup years 0–39 can be read by both; ParFlow **skips** existing
  year dirs.

Residual: a migrate job name that does not start with `<domain>_` will not
block watchdog tip deletes on that domain. Do not watch + migrate the same
incomplete tip without checking job names.

Quota timing: migrate frees space; a watchdog resubmit consumes it. If
ParFlow starts before migrate reclaims, scratch is tighter than the reverse.

## Outages / bugs already hit (do not regress)

### Aug 2026: `qsub: command not found` (six days, silent)

Cron’s environment is `PATH=/usr/local/bin:/usr/bin:/bin`. PBS is
`/opt/pbs/bin/qsub`. Interactive `ssh cron.hpc.ucar.edu` sources `/etc/profile`
and **hides** this. Every cycle logged failure in `cron_driver.log` and never
submitted Casper. `cron_driver.sh` now prepends `/opt/pbs/bin` and prefights
`qsub`. Always verify with `env -i`.

### Aug–Sep 2026: cron `python3` is 3.6 (`from __future__ import annotations`)

Cron’s `/usr/bin/python3` → 3.6.15. `restart_watchdog.py` needs 3.7+
(`annotations` future + dataclasses), so every `--decide-submit` raised
`SyntaxError` and never submitted Casper (~2.5 weeks). `cron_driver.sh` now
resolves a GLADE Python ≥3.7 (prefers `droughts` conda, then derecho apps)
before decide-submit / selftest. Always verify with `env -i`.

### Aug 2026: conda + `set -u`

Once PATH was fixed, Casper died on `conda activate droughts`: an NCL hook
references unbound `CONDA_ENV_PATH`. `watchdog.pbs` uses `set +u` around
conda. Also: `tee` used to mask Python’s exit code (`PIPESTATUS`).

### Cron `HOME` unbound under `env -i`

Lock path falls back to `/glade/u/home/bwest` if `HOME` is unset.

## Email

`benjaminwest@arizona.edu`

- Driver: cannot submit (one alert per 24 h while still failing).
- Casper: non-zero scan.
- PBS `-m ae` on the Casper wrapper.

## One-time setup (if reinstalling)

1. Edit `config.yaml` `watch:`.
2. Dry-run on a login node, then `--apply` once if the report is right.
3. `env -i …/cron_driver.sh --selftest` on the cron host.
4. Crontab as above.
5. Confirm `--heartbeat` is healthy after one Casper cycle (`logs/watchdog_*.log`
   and `last_cycle.txt` exist).

This is narrower than the interactive `restart-ensemble-jobs` skill (no
wrong-rate hash deletes, no interactive confirmation).
