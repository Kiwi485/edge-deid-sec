#!/usr/bin/env bash
# W10-2 final round on the hardened configuration, run right after the image build:
#   1) W10-1 regression: pytest, five-image TFLite pipeline, SELinux checker, AVC window
#   2) CIS evidence collection inside the controlled runtime window
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

date +%s > "$R/start_epoch"; date -Is > "$R/start_iso"
~/.venvs/edge-deid-sec/bin/python -m pytest -q test/test_week10_security.py test/test_unix_socket_ipc.py > "$R/pytest.txt" 2>&1
echo "pytest_exit=$?"
"${COMPOSE[@]}" config --quiet && echo config_ok
date +%s > "$R/up_start_epoch"
timeout 1500 "${COMPOSE[@]}" up --no-build --force-recreate > "$R/up.log" 2>&1
echo "up_exit=$?"
date +%s > "$R/probe_start_epoch"
~/.venvs/edge-deid-sec/bin/python tools/check_week10_security.py --require-selinux --output "$R/week10-selinux.json" > "$R/checker.out" 2>&1
echo "checker_exit=$?"
date +%s > "$R/end_epoch"; date -Is > "$R/end_iso"
"${COMPOSE[@]}" logs --no-color > "$R/compose.log" 2>&1
"${COMPOSE[@]}" ps -a > "$R/container-status.txt"
sudo ausearch -m AVC,USER_AVC,SELINUX_ERR -ts today > "$R/avc_today.raw" 2>/dev/null

date -Is > "$R/cis_start_iso"
bash "$CIS/scripts/runtime_window.sh" up "$PROJ" > "$R/window-up.log" 2>&1
sudo BUILD_LOG="$BUILD_LOG" bash "$CIS/scripts/collect_checks.sh" "$PROJ/$CIS/checks/final" "$PROJ"
sudo chown -R "$(id -u):$(id -g)" "$CIS/checks"
bash "$CIS/scripts/runtime_window.sh" down "$PROJ" > "$R/window-down.log" 2>&1
date -Is > "$R/cis_end_iso"
echo "final round done"
