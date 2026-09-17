import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import pytest


@pytest.mark.skipif(os.name != "posix", reason="POSIX SIGTERM lifecycle")
def test_server_boots_without_browser_install_and_shuts_down(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "ECO_NATIVE_DATA_DIR": str(tmp_path), "ECO_NATIVE_ENV_PATH": str(tmp_path / ".env"),
           "ECO_NATIVE_HOST": "127.0.0.1", "ECO_NATIVE_PORT": str(port),
           "PLAYWRIGHT_BROWSERS_PATH": str(tmp_path / "no-browsers")}
    with (tmp_path / "server.log").open("w+") as log:
        process = subprocess.Popen([sys.executable, "-m", "backend.web_server"], env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 10
            while True:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                        assert json.load(response)["status"] == "ok"
                    break
                except (urllib.error.URLError, TimeoutError):
                    assert process.poll() is None, "server exited at startup"
                    assert time.monotonic() < deadline, "server startup timed out"
                    time.sleep(0.1)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/auth/status") as response:
                assert json.load(response)["setup_required"] is True
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise AssertionError("server did not shut down gracefully")
        # Uvicorn restores/re-raises SIGTERM after completing its lifespan.
        assert process.returncode in {0, -signal.SIGTERM}
        log.seek(0)
        assert "Application shutdown complete." in log.read()
