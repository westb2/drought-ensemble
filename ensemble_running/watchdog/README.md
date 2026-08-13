# Restart watchdog (NCAR cron → Casper → Derecho)

Thin trigger on `cron.hpc.ucar.edu`, heavy scan/cleanup/resubmit on Casper.
Default is **dry-run** until you set `WATCHDOG_APPLY=1` in `watchdog.pbs`.

## Layout

| File | Role |
|------|------|
| `cron_driver.sh` | Lock + `qsub` Casper job (cron-safe) |
| `watchdog.pbs` | Casper job: conda + `restart_watchdog.py` |
| `restart_watchdog.py` | Find tip incompletes, quota-gate, optional delete + `qsub` |
| `config.yaml` | Domains/ensembles to watch |

## One-time setup

1. Edit `config.yaml` `watch:` list to the ensembles/domains you want auto-restarted.
2. Dry-run once from a login node (or Casper interactive):

```bash
cd /glade/derecho/scratch/bwest/drought-ensemble/ensemble_running/watchdog
module load conda && conda activate droughts
python3 restart_watchdog.py --config config.yaml
```

3. When the report looks right, test apply manually:

```bash
python3 restart_watchdog.py --config config.yaml --apply
# or deletes only / submits only:
python3 restart_watchdog.py --config config.yaml --apply --no-submit
python3 restart_watchdog.py --config config.yaml --apply --no-delete
```

4. Submit the Casper wrapper once:

```bash
qsub watchdog.pbs
# after trusting logs, edit watchdog.pbs: WATCHDOG_APPLY=1
```

5. On `cron.hpc.ucar.edu`:

```bash
ssh bwest@cron.hpc.ucar.edu
chmod +x /glade/derecho/scratch/bwest/drought-ensemble/ensemble_running/watchdog/cron_driver.sh
crontab -e
# every 3 hours at :15
15 */3 * * * /glade/derecho/scratch/bwest/drought-ensemble/ensemble_running/watchdog/cron_driver.sh
```

Logs: `ensemble_running/watchdog/logs/`.

## Safety behavior

- Skips any domain/ensemble/sequence that already has a matching job in `R`/`Q`.
- Deletes **only tip incompletes** (folder exists, no `run.out.00001.nc` / `processed_output.nc`, no later year dirs for that sequence).
- Never auto-deletes mid-sequence incompletes (reports them as blocked).
- Refuses tip deletes on a domain while any job is **Running** there (shared hash risk).
- Skips submits if scratch free &lt; `quota.min_free_tib` (default 1.5 TiB).
- Caps submits per cycle (`safety.max_submits_per_cycle`).

### Tombstones (cascade wipe defense)

After each successful tip delete the watchdog writes under:

`domains/<domain>/raw_runs/.watchdog_tombstones/`

- `<hash>.json` — per-folder breadcrumb  
- `<domain>__<ensemble>__<sequence>.json` — history for that target  

Then it **refuses to delete an earlier year index** for that sequence (the multi-cycle peel that could empty a tree). A **later** year is still allowed (normal walltime progress). The same year is **not** auto-retried after one tip delete (`max_tip_deletes_per_year_index: 1`) — second failure on that year is treated as likely repeatable; tip is left for inspection. Distinct-year budget: `max_unique_tip_years_deleted_per_sequence` (default 10). Clear the sequence JSON to reset.

List held failures:

```bash
python3 restart_watchdog.py --list-stuck
```

This is intentionally narrower than the interactive `restart-ensemble-jobs` skill (no wrong-rate hash deletes, no interactive confirmation).

## Manual equivalents

Same PBS template as `run_ensemble.py`, but only for sequences that need work (not every JSON in the folder).
