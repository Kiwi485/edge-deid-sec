#!/usr/bin/env bash
# Start/stop a controlled runtime window so CIS section 4/5 checks see running containers
# that use the project's real Compose security configuration.
#   extraction: real service command, waits on its Unix socket (no acquisition is started).
#   acquisition/observability: same Compose service config, entrypoint replaced by sleep.
# Usage: bash runtime_window.sh up|down <project-dir>
set -eu
ACTION=${1:?up|down}
PROJ=${2:?project dir}
cd "$PROJ"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.selinux.yml)
export BATCH_LIMIT=999 INSTALL_TFLITE=1 SEG_BACKEND=tflite

case "$ACTION" in
  up)
    "${COMPOSE[@]}" down --remove-orphans
    "${COMPOSE[@]}" up -d --no-build extraction
    for svc in acquisition observability; do
      "${COMPOSE[@]}" run -d --no-deps --pull never --name "cis-runtime-$svc" --entrypoint sleep "$svc" 7200
    done
    # compose run ignores the service restart policy, so also create (not start) the real service
    # containers; HostConfig checks over 'docker ps --all' then cover the deployed configuration too.
    "${COMPOSE[@]}" create --no-build --no-recreate acquisition observability
    for _ in $(seq 1 30); do
      [ "$(docker inspect --format '{{.State.Health.Status}}' edge-deid-extraction)" = healthy ] && break
      sleep 2
    done
    docker ps --format '{{.Names}} {{.Status}}'
    ;;
  down)
    docker rm -f cis-runtime-acquisition cis-runtime-observability 2>/dev/null || true
    "${COMPOSE[@]}" down --remove-orphans
    ;;
esac
