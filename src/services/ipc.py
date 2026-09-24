from __future__ import annotations

import json
import os
import socket
import time
from typing import Any, Callable

DEFAULT_SOCKET_PATH = "/tmp/edge_deid.sock"


def _supports_unix_socket() -> bool:
    return hasattr(socket, "AF_UNIX")


def send_job(sock_path: str = DEFAULT_SOCKET_PATH, job: dict[str, Any] | None = None) -> dict[str, Any]:
    if not _supports_unix_socket():
        raise RuntimeError("Unix domain sockets are unavailable on this platform. Run W4 inside Docker/Linux.")

    payload = job or {}
    start = time.perf_counter()

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(sock_path)
        client.sendall(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        client.shutdown(socket.SHUT_WR)

        chunks: list[bytes] = []
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)

    round_trip_ms = (time.perf_counter() - start) * 1000.0
    response = b"".join(chunks)
    data = json.loads(response.decode("utf-8") or "{}") if response else {}
    processing_ms = float(data.get("processing_ms", 0.0))
    data["round_trip_ms"] = round_trip_ms
    data["ipc_ms"] = max(0.0, round_trip_ms - processing_ms)
    return data


def serve_jobs(
    sock_path: str = DEFAULT_SOCKET_PATH,
    handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    *,
    max_requests: int = 1,
) -> None:
    if not _supports_unix_socket():
        raise RuntimeError("Unix domain sockets are unavailable on this platform. Run W4 inside Docker/Linux.")

    if handler is None:
        def _noop(job: dict[str, Any]) -> dict[str, Any]:
            return {"status": "ok", "job_id": job.get("job_id", "unknown")}

        handler = _noop

    if os.path.exists(sock_path):
        os.remove(sock_path)

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(sock_path)
            server.listen(5)
            request_count = 0

            while request_count < max_requests:
                conn, _ = server.accept()
                with conn:
                    chunks: list[bytes] = []
                    while True:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        chunks.append(chunk)

                    if not chunks:
                        continue

                    request_count += 1
                    try:
                        job = json.loads(b"".join(chunks).decode("utf-8"))
                    except json.JSONDecodeError as exc:
                        response = {"status": "error", "error": f"invalid_json: {exc}"}
                    else:
                        response = handler(job)

                    conn.sendall(json.dumps(response, separators=(",", ":")).encode("utf-8"))
    finally:
        if os.path.exists(sock_path):
            try:
                os.remove(sock_path)
            except OSError:
                pass
