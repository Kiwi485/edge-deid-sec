"""Collect W10 configuration/runtime evidence without claiming CIS compliance."""

import argparse
import json
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
import errno, json, os, socket, tempfile
from pathlib import Path
checks = {"non_root": os.getuid() != 0}
status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
checks["capabilities_dropped"] = int(status["CapEff"].strip(), 16) == 0
checks["no_new_privileges"] = status["NoNewPrivs"].strip() == "1"
mounts = [line.split() for line in Path("/proc/mounts").read_text().splitlines()]
checks["read_only_root"] = any(row[1] == "/" and "ro" in row[3].split(",") for row in mounts)
checks["temporary_input_in_tmpfs"] = any(row[1] == "/tmp" and row[2] == "tmpfs" for row in mounts)
checks["raw_directory_absent"] = not os.path.lexists("/app/data/raw")
for name, directory in (("output_writable", "/app/data/out"), ("logs_writable", "/app/logs")):
    try:
        with tempfile.TemporaryFile(dir=directory):
            pass
        checks[name] = True
    except OSError:
        checks[name] = False
with tempfile.TemporaryDirectory() as directory:
    with socket.socket(socket.AF_UNIX) as unix_socket:
        unix_socket.bind(str(Path(directory) / "probe.sock"))
        checks["unix_socket_available"] = True
try:
    with socket.socket(socket.AF_INET) as connection:
        connection.settimeout(3)
        connection.connect(("1.1.1.1", 443))
        checks["external_network_blocked"] = False
except OSError as exc:
    checks["external_network_blocked"] = exc.errno in (errno.ENETUNREACH, errno.EACCES, errno.EPERM)
context_path = Path("/proc/self/attr/current")
context = context_path.read_text().strip().strip("\x00") if context_path.exists() else "unavailable"
print(json.dumps({"checks": checks, "uid": os.getuid(), "security_context": context}))
'''
SELINUX_PROBE = r'''
import errno, json, os, socket
checks = {}
for family, name in ((socket.AF_INET, "tcp_socket_denied"), (socket.AF_INET6, "tcp6_socket_denied")):
    try:
        with socket.socket(family, socket.SOCK_STREAM):
            checks[name] = False
    except OSError as exc:
        checks[name] = exc.errno in (errno.EACCES, errno.EPERM)
try:
    os.listdir("/security-raw")
    checks["mounted_raw_directory_denied"] = False
except OSError as exc:
    checks["mounted_raw_directory_denied"] = exc.errno in (errno.EACCES, errno.EPERM)
print(json.dumps({"checks": checks}))
'''


def configuration_checks(config):
    extraction = config["services"]["extraction"]
    volumes = extraction.get("volumes", [])
    options = extraction.get("security_opt", [])
    writable = {item["target"] for item in volumes if not item.get("read_only", False)}
    return {
        "network_none": extraction.get("network_mode") == "none",
        "non_root": extraction.get("user", "0").split(":")[0] not in ("0", "root", ""),
        "read_only_root": extraction.get("read_only") is True,
        "capabilities_dropped": "ALL" in extraction.get("cap_drop", []),
        "no_new_privileges": any(option in ("no-new-privileges:true", "no-new-privileges") for option in options),
        "pid_limit": 0 < extraction.get("pids_limit", 0) <= 256,
        "raw_not_mounted": all(
            item["target"] not in ("/", "/app", "/app/data", "/app/data/raw")
            and not item["target"].startswith("/app/data/raw/")
            and not (item.get("type") == "bind" and Path(item["source"]).resolve() in (ROOT, ROOT / "data", ROOT / "data/raw"))
            for item in volumes
        ),
        "no_docker_socket": all("docker.sock" not in item["target"] and "docker.sock" not in item.get("source", "") for item in volumes),
        "models_read_only": any(item["target"] == "/app/models" and item.get("read_only") for item in volumes),
        "writable_mounts_limited": writable == {"/app/data/out", "/app/logs", "/run/edge-deid"},
        "tmpfs_configured": any(item.split(":")[0] == "/tmp" for item in extraction.get("tmpfs", [])),
    }


def run(command):
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180, check=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--require-selinux", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/security/week10.json")
    args = parser.parse_args()
    compose = ["docker", "compose", "-f", str(ROOT / "docker-compose.yml")]
    if args.require_selinux:
        compose += ["-f", str(ROOT / "docker-compose.selinux.yml")]
    evidence = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "static-only" if args.static_only else "configuration-and-runtime",
        "cis_full_audit": "not_run",
        "selinux_verified": False,
    }
    try:
        config = json.loads(run(compose + ["config", "--format", "json"]))
        evidence["configuration"] = configuration_checks(config)
        evidence["host_selinux"] = run(["getenforce"]) if shutil.which("getenforce") else "unavailable"
        evidence["docker_security_options"] = json.loads(run(["docker", "info", "--format", "{{json .SecurityOptions}}"] ))
        if not args.static_only:
            try:
                with socket.create_connection(("1.1.1.1", 443), timeout=3):
                    evidence["host_network_control"] = "connected"
            except OSError:
                evidence["host_network_control"] = "unavailable"
            evidence["runtime"] = json.loads(run(compose + ["run", "--rm", "--no-deps", "--no-build", "--entrypoint", "python", "extraction", "-c", PROBE]))
        if args.require_selinux and not args.static_only:
            evidence["raw_label"] = run(["ls", "-Zd", str(ROOT / "data/raw")])
            evidence["selinux_denials"] = json.loads(run(compose + [
                "run", "--rm", "--no-deps", "--no-build", "-v", f"{ROOT / 'data/raw'}:/security-raw:ro",
                "--entrypoint", "python", "extraction", "-c", SELINUX_PROBE,
            ]))
            evidence["selinux_verified"] = (
                evidence["host_selinux"] == "Enforcing"
                and "edge_deid_extraction_t" in evidence["runtime"]["security_context"]
                and "edge_deid_raw_t" in evidence["raw_label"]
                and all(evidence["selinux_denials"]["checks"].values())
            )
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
        evidence["error"] = str(exc)
    passed = "error" not in evidence and all(evidence.get("configuration", {}).values())
    if not args.static_only:
        passed = passed and bool(evidence.get("runtime")) and all(evidence.get("runtime", {}).get("checks", {}).values())
        passed = passed and evidence.get("host_network_control") == "connected"
    if args.require_selinux:
        passed = passed and evidence["selinux_verified"]
    evidence["checks_passed"] = bool(passed)
    evidence["week10_complete"] = bool(passed and evidence["selinux_verified"] and evidence["cis_full_audit"] == "passed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())