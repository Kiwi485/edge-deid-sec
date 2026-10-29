#!/usr/bin/env bash
# W10-2 final round on the hardened configuration, run right after the image build:
#   1) W10-1 regression: pytest, five-image TFLite pipeline, SELinux checker, AVC window
#   2) CIS evidence collection inside the controlled runtime window
# Stops at the first failed step and exits non-zero, so a broken regression never produces
# CIS evidence that looks like it came from a working configuration.
# Usage: bash run_final_round.sh <project-dir> <build-log> <round-dir>
set -u
PROJ=${1:?project dir}
BUILD_LOG=${2:?build log}
R=${3:?round dir}
cd "$PROJ"
CIS=evidence/security/cis
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.selinux.yml)
export BATCH_LIMIT=5 INSTALL_TFLITE=1 SEG_BACKEND=tflite
mkdir -p "$R"

step() {
  local name=$1; shift
  "$@"
  local rc=$?
  echo "${name}_exit=$rc"
  if [ $rc -ne 0 ]; then
    echo "final round FAILED at $name; CIS checks not collected" >&2
    exit $rc
  fi
}

# Every service must exit 0; 'compose up' alone does not fail when a one-shot service fails.
services_ok() {
  local bad
  bad=$("${COMPOSE[@]}" ps -a --format '{{.Service}} {{.ExitCode}}' | awk '$2 != 0')
  [ -z "$bad" ] || { echo "non-zero service exit: $bad" >&2; return 1; }
}

date +%s > "$R/start_epoch"; date -Is > "$R/start_iso"
step pytest bash -c "~/.venvs/edge-deid-sec/bin/python -m pytest -q test/test_week10_security.py test/test_unix_socket_ipc.py > '$R/pytest.txt' 2>&1"
step config "${COMPOSE[@]}" config --quiet
date +%s > "$R/up_start_epoch"
step up bash -c "timeout 1500 $(printf '%q ' "${COMPOSE[@]}") up --no-build --force-recreate --abort-on-container-failure > '$R/up.log' 2>&1"
"${COMPOSE[@]}" ps -a > "$R/container-status.txt"
step services services_ok
date +%s > "$R/probe_start_epoch"
step checker bash -c "~/.venvs/edge-deid-sec/bin/python tools/check_week10_security.py --require-selinux --output '$R/week10-selinux.json' > '$R/checker.out' 2>&1"
date +%s > "$R/end_epoch"; date -Is > "$R/end_iso"
"${COMPOSE[@]}" logs --no-color > "$R/compose.log" 2>&1
sudo ausearch -m AVC,USER_AVC,SELINUX_ERR -ts today > "$R/avc_today.raw" 2>/dev/null

date -Is > "$R/cis_start_iso"
step window_up bash -c "bash '$CIS/scripts/runtime_window.sh' up '$PROJ' > '$R/window-up.log' 2>&1"
sudo BUILD_LOG="$BUILD_LOG" bash "$CIS/scripts/collect_checks.sh" "$PROJ/$CIS/checks/final" "$PROJ"
sudo chown -R "$(id -u):$(id -g)" "$CIS/checks"
step window_down bash -c "bash '$CIS/scripts/runtime_window.sh' down '$PROJ' > '$R/window-down.log' 2>&1"
date -Is > "$R/cis_end_iso"
echo "final round done"
