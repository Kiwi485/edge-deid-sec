import http.client
import json
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from tools import web_camera_demo as demo


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "RUNS_DIR", tmp_path)
    instance = ThreadingHTTPServer(("127.0.0.1", 0), demo.DemoHandler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    thread.join()


def request(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    connection.request(method, path, body, headers or {})
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response.status, data


def test_capture_runs_real_pipeline_contract_and_serves_only_deidentified_image(server, tmp_path, monkeypatch):
    def fake_pipeline(command, **kwargs):
        assert command[1:3] == ["-m", "src.pipeline_local"]
        assert command[-2:] == ["--seg-backend", "torch"]
        raw = tmp_path / next(tmp_path.iterdir()).name / "raw" / "capture.jpg"
        assert raw.read_bytes() == b"\xff\xd8test"
        output = raw.parent.parent / "out" / "capture"
        output.mkdir(parents=True)
        (output / "meta.json").write_text(json.dumps({
            "status": "ok",
            "privacy_metrics": {"privacy_pass": True},
            "roi_method_used": "mediapipe",
            "timing_ms": {"total_ms": 1250},
            "feature_version": "v2_glcm",
        }), encoding="utf-8")
        (output / "deid.png").write_bytes(b"deidentified")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(demo.subprocess, "run", fake_pipeline)
    origin = f"http://127.0.0.1:{server.server_port}"
    status, body = request(server, "POST", "/api/capture", b"\xff\xd8test", {
        "Origin": origin, "Content-Type": "image/jpeg",
    })
    assert status == 200
    result = json.loads(body)
    assert result["roi_method"] == "mediapipe"
    assert result["total_ms"] == 1250
    assert result["metadata"]["privacy_metrics"]["privacy_pass"] is True
    assert result["metadata"]["timing_ms"] == {"total_ms": 1250}
    assert request(server, "GET", result["image_url"]) == (200, b"deidentified")
    assert request(server, "GET", "/result/../../raw/capture.jpg")[0] == 404


@pytest.mark.parametrize(
    ("status", "privacy"),
    [("quality_fail", True), ("ok", False)],
)
def test_capture_rejects_failed_quality_or_privacy(server, tmp_path, monkeypatch, status, privacy):
    def fake_pipeline(command, **kwargs):
        output = next(tmp_path.iterdir()) / "out" / "capture"
        output.mkdir(parents=True)
        (output / "meta.json").write_text(json.dumps({
            "status": status, "privacy_metrics": {"privacy_pass": privacy},
            "error": "blur" if status == "quality_fail" else "",
        }), encoding="utf-8")
        (output / "deid.png").write_bytes(b"not-safe")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(demo.subprocess, "run", fake_pipeline)
    origin = f"http://127.0.0.1:{server.server_port}"
    code, body = request(server, "POST", "/api/capture", b"\xff\xd8test", {
        "Origin": origin, "Content-Type": "image/jpeg",
    })
    assert code == 422
    assert "error" in json.loads(body)
    run_id = next(tmp_path.iterdir()).name
    assert request(server, "GET", f"/result/{run_id}/deid.png")[0] == 404


def test_rejects_cross_origin_bad_type_and_invalid_image(server, tmp_path):
    origin = f"http://127.0.0.1:{server.server_port}"
    assert request(server, "POST", "/api/capture", b"\xff\xd8test", {
        "Origin": "http://example.com", "Content-Type": "image/jpeg",
    })[0] == 403
    assert request(server, "POST", "/api/capture", b"data", {
        "Origin": origin, "Content-Type": "text/plain",
    })[0] == 415
    assert request(server, "POST", "/api/capture", b"not-jpeg", {
        "Origin": origin, "Content-Type": "image/jpeg",
    })[0] == 400
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("valid", [True, False])
@pytest.mark.parametrize("seconds", [1, 60])
def test_pi_capture_invokes_camera_script_and_requires_validation(server, tmp_path, monkeypatch, valid, seconds):
    server.pi_mode = True
    monkeypatch.setattr(demo, "ROOT", tmp_path)

    def fake_pipeline(command, **kwargs):
        assert command[0] == "bash"
        assert command[1] == str(tmp_path / "camera-run.sh")
        assert command[2] == "--web"
        assert command[4] == str(seconds)
        run_dir = tmp_path / "data" / "camera-runs" / f"run-{command[3]}"
        output = run_dir / "out" / "tongue"
        output.mkdir(parents=True)
        (output / "meta.json").write_text(json.dumps({
            "status": "ok", "seg_backend": "tflite",
            "privacy_metrics": {"privacy_pass": True},
            "timing_ms": {"total_ms": 2000},
        }), encoding="utf-8")
        (output / "deid.png").write_bytes(b"pi-result")
        report = run_dir / "evidence" / "batch"
        report.mkdir(parents=True)
        (report / "validation_summary.csv").write_text(
            f"image_id,final_result\ntongue,{'pass' if valid else 'fail'}\n", encoding="utf-8",
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(demo.subprocess, "run", fake_pipeline)
    origin = f"http://127.0.0.1:{server.server_port}"
    assert json.loads(request(server, "GET", "/api/config")[1]) == {"mode": "pi"}
    code, body = request(server, "POST", "/api/capture", json.dumps({"countdown_seconds": seconds}).encode(), {
        "Origin": origin, "Content-Type": "application/json",
    })
    assert code == (200 if valid else 422)
    run_id = next((tmp_path / "data" / "camera-runs").iterdir()).name[4:]
    result_path = f"/result/{run_id}/deid.png"
    assert request(server, "GET", result_path)[0] == (200 if valid else 404)
    if valid:
        assert json.loads(body)["image_url"] == result_path
        assert json.loads(body)["metadata"]["seg_backend"] == "tflite"
        assert request(server, "GET", result_path)[1] == b"pi-result"


def test_pi_rejects_uploads_and_camera_failures(server, monkeypatch):
    server.pi_mode = True
    origin = f"http://127.0.0.1:{server.server_port}"
    assert request(server, "POST", "/api/capture", b"image", {"Origin": origin})[0] == 415
    assert request(server, "POST", "/api/capture", b"", {"Origin": "http://example.com"})[0] == 403
    monkeypatch.setattr(demo.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1, stdout="", stderr="camera error",
    ))
    code, body = request(server, "POST", "/api/capture", b'{"countdown_seconds":5}', {
        "Origin": origin, "Content-Type": "application/json",
    })
    assert code == 500
    assert "error" in json.loads(body)


@pytest.mark.parametrize("seconds", [0, 61, True, 1.5, "5", None])
def test_pi_rejects_invalid_countdown(server, monkeypatch, seconds):
    server.pi_mode = True
    def should_not_run(*args, **kwargs):
        pytest.fail("invalid countdown must not start camera")
    monkeypatch.setattr(demo.subprocess, "run", should_not_run)
    origin = f"http://127.0.0.1:{server.server_port}"
    code, body = request(server, "POST", "/api/capture", json.dumps({"countdown_seconds": seconds}).encode(), {
        "Origin": origin, "Content-Type": "application/json",
    })
    assert code == 400
    assert "error" in json.loads(body)


@pytest.mark.parametrize("validation_pass", [True, False])
def test_computer_webcam_uses_docker_and_validates_output(server, tmp_path, monkeypatch, validation_pass):
    server.demo_mode = "docker"
    commands = []

    def fake_docker(command, **kwargs):
        commands.append(command)
        if command[1] == "compose":
            assert command[-3:] == ["up", "--no-build", "--force-recreate"]
            env = kwargs["env"]
            assert env["SEG_BACKEND"] == "tflite" and env["BATCH_LIMIT"] == "1"
            run = tmp_path / next(tmp_path.iterdir()).name
            assert (run / "raw" / "capture.jpg").read_bytes() == b"\xff\xd8test"
            output = run / "out" / "capture"
            output.mkdir()
            (output / "meta.json").write_text(json.dumps({
                "status": "ok", "seg_backend": "tflite",
                "privacy_metrics": {"privacy_pass": True},
            }), encoding="utf-8")
            (output / "deid.png").write_bytes(b"docker-result")
            report = run / "evidence" / "batch"
            report.mkdir()
            (report / "validation_summary.csv").write_text(
                f"image_id,final_result\ncapture,{'pass' if validation_pass else 'fail'}\n", encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="exited 0\n", stderr="")

    monkeypatch.setattr(demo.subprocess, "run", fake_docker)
    origin = f"http://127.0.0.1:{server.server_port}"
    assert json.loads(request(server, "GET", "/api/config")[1]) == {"mode": "docker"}
    code, body = request(server, "POST", "/api/capture", b"\xff\xd8test", {
        "Origin": origin, "Content-Type": "image/jpeg",
    })
    assert code == (200 if validation_pass else 422)
    assert len(commands) == 4
    run_id = next(tmp_path.iterdir()).name
    result_path = f"/result/{run_id}/deid.png"
    assert request(server, "GET", result_path)[0] == (200 if validation_pass else 404)
    if validation_pass:
        assert json.loads(body)["image_url"] == result_path
        assert json.loads(body)["metadata"]["seg_backend"] == "tflite"


def test_invalid_metadata_is_not_returned_as_invalid_json(server, tmp_path, monkeypatch):
    def fake_pipeline(command, **kwargs):
        output = next(tmp_path.iterdir()) / "out" / "capture"
        output.mkdir(parents=True)
        (output / "meta.json").write_text(json.dumps({
            "status": "ok", "privacy_metrics": {"privacy_pass": True},
            "timing_ms": {"total_ms": float("nan")},
        }), encoding="utf-8")
        (output / "deid.png").write_bytes(b"image")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(demo.subprocess, "run", fake_pipeline)
    origin = f"http://127.0.0.1:{server.server_port}"
    code, body = request(server, "POST", "/api/capture", b"\xff\xd8test", {
        "Origin": origin, "Content-Type": "image/jpeg",
    })
    assert code == 500
    assert "metadata" in json.loads(body)["error"]


def test_computer_docker_service_failure_is_not_reported_as_success(server, monkeypatch):
    server.demo_mode = "docker"
    def fake_docker(command, **kwargs):
        if command[1] == "compose":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="exited 1\n", stderr="")
    monkeypatch.setattr(demo.subprocess, "run", fake_docker)
    origin = f"http://127.0.0.1:{server.server_port}"
    code, body = request(server, "POST", "/api/capture", b"\xff\xd8test", {
        "Origin": origin, "Content-Type": "image/jpeg",
    })
    assert code == 500
    assert "error" in json.loads(body)
