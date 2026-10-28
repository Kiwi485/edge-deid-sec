#!/usr/bin/env bash
# Collect evidence for CIS Docker Benchmark v1.9.0 controls on this host.
# Usage: sudo bash collect_checks.sh <output-dir> <project-dir>
# Read-only: it only runs inspection commands (auditctl -l, stat, docker inspect, ...).
# Section 4/5 checks expect the controlled runtime window (runtime_window.sh up) to be running.
set -u
OUT=${1:?output dir}
PROJ=${2:?project dir}
mkdir -p "$OUT"
cd "$PROJ"

run() {
  local id=$1; shift
  local f="$OUT/$id.txt"
  {
    echo "# CIS Docker Benchmark v1.9.0 control $id"
    echo "# host: $(hostname)  collected: $(date -Is)"
    for cmd in "$@"; do
      echo
      echo "\$ $cmd"
      bash -c "$cmd" 2>&1
      echo "[exit=$?]"
    done
  } > "$f"
}

IMAGES="edge-deid-sec-acquisition:latest edge-deid-sec-extraction:latest edge-deid-sec-observability:latest"
INSPECT_ALL='docker ps --quiet --all | xargs -r docker inspect --format'

# Shared context
run _context "date -Is" "cat /etc/os-release" "uname -r" "getenforce" "docker version" "docker info" \
  "docker ps -a --format '{{.ID}} {{.Names}} {{.Image}} {{.Status}}'" "auditctl -l" "cat /etc/docker/daemon.json"

# 1 Host configuration
run 1.1.1 "grep '/var/lib/docker\s' /proc/mounts" "mountpoint -- \"\$(docker info -f '{{ .DockerRootDir }}')\"" "findmnt -T /var/lib/docker" "df -h /var/lib/docker"
run 1.1.2 "getent group docker"
run 1.1.3 "auditctl -l | grep /usr/bin/dockerd"
run 1.1.4 "auditctl -l | grep /run/containerd"
run 1.1.5 "docker info -f '{{ .DockerRootDir }}'" "auditctl -l | grep /var/lib/docker"
run 1.1.6 "auditctl -l | grep /etc/docker"
run 1.1.7 "systemctl show -p FragmentPath docker.service" "auditctl -l | grep docker.service"
run 1.1.8 "grep 'containerd.sock' /etc/containerd/config.toml" "ls -l /run/containerd/containerd.sock" "auditctl -l | grep containerd.sock"
run 1.1.9 "systemctl show -p FragmentPath docker.socket" "grep ListenStream /usr/lib/systemd/system/docker.socket" "ls -l /run/docker.sock" "auditctl -l | grep docker.sock"
run 1.1.10 "ls -l /etc/default/docker" "auditctl -l | grep /etc/default/docker"
run 1.1.11 "ls -l /etc/docker/daemon.json" "auditctl -l | grep /etc/docker/daemon.json"
run 1.1.12 "ls -l /etc/containerd/config.toml" "auditctl -l | grep /etc/containerd/config.toml"
run 1.1.13 "ls -l /etc/sysconfig/docker" "auditctl -l | grep /etc/sysconfig/docker"
run 1.1.14 "ls -l /usr/bin/containerd" "auditctl -l | grep -E '/usr/bin/containerd( |$)'"
run 1.1.15 "ls -l /usr/bin/containerd-shim" "auditctl -l | grep -E '/usr/bin/containerd-shim( |$)'"
run 1.1.16 "ls -l /usr/bin/containerd-shim-runc-v1" "auditctl -l | grep /usr/bin/containerd-shim-runc-v1"
run 1.1.17 "ls -l /usr/bin/containerd-shim-runc-v2" "auditctl -l | grep /usr/bin/containerd-shim-runc-v2"
run 1.1.18 "ls -l /usr/bin/runc" "auditctl -l | grep /usr/bin/runc"
run 1.2.1 "cat /etc/os-release" "getenforce" "systemctl is-active auditd firewalld" "firewall-cmd --state" \
  "rpm -q scap-security-guide openscap-scanner" "ss -ltnup"
run 1.2.2 "docker version --format 'client={{.Client.Version}} server={{.Server.Version}}'" "rpm -q docker-ce docker-ce-cli containerd.io" \
  "dnf -q check-update docker-ce docker-ce-cli containerd.io docker-compose-plugin; echo dnf_check_update_rc=\$?"

# 2 Docker daemon configuration
DAEMON_CMDS=("ps -ef | grep '[d]ockerd'" "cat /etc/docker/daemon.json")
run 2.1 "ps -fe | grep '[d]ockerd'"
run 2.2 "docker network ls --quiet | xargs docker network inspect --format '{{ .Name }}: {{ .Options }}'" "${DAEMON_CMDS[@]}"
run 2.3 "grep 'log-level' /etc/docker/daemon.json" "${DAEMON_CMDS[@]}"
run 2.4 "grep -- 'iptables' /etc/docker/daemon.json" "${DAEMON_CMDS[@]}"
run 2.5 "docker info --format 'Insecure Registries: {{ .RegistryConfig.InsecureRegistryCIDRs }} IndexConfigs: {{ range .RegistryConfig.IndexConfigs }}{{ .Name }} secure={{ .Secure }}; {{ end }}'"
run 2.6 "docker info --format 'Storage Driver: {{ .Driver }}'"
run 2.7 "docker info --format 'Storage Driver: {{ .Driver }}'"
run 2.8 "grep -E 'tls|hosts' /etc/docker/daemon.json" "${DAEMON_CMDS[@]}" "systemctl cat docker.service | grep -E '^ExecStart'" "ss -ltnp | grep -E ':2375|:2376'"
run 2.9 "grep -A4 'default-ulimits' /etc/docker/daemon.json" "${DAEMON_CMDS[@]}"
run 2.10 "docker info --format '{{ .SecurityOptions }}'" \
  "docker inspect --format='{{ .State.Pid }}' \$(docker ps -q) | while read -r line; do ps -h -p \"\$line\" -o pid,user; done" \
  "for i in $IMAGES; do echo \"\$i User=\$(docker image inspect --format '{{.Config.User}}' \$i)\"; done"
run 2.11 "grep -- 'cgroup-parent' /etc/docker/daemon.json" "${DAEMON_CMDS[@]}"
run 2.12 "grep -- 'dm.basesize' /etc/docker/daemon.json" "${DAEMON_CMDS[@]}"
run 2.13 "grep -- 'authorization-plugins' /etc/docker/daemon.json" "docker info --format 'Authorization plugins: {{ .Plugins.Authorization }}'" "${DAEMON_CMDS[@]}"
run 2.14 "docker info --format '{{ .LoggingDriver }}'" "grep -- 'log-driver' /etc/docker/daemon.json" "${DAEMON_CMDS[@]}"
run 2.15 "grep -- 'no-new-privileges' /etc/docker/daemon.json" "${DAEMON_CMDS[@]}"
run 2.16 "docker info --format '{{ .LiveRestoreEnabled }}'" "grep -- 'live-restore' /etc/docker/daemon.json"
run 2.17 "grep -- 'userland-proxy' /etc/docker/daemon.json" "${DAEMON_CMDS[@]}" "pgrep -a docker-proxy"
run 2.18 "docker info --format '{{ .SecurityOptions }}'"
run 2.19 "docker version --format '{{ .Server.Experimental }}'"

# 3 Docker daemon configuration files
run 3.1 "systemctl show -p FragmentPath docker.service" "stat -c '%U:%G %n' /usr/lib/systemd/system/docker.service" "stat -c %U:%G /usr/lib/systemd/system/docker.service | grep -v root:root"
run 3.2 "systemctl show -p FragmentPath docker.service" "stat -c '%a %n' /usr/lib/systemd/system/docker.service"
run 3.3 "systemctl show -p FragmentPath docker.socket" "stat -c '%U:%G %n' /usr/lib/systemd/system/docker.socket" "stat -c %U:%G /usr/lib/systemd/system/docker.socket | grep -v root:root"
run 3.4 "systemctl show -p FragmentPath docker.socket" "stat -c '%a %n' /usr/lib/systemd/system/docker.socket"
run 3.5 "stat -c '%U:%G %n' /etc/docker" "stat -c %U:%G /etc/docker | grep -v root:root"
run 3.6 "stat -c '%a %n' /etc/docker"
run 3.7 "ls -la /etc/docker/certs.d" "stat -c %U:%G /etc/docker/certs.d/* | grep -v root:root"
run 3.8 "ls -la /etc/docker/certs.d" "find /etc/docker/certs.d/ -type f -exec stat -c '%a %n' {} \\;"
for id in 3.9 3.10 3.11 3.12 3.13 3.14; do
  run $id "grep -E 'tls' /etc/docker/daemon.json" "${DAEMON_CMDS[@]}" "ss -ltnp | grep -E ':2375|:2376'"
done
run 3.15 "stat -c '%U:%G %n' /var/run/docker.sock" "stat -c %U:%G /var/run/docker.sock | grep -v root:docker"
run 3.16 "stat -c '%a %n' /var/run/docker.sock"
run 3.17 "stat -c '%U:%G %n' /etc/docker/daemon.json" "stat -c %U:%G /etc/docker/daemon.json | grep -v root:root"
run 3.18 "stat -c '%a %n' /etc/docker/daemon.json"
run 3.19 "stat -c %U:%G /etc/default/docker | grep -v root:root"
run 3.20 "stat -c %a /etc/default/docker"
run 3.21 "stat -c %a /etc/sysconfig/docker"
run 3.22 "stat -c %U:%G /etc/sysconfig/docker | grep -v root:root"
run 3.23 "stat -c '%U:%G %n' /run/containerd/containerd.sock" "stat -c %U:%G /run/containerd/containerd.sock | grep -v root:root"
run 3.24 "stat -c '%a %n' /run/containerd/containerd.sock"

# 4 Container images and build files
run 4.1 "docker ps --quiet | xargs --max-args=1 -I{} sh -c 'echo \"{} \$(docker inspect --format {{.Name}} {}) \$(docker exec {} cat /proc/1/status | grep ^Uid:)\"'" \
  "for i in $IMAGES; do echo \"\$i User=\$(docker image inspect --format '{{.Config.User}}' \$i)\"; done" "grep -n '^USER' Dockerfile"
run 4.2 "docker images" "grep -n '^FROM' Dockerfile" \
  "for i in $IMAGES; do echo \"== \$i\"; docker history \$i; done" \
  "docker image inspect --format '{{.RepoTags}} {{.RepoDigests}}' python:3.11-slim"
run 4.3 "for c in \$(docker ps -q); do echo \"== \$(docker inspect --format {{.Name}} \$c)\"; docker exec \$c dpkg-query -W -f='\${Package}\n' | wc -l; docker exec \$c python -m pip list --format=freeze; done" \
  "cat requirements.txt"
run 4.4 "which trivy && trivy --version" "grep -ohE 'python:3.11-slim@sha256:[0-9a-f]{64}' \${BUILD_LOG:-/dev/null} | sort -u" "docker buildx imagetools inspect python:3.11-slim --format '{{json .Manifest.Digest}}'" "for i in $IMAGES; do echo \"== \$i\"; docker image inspect --format 'Created={{.Created}}' \$i; done" \
  "docker image inspect --format 'base Created={{.Created}} {{.RepoDigests}}' python:3.11-slim"
run 4.5 "for i in $IMAGES; do echo \"\$i Healthcheck=\$(docker inspect --format='{{ .Config.Healthcheck }}' \$i)\"; done" "grep -n HEALTHCHECK Dockerfile"
run 4.6 "grep -n '^RUN' Dockerfile" "for i in $IMAGES; do echo \"== \$i\"; docker history --no-trunc --format '{{.CreatedBy}}' \$i | grep -i 'update'; done"
# 4.7: equivalent to 'docker export | tar -tv | grep s-bit' but runs find as root inside each container's
# mount namespace (-xdev skips bind mounts/tmpfs), avoiding an 11 GB export per container.
run 4.7 "for c in \$(docker ps -q); do p=\$(docker inspect --format {{.State.Pid}} \$c); echo \"== \$(docker inspect --format {{.Name}} \$c) files=\$(nsenter -t \$p -m find / -xdev -type f | wc -l)\"; nsenter -t \$p -m find / -xdev -perm /6000 -type f -exec ls -l {} +; echo setuid_setgid_count=\$(nsenter -t \$p -m find / -xdev -perm /6000 -type f | wc -l); done" \
  "p=\$(docker inspect --format {{.State.Pid}} edge-deid-extraction); nsenter -t \$p -m ls -l /usr/bin/su /usr/bin/passwd /usr/bin/mount"
run 4.8 "grep -nE '^(ADD|COPY)' Dockerfile" "for i in $IMAGES; do echo \"== \$i\"; docker history --no-trunc --format '{{.CreatedBy}}' \$i | grep -E '^ADD|ADD ' ; done"
run 4.9 "grep -niE 'password|passwd|secret|token|api[_-]?key|private' Dockerfile" \
  "for i in $IMAGES; do echo \"== \$i\"; docker history --no-trunc --format '{{.CreatedBy}}' \$i | grep -niE 'password|passwd|secret|token|api[_-]?key|private'; done" \
  "for i in $IMAGES; do echo \"== \$i\"; docker image inspect --format '{{range .Config.Env}}{{println .}}{{end}}' \$i; done"
run 4.10 "grep -nE 'apt-get|pip install' Dockerfile" \
  "docker exec edge-deid-extraction sh -c 'ls /etc/apt/trusted.gpg.d /usr/share/keyrings; grep -rh allow-insecure /etc/apt/ 2>/dev/null; echo apt_insecure_grep_rc=\$?'" \
  "grep -n -- '--hash' requirements.txt; echo pip_hash_grep_rc=\$?"
run 4.11 "env | grep -i DOCKER_CONTENT_TRUST; echo dct_env_rc=\$?" "docker trust inspect python:3.11-slim 2>&1 | head -20"

# 5 Container runtime configuration
run 5.1 "docker info --format '{{ .Swarm }}'"
run 5.2 "$INSPECT_ALL '{{ .Id }}: AppArmorProfile={{ .AppArmorProfile }}'" "docker info --format '{{ .SecurityOptions }}'" "ls /sys/kernel/security/apparmor 2>&1"
run 5.3 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: SecurityOpt={{ .HostConfig.SecurityOpt }} MountLabel={{ .MountLabel }} ProcessLabel={{ .ProcessLabel }}'"
run 5.4 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: CapAdd={{ .HostConfig.CapAdd }} CapDrop={{ .HostConfig.CapDrop }}'"
run 5.5 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: Privileged={{ .HostConfig.Privileged }}'"
run 5.6 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: Volumes={{ .Mounts }}'"
run 5.7 "for c in \$(docker ps -q); do echo \"== \$(docker inspect --format {{.Name}} \$c)\"; docker top \$c -eo pid,user,comm; done"
run 5.8 "docker ps --quiet | xargs -r docker inspect --format '{{ .Name }} {{ .Id }}: Ports={{ .NetworkSettings.Ports }}'"
run 5.9 "docker ps --quiet | xargs -r docker inspect --format '{{ .Name }} {{ .Id }}: Ports={{ .NetworkSettings.Ports }}'"
run 5.10 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: NetworkMode={{ .HostConfig.NetworkMode }}'"
run 5.11 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: Memory={{ .HostConfig.Memory }}'"
run 5.12 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: CpuShares={{ .HostConfig.CpuShares }}'"
run 5.13 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: ReadonlyRootfs={{ .HostConfig.ReadonlyRootfs }}'"
run 5.14 "docker ps --quiet | xargs -r docker inspect --format '{{ .Name }} {{ .Id }}: Ports={{ .NetworkSettings.Ports }}'"
run 5.15 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: RestartPolicyName={{ .HostConfig.RestartPolicy.Name }} MaximumRetryCount={{ .HostConfig.RestartPolicy.MaximumRetryCount }}'"
run 5.16 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: PidMode={{ .HostConfig.PidMode }}'"
run 5.17 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: IpcMode={{ .HostConfig.IpcMode }}'"
run 5.18 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: Devices={{ .HostConfig.Devices }}'"
run 5.19 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: Ulimits={{ .HostConfig.Ulimits }}'"
run 5.20 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: Propagation={{range \$mnt := .Mounts}} {{json \$mnt.Propagation}} {{end}}'"
run 5.21 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: UTSMode={{ .HostConfig.UTSMode }}'"
run 5.22 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: SecurityOpt={{ .HostConfig.SecurityOpt }}'" "docker info --format '{{ .SecurityOptions }}'"
run 5.23 "ausearch -k docker 2>&1 | grep exec | grep privileged; echo grep_rc=\$?" "auditctl -l | grep -E -- '-k docker'"
run 5.24 "ausearch -k docker 2>&1 | grep exec | grep user; echo grep_rc=\$?" "auditctl -l | grep -E -- '-k docker'"
run 5.25 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: CgroupParent={{ .HostConfig.CgroupParent }}'"
run 5.26 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: SecurityOpt={{ .HostConfig.SecurityOpt }}'" "grep no-new-privileges /etc/docker/daemon.json"
run 5.27 "docker ps --quiet | xargs -r docker inspect | python3 -c 'import json,sys; [print(c[\"Name\"], c[\"Id\"][:12]+\":\", \"Health=\"+(c[\"State\"].get(\"Health\") or {}).get(\"Status\",\"<none>\")) for c in json.load(sys.stdin)]'"
run 5.28 "grep -n '^FROM' Dockerfile" "docker image inspect --format 'local {{.RepoDigests}} Created={{.Created}}' python:3.11-slim" \
  "grep -ohE 'python:3.11-slim@sha256:[0-9a-f]{64}' \${BUILD_LOG:-/dev/null} | sort -u" "docker buildx imagetools inspect python:3.11-slim --format '{{json .Manifest.Digest}}'"
run 5.29 "docker ps -q | xargs -r docker inspect --format '{{.Name}} {{.HostConfig.PidsLimit}}'" \
  "docker ps -q | xargs -r docker inspect --format '{{.Name}} {{.HostConfig.PidsLimit}}' | awk '\$2 == 0 || \$2 == -1'"
run 5.30 "docker network ls -q | xargs docker network inspect -f '{{ .Name }} {{\":\"}} {{index .Options \"com.docker.network.bridge.name\"}}'" \
  "docker ps -aq | xargs -r docker inspect -f '{{.Name }} {{ .Id }}: {{range \$n, \$_ := .NetworkSettings.Networks}}{{ \$n }} {{end}}'"
run 5.31 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: UsernsMode={{ .HostConfig.UsernsMode }}'"
run 5.32 "$INSPECT_ALL '{{ .Name }} {{ .Id }}: Volumes={{ .Mounts }}' | grep docker.sock; echo grep_rc=\$?"

# 6 Docker security operations
run 6.1 "docker images --quiet | xargs docker image inspect --format '{{ .Id }}: Tags={{ .RepoTags }}'" "docker images -a" \
  "docker ps -a --format '{{.Names}} {{.Image}}'" "docker system df"
run 6.2 "docker info --format '{{ .Containers }}'" "docker info --format '{{ .ContainersStopped }}'" "docker info --format '{{ .ContainersRunning }}'" "docker ps -a --format '{{.Names}} {{.Status}}'"

# 7 Docker Swarm configuration (applicability depends on swarm state)
for id in 7.1 7.2 7.3 7.4 7.5 7.6 7.7 7.8 7.9; do
  run $id "docker info --format 'Swarm LocalNodeState={{ .Swarm.LocalNodeState }} ControlAvailable={{ .Swarm.ControlAvailable }} Managers={{ .Swarm.Managers }}'" \
    "ss -lpn | grep -iE ':2377|:7946'; echo grep_rc=\$?" "docker network ls --filter driver=overlay --quiet | wc -l"
done

echo "collected $(ls "$OUT" | wc -l) files into $OUT"
