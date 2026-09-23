#!/bin/bash
# Thin NCAR-cron driver: lock, log, wake-decide, optional qsub Casper watchdog.
# Do not put heavy Python/I/O here — the cron host is memory-capped (~1 GB).
# --decide-submit is a light stdlib-only check (wake_state + qstat).
#
# Install on cron.hpc.ucar.edu, e.g. every 3 hours:
#   15 */3 * * * /glade/derecho/scratch/bwest/drought-ensemble/ensemble_running/watchdog/cron_driver.sh
#
# Verify without waiting for the next tick:
#   env -i /bin/bash .../cron_driver.sh --selftest
#
# See README.md for first-time setup.

set -euo pipefail

# cron provides only /usr/local/bin:/usr/bin:/bin — PBS lives outside that and
# no profile is sourced, so locate qsub explicitly rather than inheriting PATH.
export PATH="/opt/pbs/bin:/glade/u/apps/opt/qstat-cache/bin:${PATH:-/usr/local/bin:/usr/bin:/bin}"

ROOT="/glade/derecho/scratch/bwest/drought-ensemble"
WD="${ROOT}/ensemble_running/watchdog"
LOGDIR="${WD}/logs"
LOCK="${HOME:-/glade/u/home/bwest}/.drought_ensemble_restart_watchdog.lock"
PBS_SCRIPT="${WD}/watchdog.pbs"
LOG="${LOGDIR}/cron_driver.log"
STATUS="${LOGDIR}/last_status.txt"
ALERT_STAMP="${LOGDIR}/.last_alert_epoch"
MAILTO="benjaminwest@arizona.edu"
# Do not send more than one alert per this many seconds while still failing.
ALERT_INTERVAL=86400

# Cron host /usr/bin/python3 is 3.6 and cannot parse restart_watchdog.py
# (needs 3.7+ for `from __future__ import annotations` and dataclasses).
# Prefer a GLADE-mounted interpreter; --decide-submit is stdlib-only.
resolve_python3() {
  local cand
  for cand in \
    /glade/work/bwest/conda-envs/droughts/bin/python3 \
    /glade/u/apps/derecho/25.10/opt/view/bin/python3 \
    /glade/u/apps/opt/conda/bin/python3 \
    "$(command -v python3 2>/dev/null || true)"
  do
    [[ -n "${cand}" && -x "${cand}" ]] || continue
    if "${cand}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 7) else 1)' \
      2>/dev/null; then
      printf '%s\n' "${cand}"
      return 0
    fi
  done
  return 1
}

PYTHON3="$(resolve_python3 || true)"

SELFTEST=0
[[ "${1:-}" == "--selftest" ]] && SELFTEST=1

mkdir -p "${LOGDIR}"

log() {
  echo "[$(date -Is)] $*" >>"${LOG}"
}

write_status() {
  # result detail — read by restart_watchdog.py --heartbeat to detect silent breakage
  printf 'epoch=%s\nutc=%s\nresult=%s\ndetail=%s\n' \
    "$(date +%s)" "$(date -Is)" "$1" "$2" >"${STATUS}"
}

alert() {
  local subject="$1" body="$2" now last=0
  now=$(date +%s)
  [[ -f "${ALERT_STAMP}" ]] && last=$(cat "${ALERT_STAMP}" 2>/dev/null || echo 0)
  if (( now - last < ALERT_INTERVAL )); then
    log "alert suppressed (last sent $(( (now - last) / 3600 ))h ago): ${subject}"
    return 0
  fi
  if command -v mail >/dev/null 2>&1; then
    printf '%s\n\nHost: %s\nLog: %s\n' "${body}" "$(hostname)" "${LOG}" \
      | mail -s "${subject}" "${MAILTO}" 2>/dev/null \
      && echo "${now}" >"${ALERT_STAMP}" \
      && log "alert emailed: ${subject}"
  else
    log "alert NOT emailed (no mail command): ${subject}"
  fi
}

fail() {
  local detail="$1"
  log "FAILED: ${detail}"
  write_status fail "${detail}"
  alert "drought-ensemble watchdog cron FAILED" \
    "The restart watchdog could not be submitted.

Reason: ${detail}

Runs are NOT being auto-restarted until this is fixed."
  exit 1
}

# --------------------------------------------------------------------------
# Preflight — these are the things that silently broke before
# --------------------------------------------------------------------------
preflight() {
  local problems=()
  command -v qsub >/dev/null 2>&1 || problems+=("qsub not on PATH (${PATH})")
  if [[ -z "${PYTHON3}" ]]; then
    problems+=("no Python >=3.7 on GLADE (cron /usr/bin/python3 is too old)")
  fi
  [[ -r "${PBS_SCRIPT}" ]] || problems+=("cannot read ${PBS_SCRIPT}")
  [[ -r "${WD}/config.yaml" ]] || problems+=("cannot read ${WD}/config.yaml")
  [[ -r "${WD}/restart_watchdog.py" ]] || problems+=("cannot read ${WD}/restart_watchdog.py")
  [[ -d "${ROOT}/domains" ]] || problems+=("GLADE not mounted? missing ${ROOT}/domains")
  if (( ${#problems[@]} > 0 )); then
    printf '%s\n' "${problems[@]}"
    return 1
  fi
  return 0
}

if (( SELFTEST )); then
  echo "cron_driver selftest on $(hostname)"
  echo "PATH=${PATH}"
  echo "PYTHON3=${PYTHON3:-<none>}"
  if out=$(preflight); then
    echo "PASS: qsub=$(command -v qsub)"
    echo "PASS: python3=${PYTHON3} ($("${PYTHON3}" -c 'import sys; print(sys.version.split()[0])'))"
    echo "PASS: pbs script, config, and GLADE all readable"
  else
    echo "FAIL:"
    printf '  %s\n' ${out}
    exit 1
  fi
  if ! "${PYTHON3}" "${WD}/restart_watchdog.py" --help 2>&1 | grep -q decide-submit; then
    echo "FAIL: --decide-submit missing from restart_watchdog.py"
    exit 1
  fi
  echo "PASS: restart_watchdog.py --decide-submit available"
  echo "selftest OK — a real cycle would decide-submit then maybe qsub ${PBS_SCRIPT}"
  exit 0
fi

if ! problems=$(preflight); then
  fail "preflight: ${problems//$'\n'/; }"
fi

# --------------------------------------------------------------------------
# Single instance
# --------------------------------------------------------------------------
another_instance() {
  log "cannot acquire ${LOCK}; another instance running"
  exit 0
}

if command -v lockfile >/dev/null 2>&1; then
  lockfile -r 5 -l 3600 "${LOCK}" || another_instance
  trap 'rm -f "${LOCK}"' EXIT
else
  if ! mkdir "${LOCK}" 2>/dev/null; then
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

# --------------------------------------------------------------------------
# Decide whether a Casper scan is needed (wake_state + light qstat)
# --------------------------------------------------------------------------
# restart_watchdog.py --decide-submit is stdlib-only (no conda/PyYAML).
# Exit 0 = submit Casper, 10 = skip this cycle, other = error.
log "decide-submit"

set +e
decide_out=$("${PYTHON3}" "${WD}/restart_watchdog.py" --decide-submit 2>&1)
decide_rc=$?
set -e

# Collapse multiline qstat noise to one log line
decide_one_line=$(printf '%s' "${decide_out}" | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g')
log "decide-submit rc=${decide_rc} ${decide_one_line}"

if (( decide_rc == 10 )); then
  write_status ok "skipped ${decide_one_line}"
  exit 0
fi
if (( decide_rc != 0 )); then
  fail "decide-submit rc=${decide_rc}: ${decide_one_line}"
fi

# --------------------------------------------------------------------------
# Submit the Casper watchdog job
# --------------------------------------------------------------------------
log "submitting ${PBS_SCRIPT}"

if ! out=$(qsub -q casper@casper-pbs "${PBS_SCRIPT}" 2>&1); then
  fail "qsub: ${out}"
fi

log "submitted ${out}"
write_status ok "submitted ${out}"
rm -f "${ALERT_STAMP}"
