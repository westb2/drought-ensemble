---
name: restart-ensemble-jobs
description: >-
  Restart drought-ensemble PBS jobs after walltime/quota/mid-year failures:
  inspect recent ensemble_running logs, remove incomplete raw_runs year
  folders (with confirmation), check scratch quota, and resubmit via
  run_ensemble.py. Use when the user asks to restart ensemble jobs, re-run
  failed drought/spinup sequences, resume mid-failed ParFlow years, or clean
  up incomplete raw_runs before qsub.
---

# Restart ensemble jobs

Use this for mid-failed multi-year ParFlow ensemble runs under `drought-ensemble/`.

## Required companion rule

**Before identifying or deleting any incomplete year folders, read and follow:**

`.cursor/rules/incomplete-year-cleanup.mdc`

That rule is the source of truth for tip vs mid-sequence incompletes, active-job guards, and path shape (`domains/<domain>/raw_runs/<hash>`).

## Workflow

Copy and track:

```
Restart progress:
- [ ] 1. qstat + recent job outcomes
- [ ] 2. Incomplete / bad year folders (via incomplete-year-cleanup rule)
- [ ] 3. Collision check (active jobs + later-year deps)
- [ ] 4. User confirms deletes
- [ ] 5. Scratch quota headroom
- [ ] 6. Resubmit (subset if needed)
- [ ] 7. Report job IDs
```

### 1. qstat + recent job outcomes

Always start with `qstat -u $USER` (`R` = running, `Q` = queued).

In `ensemble_running/`, inspect newest `*.o<jobid>` logs (`ls -lt *.o* | head`).

For each job, record:
- job name / id / state
- domain + ensemble + sequence
- outcome: finished vs killed (`walltime … exceeded`, `Disk quota exceeded`, other errors)
- any `raw_runs/<hash>` path in I/O errors

**Do not delete folders owned by `R` jobs.** Progress is often only in `run_log.txt` (PBS stdout may stay quiet for hours).

### 2. Incomplete / bad year folders

Follow `.cursor/rules/incomplete-year-cleanup.mdc`.

Cross-check: last `Running year N …/raw_runs/<hash>` in  
`domains/<domain>/processed_full_runs/<ensemble>/<member>/run_log.txt`  
must match the tip folder from the PBS log.

**Wrong-rate / formula fixes:** hash ignores computed fluxes. After fixing pumping math, delete only the **pumping** year hashes for that sequence (not shared spinup), or resubmit will skip and keep bad rates.

### 3. Collision check before proposing deletes

For each candidate hash on domain D:

- No **`R`** job on D is writing it.
- No **later year dirs** exist for sequences that use this hash as a prefix (unless the user explicitly wants a full re-chain).
- Same hash on **other domains** is unrelated — leave those alone unless asked.

Say clearly whether each path is tip-incomplete vs wrong-rate-complete.

### 4. Confirm before delete

**Always list exact folder paths (and approximate sizes) and wait for explicit user approval.** Never delete without confirmation.

After approval: `rm -rf` only those folders. Keep prior complete / mid-sequence IC years.

### 5. Scratch quota

Run `gladequota` **before** submitting. Rough finished-year sizes (full `raw_runs` dir): wolf2 ~20 GB, potomac2 ~56 GB, republican ~96 GB.

Estimate **unique new years** across the submit set (shared prefixes count once per domain). If free ≪ need, stop — propose deletes or cancel/hold large domains (e.g. republican) rather than submitting into a full scratch.

For **12 h walltime planning**, see `.cursor/skills/drought-ensemble/SKILL.md`. Estimate remaining years with:

```bash
python .cursor/skills/drought-ensemble/scripts/years_to_run.py run_sequences/<ensemble>/<seq>.json <domain>
```

### 6. Resubmit

From `ensemble_running/`:

```bash
python run_ensemble.py <ensemble_name> <domain> [<domain> ...]
# optional: --walltime HH:MM:SS  --dry-run
```

`run_ensemble.py` submits **every** `.json` in the ensemble folder. If only some members need restart, submit those with a one-off `tmp_job.pbs` (same template as `run_ensemble.py`) instead of the whole folder.

Prefer `--dry-run` when the set is ambiguous. Incomplete tips must already be deleted; complete years are skipped.

Derecho `cpu`/`main` walltime is typically **12 h max** — long droughts often need multiple restarts; plan remaining years accordingly.

### Optional: automated watchdog

For unattended tip-cleanup + resubmit (narrower than this skill), see
`ensemble_running/watchdog/README.md` (NCAR cron → Casper → Derecho).

When reporting run status, also run
`python3 ensemble_running/watchdog/restart_watchdog.py --list-stuck` and mention any
`stuck_same_year` sequences (failed twice on the same tip year; not auto-resubmitted).

### 7. Report

Return PBS job IDs and domain/ensemble/sequence mapping. Note anything held for quota.

## Do not

- Delete complete prior-year or mid-sequence IC folders needed by later years
- Delete anything an **`R`** job is writing
- Resubmit the same domain+sequence while it is still **`R`**
- Assume freeing disk resumes a dead job
- Bypass the incomplete-year-cleanup rule when choosing delete targets
- Submit large new ensembles without a quota estimate
