import socket
import threading
import time

import pytest

from src.services.ipc import send_job, serve_jobs


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="Unix domain sockets are unavailable on this platform; W4 is validated in Docker/Linux.")
def test_send_and_serve_job_roundtrip(tmp_path):
    sock_path = tmp_path / "test.sock"
    received = {}

    def on_job(job):
        received.update(job)
        return {"status": "ok", "job_id": job["job_id"]}

    server = threading.Thread(target=serve_jobs, args=(str(sock_path), on_job), daemon=True)
    server.start()
    time.sleep(0.15)

    response = send_job(str(sock_path), {"job_id": "job-42", "input_file": "a.jpg"})

    assert response["status"] == "ok"
    assert response["job_id"] == "job-42"
    assert received["job_id"] == "job-42"
    assert received["input_file"] == "a.jpg"
