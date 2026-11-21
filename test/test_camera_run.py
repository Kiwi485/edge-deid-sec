import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
BASH = str(GIT_BASH) if os.name == "nt" and GIT_BASH.exists() else shutil.which("bash")


def _stub(path, contents):
    path.write_text("#!/usr/bin/env bash\nset -eu\n" + contents, encoding="utf-8")
    path.chmod(0o755)


@pytest.mark.skipif(BASH is None, reason="Bash is required")
@pytest.mark.parametrize(("web_mode", "seconds"), [(False, 5), (True, 1), (True, 60)])
@pytest.mark.parametrize("tracing", [None, "console"])
@pytest.mark.parametrize(
    ("scenario", "success", "docker_started"),
    [
        ("ok", True, True),
        ("no_photo", False, False),
        ("quality_fail", False, True),
        ("privacy_fail", False, True),
        ("validation_fail", False, True),
        ("container_fail", False, True),
    ],
)
def test_camera_run_isolates_input_and_checks_results(tmp_path, scenario, success, docker_started, web_mode, seconds, tracing):
    shutil.copy(ROOT / "camera-run.sh", tmp_path / "camera-run.sh")
    model = tmp_path / "models" / "seg" / "model.tflite"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"model")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub(bin_dir / "sudo", """\
if [ "$1" = -n ]; then shift; fi
case "$1" in
    -v|chgrp) exit 0 ;;
    env)
        unset EDGE_DEID_TRACING
        exec "$@"
        ;;
    install)
        shift
        while [ "$#" -gt 0 ]; do
            case "$1" in
                -d) shift ;;
                -m|-o|-g) shift 2 ;;
                *) mkdir -p "$1"; shift ;;
            esac
        done
        ;;
    *) exec "$@" ;;
esac
""")
    _stub(bin_dir / "rpicam-still", """\
echo "$*" > "$CAMERA_LOG"
if [ "$SCENARIO" = no_photo ]; then exit 0; fi
for arg in "$@"; do output="$arg"; done
printf 'photo' > "$output"
""")
    _stub(bin_dir / "docker", """\
if [ "$1" = compose ]; then
    echo compose >> "$EVENT_LOG"
    echo "tracing=${EDGE_DEID_TRACING-unset}" >> "$EVENT_LOG"
    mkdir -p "$CAMERA_RUN_DIR/out/tongue" "$CAMERA_RUN_DIR/evidence/batch"
    status=ok
    privacy=true
    result=pass
    if [ "$SCENARIO" = quality_fail ]; then status=quality_fail; fi
    if [ "$SCENARIO" = privacy_fail ]; then privacy=false; fi
    if [ "$SCENARIO" = validation_fail ]; then result=fail; fi
    printf '{"status":"%s","seg_backend":"tflite","privacy_metrics":{"privacy_pass":%s}}' "$status" "$privacy" > "$CAMERA_RUN_DIR/out/tongue/meta.json"
    printf 'image_id,final_result\\ntongue,%s\\n' "$result" > "$CAMERA_RUN_DIR/evidence/batch/validation_summary.csv"
    printf 'image' > "$CAMERA_RUN_DIR/out/tongue/deid.png"
elif [ "$1" = inspect ]; then
    if [ "$SCENARIO" = container_fail ]; then echo "exited 1"; else echo "exited 0"; fi
else
    exit 1
fi
""")
    _stub(bin_dir / "xdg-open", 'echo opened >> "$EVENT_LOG"\n')

    env = os.environ.copy()
    env.pop("EDGE_DEID_TRACING", None)
    if tracing is not None:
        env["EDGE_DEID_TRACING"] = tracing
    env.update(
        PATH=str(bin_dir) + os.pathsep + env["PATH"],
        SCENARIO=scenario,
        EVENT_LOG=str(tmp_path / "events"),
        CAMERA_LOG=str(tmp_path / "camera_args"),
    )
    result = subprocess.run(
        [BASH, str(tmp_path / "camera-run.sh")] + (["--web", "a" * 32, str(seconds)] if web_mode else []),
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    events = (tmp_path / "events").read_text().splitlines() if (tmp_path / "events").exists() else []
    assert (result.returncode == 0) is success, result.stdout + result.stderr
    assert ("compose" in events) is docker_started
    if docker_started:
        assert f"tracing={tracing or 'off'}" in events
    assert ("opened" in events) is (success and not web_mode)
    assert f"-t {seconds * 1000}" in (tmp_path / "camera_args").read_text()
    runs = list((tmp_path / "data" / "camera-runs").iterdir())
    assert len(runs) == 1
    if web_mode:
        assert runs[0].name == "run-" + "a" * 32
    assert (runs[0] / "raw" / "tongue.jpg").exists() is (scenario != "no_photo")


@pytest.mark.skipif(BASH is None, reason="Bash is required")
@pytest.mark.parametrize("seconds", ["0", "61", "-1", "1.5", "bad"])
def test_camera_run_rejects_invalid_web_countdown(tmp_path, seconds):
    shutil.copy(ROOT / "camera-run.sh", tmp_path / "camera-run.sh")
    result = subprocess.run(
        [BASH, str(tmp_path / "camera-run.sh"), "--web", "a" * 32, seconds],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "Invalid arguments" in result.stderr
    assert not (tmp_path / "data").exists()


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker Compose is required")
def test_pi_camera_compose_preserves_security_and_isolates_mounts(tmp_path):
    env = os.environ.copy()
    env.update(
        CAMERA_RUN_DIR=str(tmp_path),
        INSTALL_TFLITE="1",
        SEG_BACKEND="tflite",
        BATCH_LIMIT="1",
    )
    result = subprocess.run(
        [
            "docker", "compose", "-f", "docker-compose.yml",
            "-f", "docker-compose.pi.yml", "-f", "docker-compose.camera.yml",
            "config", "--format", "json",
        ],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    services = json.loads(result.stdout)["services"]
    for service in services.values():
        assert service["build"]["args"]["PI_ARM64"] == "1"
        assert service["user"] == "10001:10001"
        assert service["read_only"]
    extraction = services["extraction"]
    assert extraction["build"]["args"]["INSTALL_TFLITE"] == "1"
    assert extraction["network_mode"] == "none"
    assert "/app/data/raw" not in {volume["target"] for volume in extraction["volumes"]}
    for service in services.values():
        for volume in service["volumes"]:
            if volume["target"] in {"/app/data/raw", "/app/data/out", "/app/logs", "/app/evidence", "/app/docs"}:
                assert Path(volume["source"]).is_relative_to(tmp_path)
