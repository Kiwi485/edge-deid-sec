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
    deadline = time.monotonic() + 2
    while not Path(sock_path).exists() and time.monotonic() < deadline:
        threading.Event().wait(0.01)
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
    deadline = time.monotonic() + 2
    while not Path(sock_path).exists() and time.monotonic() < deadline:
        threading.Event().wait(0.01)
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
    for name in ("acquisition", "observability"):
        raw = next(volume for volume in config["services"][name]["volumes"] if volume["target"] == "/app/data/raw")
        assert raw["read_only"]
        assert not raw.get("bind", {}).get("selinux")