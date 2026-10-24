import base64
import json
import shutil
import socket
import stat
import sys
import threading
import time
from pathlib import Path
from types import ModuleType

import pytest

from src.services.acquisition_service import build_socket_job
from src.services.extraction_service import _handle_job


def _wait_for_socket(sock_path):
    deadline = time.monotonic() + 2
    while True:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            try:
                client.connect(sock_path)
                return
            except (FileNotFoundError, ConnectionRefusedError):
                if time.monotonic() >= deadline:
                    raise
        threading.Event().wait(0.01)


@pytest.mark.parametrize("pipeline_error", [False, True])
def test_socket_input_is_ephemeral_and_paths_are_server_owned(tmp_path, monkeypatch, pipeline_error):
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"test image content")
    job = build_socket_job(image_path)
    assert "raw_dir" not in job
    image_path.unlink()
    job.update(raw_dir="/forbidden/raw", out_dir="/forbidden/out", csv="/forbidden/log")
    out_dir = tmp_path / "out"
    csv_path = tmp_path / "latency.csv"
    observed = {}

    def fake_pipeline(**kwargs):
        observed.update(kwargs)
        assert (kwargs["raw_dir"] / "image.png").read_bytes() == b"test image content"
        assert kwargs["out_dir"] == out_dir
        assert kwargs["csv_path"] == csv_path
        if pipeline_error:
            raise RuntimeError("pipeline failed")
        meta_dir = out_dir / "image"
        meta_dir.mkdir(parents=True)
        (meta_dir / "meta.json").write_text(json.dumps({"status": "ok"}))

    pipeline = ModuleType("src.pipeline_local")
    pipeline.run_batch_pipeline = fake_pipeline
    monkeypatch.setitem(sys.modules, "src.pipeline_local", pipeline)
    response = _handle_job(job, out_dir=out_dir, csv_path=csv_path)
    assert response["status"] == ("error" if pipeline_error else "ok")
    assert not observed["raw_dir"].exists()


@pytest.mark.parametrize("filename", ["../image.png", "/tmp/image.png", "..", "image.txt"])
def test_reject_unsafe_input_names(filename):
    response = _handle_job({"input_file": filename, "image_b64": "eA=="})
    assert response["status"] == "error"
    assert response["error"] == "invalid input_file"


@pytest.mark.parametrize("encoded", [None, "!invalid!", "", base64.b64encode(b"").decode()])
def test_reject_missing_or_invalid_image(encoded):
    response = _handle_job({"input_file": "image.png", "image_b64": encoded})
    assert response["status"] == "error"


def test_reject_oversized_image(tmp_path, monkeypatch):
    from src.services import acquisition_service, extraction_service

    monkeypatch.setattr(acquisition_service, "MAX_IMAGE_BYTES", 2)
    monkeypatch.setattr(extraction_service, "MAX_IMAGE_BYTES", 2)
    image_path = tmp_path / "large.png"
    image_path.write_bytes(b"123")
    with pytest.raises(ValueError):
        build_socket_job(image_path)
    response = _handle_job({"input_file": "large.png", "image_b64": "MTIz"})
    assert response["status"] == "error"


def test_image_content_roundtrip_over_socket(tmp_path, monkeypatch):
    from src.services.ipc import send_job, serve_jobs

    image_bytes = b"image-content" * 20000
    image_path = tmp_path / "roundtrip.png"
    image_path.write_bytes(image_bytes)
    job = build_socket_job(image_path)
    image_path.unlink()
    out_dir = tmp_path / "out"
    observed = {}

    def fake_pipeline(**kwargs):
        observed.update(kwargs)
        assert (kwargs["raw_dir"] / "roundtrip.png").read_bytes() == image_bytes
        meta_dir = out_dir / "roundtrip"
        meta_dir.mkdir(parents=True)
        (meta_dir / "meta.json").write_text('{"status": "ok"}')

    pipeline = ModuleType("src.pipeline_local")
    pipeline.run_batch_pipeline = fake_pipeline
    monkeypatch.setitem(sys.modules, "src.pipeline_local", pipeline)
    sock_path = str(tmp_path / "image.sock")

    def handle(job):
        return _handle_job(job, out_dir=out_dir, csv_path=tmp_path / "latency.csv")

    server = threading.Thread(target=serve_jobs, args=(sock_path, handle), daemon=True)
    server.start()
    _wait_for_socket(sock_path)
    response = send_job(sock_path, job)
    server.join(timeout=2)
    assert not server.is_alive()
    assert response["status"] == "ok"
    assert response["processed"]
    assert not observed["raw_dir"].exists()


def test_ipc_rejects_non_object_and_limits_request_size(tmp_path, monkeypatch):
    from src.services import ipc

    sock_path = str(tmp_path / "bounded.sock")
    called = []
    monkeypatch.setattr(ipc, "MAX_REQUEST_BYTES", 64)
    server = threading.Thread(target=ipc.serve_jobs, args=(sock_path, called.append), daemon=True)
    server.start()
    _wait_for_socket(sock_path)
    assert stat.S_IMODE(Path(sock_path).stat().st_mode) == 0o660
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(sock_path)
        client.sendall(b"[]")
        client.shutdown(socket.SHUT_WR)
        response = json.loads(client.recv(4096))
    server.join(timeout=2)
    assert not server.is_alive()
    assert response["status"] == "error"
    assert not called
    with pytest.raises(ValueError, match="size limit"):
        ipc.send_job(sock_path, {"image_b64": "x" * 65})


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker Compose is needed for configuration checks")
def test_compose_security_configuration():
    import subprocess
    from tools.check_week10_security import ROOT, configuration_checks

    result = subprocess.run(["docker", "compose", "config", "--format", "json"], cwd=ROOT, capture_output=True, text=True, check=True)
    config = json.loads(result.stdout)
    checks = configuration_checks(config)
    assert all(checks.values()), checks
    extraction = config["services"]["extraction"]
    assert "--clear-out" not in extraction["command"]
    output = next(volume for volume in config["services"]["observability"]["volumes"] if volume["target"] == "/app/data/out")
    assert not output.get("read_only", False)


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker Compose is needed for configuration checks")
def test_selinux_override_preserves_custom_raw_label():
    import subprocess
    from tools.check_week10_security import ROOT

    result = subprocess.run(["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.selinux.yml", "config", "--format", "json"], cwd=ROOT, capture_output=True, text=True, check=True)
    config = json.loads(result.stdout)
    assert "label=type:edge_deid_extraction_t" in config["services"]["extraction"]["security_opt"]
    assert "no-new-privileges:true" in config["services"]["extraction"]["security_opt"]
    for name in ("acquisition", "observability"):
        raw = next(volume for volume in config["services"][name]["volumes"] if volume["target"] == "/app/data/raw")
        assert raw["read_only"]
        assert not raw.get("bind", {}).get("selinux")


@pytest.mark.parametrize("require_selinux", [False, True])
@pytest.mark.parametrize("explicit_image", [False, True])
def test_runtime_probe_uses_existing_image(tmp_path, monkeypatch, require_selinux, explicit_image):
    from tools import check_week10_security as checker

    commands = []
    image = "custom-extraction:local" if explicit_image else "test-project-extraction"
    config = {"name": "test-project", "services": {"extraction": {"image": image} if explicit_image else {}}}

    def fake_run(command):
        commands.append(command)
        if "config" in command:
            return json.dumps(config)
        if command[:3] == ["docker", "image", "inspect"]:
            assert command[-1] == image
            return "[]"
        if "run" in command:
            assert commands.index(["docker", "image", "inspect", image]) < len(commands) - 1
            assert "--no-build" not in command
            assert "--build" not in command
            assert command[command.index("--pull") + 1] == "never"
            return json.dumps({"checks": {"probe": True}, "security_context": "edge_deid_extraction_t"})
        if command[0] == "getenforce":
            return "Enforcing"
        if command[0] == "ls":
            return "edge_deid_raw_t"
        return "[]"

    class Connected:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    output = tmp_path / "runtime.json"
    monkeypatch.setattr(sys, "argv", ["checker", "--output", str(output)] + (["--require-selinux"] if require_selinux else []))
    monkeypatch.setattr(checker, "run", fake_run)
    monkeypatch.setattr(checker, "configuration_checks", lambda config: {"configuration": True})
    monkeypatch.setattr(checker.shutil, "which", lambda name: name)
    monkeypatch.setattr(checker.socket, "create_connection", lambda *args, **kwargs: Connected())
    assert checker.main() == 0
    evidence = json.loads(output.read_text())
    assert evidence["checks_passed"]
    assert evidence["selinux_verified"] == require_selinux
    assert len([command for command in commands if "run" in command]) == (2 if require_selinux else 1)


def test_checker_preserves_subprocess_error_output(tmp_path, monkeypatch):
    import subprocess
    from tools import check_week10_security as checker

    def fail(command):
        raise subprocess.CalledProcessError(1, command, output="", stderr="Docker diagnostic")

    output = tmp_path / "failed.json"
    monkeypatch.setattr(sys, "argv", ["checker", "--output", str(output)])
    monkeypatch.setattr(checker, "run", fail)
    assert checker.main() == 1
    evidence = json.loads(output.read_text())
    assert not evidence["checks_passed"]
    assert evidence["command_stderr"] == "Docker diagnostic"