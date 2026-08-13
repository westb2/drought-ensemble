#!/bin/bash
# Thin NCAR-cron driver: lock, log, qsub Casper watchdog. Do not put heavy
# Python/I/O here — the cron host is memory-capped (~1 GB).
#
# Install on cron.hpc.ucar.edu, e.g. every 3 hours:
#   15 */3 * * * /glade/derecho/scratch/bwest/drought-ensemble/ensemble_running/watchdog/cron_driver.sh
#
# See README.md for first-time setup.

set -euo pipefail

ROOT="/glade/derecho/scratch/bwest/drought-ensemble"
WD="${ROOT}/ensemble_running/watchdog"
LOGDIR="${WD}/logs"
LOCK="${HOME}/.drought_ensemble_restart_watchdog.lock"
PBS_SCRIPT="${WD}/watchdog.pbs"

mkdir -p "${LOGDIR}"

remove_lock() {
  rm -f "${LOCK}"
}

another_instance() {
  echo "[$(date -Is)] cannot acquire ${LOCK}; another instance running" >>"${LOGDIR}/cron_driver.log"
  exit 0
}

# lockfile may be missing on cron; fall back to mkdir lock
if command -v lockfile >/dev/null 2>&1; then
  lockfile -r 5 -l 3600 "${LOCK}" || another_instance
  trap remove_lock EXIT
else
  if ! mkdir "${LOCK}" 2>/dev/null; then
    # stale lock older than 2 hours?
    if [[ -d "${LOCK}" ]]; then
      age=$(($(date +%s) - $(stat -c %Y "${LOCK}" 2>/dev/null || echo 0)))
      if (( age > 7200 )); then
        rmdir "${LOCK}" 2>/dev/null || true
        mkdir "${LOCK}" || another_instance
      else
        another_instance
      fi
    else
      another_instance
    fi
  fi
  trap 'rmdir "${LOCK}" 2>/dev/null || true' EXIT
fi

stamp="$(date -Is)"
echo "[${stamp}] submitting ${PBS_SCRIPT}" >>"${LOGDIR}/cron_driver.log"

# Casper via peer scheduling from cron host
if ! out=$(qsub -q casper@casper-pbs "${PBS_SCRIPT}" 2>&1); then
  echo "[${stamp}] qsub failed: ${out}" >>"${LOGDIR}/cron_driver.log"
  exit 1
fi

echo "[${stamp}] submitted ${out}" >>"${LOGDIR}/cron_driver.log"
