"""Local webcam demo backed by the existing image pipeline."""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web_demo"
RUNS_DIR = ROOT / "data" / "web-demo"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
RESULT_PATH = re.compile(r"/result/([0-9a-f]{32})/deid\.png")
BUSY = threading.Lock()


class DemoHandler(BaseHTTPRequestHandler):
    def _pi_mode(self):
        return self._mode() == "pi"

    def _mode(self):
        return getattr(self.server, "demo_mode", "pi" if getattr(self.server, "pi_mode", False) else "pc")

    @staticmethod
    def _privacy_pass(meta):
        return (
            isinstance(meta, dict)
            and meta.get("status") == "ok"
            and isinstance(meta.get("privacy_metrics"), dict)
            and meta["privacy_metrics"].get("privacy_pass") is True
        )

    def _local_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def _send(self, status, content, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' blob:; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)

    def _json(self, status, data):
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _success(self, run_id, meta):
        try:
            json.dumps(meta, allow_nan=False)
        except (TypeError, ValueError) as exc:
            print(f"Invalid metadata for {run_id}: {exc}", file=sys.stderr)
            self._json(500, {"error": "處理結果的 metadata 格式無效。"})
            return
        timing = meta.get("timing_ms")
        self._json(200, {
            "image_url": f"/result/{run_id}/deid.png",
            "roi_method": meta.get("roi_method_used", ""),
            "total_ms": timing.get("total_ms") if isinstance(timing, dict) else None,
            "feature_version": meta.get("feature_version", ""),
            "metadata": meta,
        })

    def do_GET(self):
        if not self._local_host():
            self._json(403, {"error": "Use the local 127.0.0.1 address."})
            return
        path = urlsplit(self.path).path
        if path == "/api/config":
            self._json(200, {"mode": self._mode()})
            return
        if path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            try:
                content = (WEB_DIR / filename).read_bytes()
            except OSError as exc:
                print(f"Cannot read web asset {filename}: {exc}", file=sys.stderr)
                self._json(500, {"error": "Cannot load the demo page. Check the server terminal."})
                return
            self._send(200, content, content_type)
            return

        match = RESULT_PATH.fullmatch(path)
        if match:
            if self._pi_mode():
                run_dir = ROOT / "data" / "camera-runs" / f"run-{match.group(1)}"
                output = run_dir / "out" / "tongue"
            else:
                run_dir = RUNS_DIR / match.group(1)
                output = run_dir / "out" / "capture"
            try:
                meta = json.loads((output / "meta.json").read_text(encoding="utf-8"))
                if not self._privacy_pass(meta):
                    self._json(404, {"error": "Result is unavailable."})
                    return
                if self._mode() in ("pi", "docker") and not self._docker_validated(run_dir, meta, "tongue" if self._pi_mode() else "capture"):
                    self._json(404, {"error": "Result is unavailable."})
                    return
                image = (output / "deid.png").read_bytes()
            except (OSError, ValueError):
                self._json(404, {"error": "Result is unavailable."})
                return
            self._send(200, image, "image/png")
            return
        self._json(404, {"error": "Not found."})

    def do_POST(self):
        if not self._local_host() or self.headers.get("Origin") != f"http://127.0.0.1:{self.server.server_port}":
            self._json(403, {"error": "Only this local demo page can submit images."})
            return
        if self.path != "/api/capture":
            self._json(404, {"error": "Not found."})
            return
        if self._pi_mode():
            if self.headers.get_content_type() != "application/json":
                self._json(415, {"error": "Expected JSON capture settings."})
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._json(400, {"error": "Missing or invalid settings length."})
                return
            if length <= 0 or length > 128:
                self._json(400, {"error": "Invalid capture settings length."})
                return
            try:
                settings = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"error": "Invalid capture settings."})
                return
            seconds = settings.get("countdown_seconds") if isinstance(settings, dict) else None
            if type(seconds) is not int or not 1 <= seconds <= 60:
                self._json(400, {"error": "倒數時間必須是 1 至 60 秒的整數。"})
                return
            if not BUSY.acquire(blocking=False):
                self._json(409, {"error": "The previous capture is still processing."})
                return
            try:
                self._process_pi(seconds)
            except OSError as exc:
                print(f"Cannot run Pi capture: {exc}", file=sys.stderr)
                self._json(500, {"error": "無法執行 Pi 相機流程，請檢查伺服器終端機。"})
            finally:
                BUSY.release()
            return
        if self.headers.get_content_type() != "image/jpeg":
            self._json(415, {"error": "Expected a JPEG image."})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._json(400, {"error": "Missing or invalid image length."})
            return
        if length <= 0 or length > MAX_IMAGE_BYTES:
            self._json(413, {"error": "Image size must be between 1 byte and 5 MB."})
            return
        if not BUSY.acquire(blocking=False):
            self._json(409, {"error": "The previous capture is still processing."})
            return
        try:
            image = self.rfile.read(length)
            if len(image) != length or not image.startswith(b"\xff\xd8"):
                self._json(400, {"error": "The JPEG image is incomplete or invalid."})
                return
            try:
                if self._mode() == "docker":
                    self._process_docker(image)
                else:
                    self._process(image)
            except OSError as exc:
                print(f"Cannot process capture: {exc}", file=sys.stderr)
                self._json(500, {"error": "Cannot save or process the image. Check the server terminal."})
        finally:
            BUSY.release()

    def _process(self, image):
        run_id = uuid.uuid4().hex
        run_dir = RUNS_DIR / run_id
        raw_dir = run_dir / "raw"
        out_dir = run_dir / "out"
        raw_dir.mkdir(parents=True, mode=0o700)
        (raw_dir / "capture.jpg").write_bytes(image)
        command = [
            sys.executable, "-m", "src.pipeline_local",
            "--raw-dir", str(raw_dir),
            "--out-dir", str(out_dir),
            "--csv", str(run_dir / "latency.csv"),
            "--seg-backend", "torch",
        ]
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        try:
            result = subprocess.run(
                command, cwd=ROOT, env=env, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=300,
            )
        except subprocess.TimeoutExpired:
            print(f"Pipeline timed out for {run_id}", file=sys.stderr)
            self._json(504, {"error": "Processing timed out. Check the server terminal."})
            return
        if result.returncode:
            print(result.stdout, result.stderr, file=sys.stderr)
            self._json(500, {"error": "Pipeline failed. Check the server terminal."})
            return
        try:
            meta = json.loads((out_dir / "capture" / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"Cannot read pipeline metadata for {run_id}: {exc}", file=sys.stderr)
            self._json(500, {"error": "Pipeline did not produce valid metadata."})
            return
        if not isinstance(meta, dict):
            self._json(500, {"error": "Pipeline did not produce valid metadata."})
            return
        if meta.get("status") != "ok":
            self._json(422, {"error": f"Image processing failed: {meta.get('error') or meta.get('status') or 'unknown status'}"})
            return
        if not self._privacy_pass(meta):
            self._json(422, {"error": "Privacy check did not pass; the result will not be displayed."})
            return
        if not (out_dir / "capture" / "deid.png").is_file():
            self._json(500, {"error": "De-identified image was not produced."})
            return
        self._success(run_id, meta)

    @staticmethod
    def _docker_validated(run_dir, meta, image_id):
        if not DemoHandler._privacy_pass(meta) or meta.get("seg_backend") != "tflite":
            return False
        with (run_dir / "evidence" / "batch" / "validation_summary.csv").open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        return len(rows) == 1 and rows[0].get("image_id") == image_id and rows[0].get("final_result") == "pass"

    def _process_docker(self, image):
        run_id = uuid.uuid4().hex
        run_dir = RUNS_DIR / run_id
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True, mode=0o700)
        (raw_dir / "capture.jpg").write_bytes(image)
        for directory in ("out", "logs", "evidence", "docs"):
            (run_dir / directory).mkdir()
        env = os.environ.copy()
        env.update(CAMERA_RUN_DIR=str(run_dir), BATCH_LIMIT="1", INSTALL_TFLITE="1", SEG_BACKEND="tflite")
        command = [
            "docker", "compose", "-p", "edge-web-demo",
            "-f", "docker-compose.yml", "-f", "docker-compose.camera.yml",
            "-f", "docker-compose.web.yml", "up", "--no-build", "--force-recreate",
        ]
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=600)
            if result.returncode:
                print(result.stdout, result.stderr, file=sys.stderr)
                self._json(500, {"error": "Docker 流程失敗，請檢查伺服器終端機和 Docker Desktop。"})
                return
            for service in ("acquisition", "extraction", "observability"):
                inspection = subprocess.run(
                    ["docker", "inspect", "--format", "{{.State.Status}} {{.State.ExitCode}}", f"edge-web-demo-{service}"],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                )
                if inspection.returncode or inspection.stdout.strip() != "exited 0":
                    print(f"Docker service {service} failed: {inspection.stdout} {inspection.stderr}", file=sys.stderr)
                    self._json(500, {"error": "Docker 服務未成功完成，請檢查伺服器終端機。"})
                    return
        except subprocess.TimeoutExpired:
            print(f"Docker pipeline timed out for {run_id}; containers may still be running.", file=sys.stderr)
            self._json(504, {"error": "Docker 流程逾時，請先檢查 Docker 容器狀態。"})
            return
        output = run_dir / "out" / "capture"
        try:
            meta = json.loads((output / "meta.json").read_text(encoding="utf-8"))
            valid = self._docker_validated(run_dir, meta, "capture")
        except (OSError, ValueError) as exc:
            print(f"Cannot read Docker results for {run_id}: {exc}", file=sys.stderr)
            self._json(500, {"error": "無法讀取 Docker 流程結果或驗證報告。"})
            return
        if not valid or not (output / "deid.png").is_file():
            self._json(422, {"error": "Docker 流程、隱私或輸出驗證未通過，結果不會顯示。"})
            return
        self._success(run_id, meta)

    def _process_pi(self, seconds):
        run_id = uuid.uuid4().hex
        try:
            result = subprocess.run(
                ["bash", str(ROOT / "camera-run.sh"), "--web", run_id, str(seconds)],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=600,
            )
        except subprocess.TimeoutExpired:
            print(f"Pi capture timed out for {run_id}", file=sys.stderr)
            self._json(504, {"error": "Pi 流程逾時，請檢查伺服器終端機及 Docker 狀態。"})
            return
        if result.returncode:
            print(result.stdout, result.stderr, file=sys.stderr)
            self._json(500, {"error": "Pi 相機或 Docker 流程失敗。請檢查伺服器終端機；sudo 授權可能已過期。"})
            return
        run_dir = ROOT / "data" / "camera-runs" / f"run-{run_id}"
        output = run_dir / "out" / "tongue"
        try:
            meta = json.loads((output / "meta.json").read_text(encoding="utf-8"))
            valid = self._docker_validated(run_dir, meta, "tongue")
        except (OSError, ValueError) as exc:
            print(f"Cannot read Pi results for {run_id}: {exc}", file=sys.stderr)
            self._json(500, {"error": "無法讀取 Pi 流程的結果或驗證報告。"})
            return
        if not valid or not (output / "deid.png").is_file():
            self._json(422, {"error": "Pi 流程、隱私或輸出驗證未通過，結果不會顯示。"})
            return
        self._success(run_id, meta)


def main():
    parser = argparse.ArgumentParser(description="Run the local webcam pipeline demo.")
    parser.add_argument("--port", type=int, default=8765)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--pi", action="store_true", help="Use the Pi camera and Docker pipeline.")
    modes.add_argument("--docker", action="store_true", help="Use the PC webcam and Docker pipeline.")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if (args.pi or args.docker) and not (ROOT / "models" / "seg" / "model.tflite").is_file():
        parser.error("models/seg/model.tflite is required for the Pi Docker pipeline")
    if not args.pi and not args.docker and not (ROOT / "models" / "seg" / "best.pth").is_file():
        parser.error("models/seg/best.pth is required for the local PyTorch pipeline")
    with ThreadingHTTPServer(("127.0.0.1", args.port), DemoHandler) as server:
        server.demo_mode = "pi" if args.pi else "docker" if args.docker else "pc"
        print(f"Open http://127.0.0.1:{args.port}/ (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nDemo stopped.", flush=True)


if __name__ == "__main__":
    main()
