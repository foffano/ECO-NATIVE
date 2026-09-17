"""Run inside the Linux image to verify headed Chromium and remote input."""
import os
import tempfile
import time
from urllib.parse import quote


def main():
    if not os.getenv("DISPLAY"):
        raise RuntimeError("DISPLAY ausente: execute este teste pelo entrypoint Xvfb")
    with tempfile.TemporaryDirectory(prefix="eco-browser-smoke-") as directory:
        os.environ["ECO_NATIVE_DATA_DIR"] = directory
        os.environ["ECO_NATIVE_MAKERWORLD_URL"] = "data:text/html," + quote(
            '<button onclick="document.title=\'clicked\'">Testar</button><input id="text">'
        )
        from backend.app.services.makerworld_session import RemoteBrowserSession
        session = RemoteBrowserSession("smoke")
        session.start()
        try:
            deadline = time.monotonic() + 30
            while not session.frame():
                if time.monotonic() >= deadline:
                    raise RuntimeError(session.status().message)
                time.sleep(0.1)
            original = session.frame()
            session.send({"type": "click", "x": 150, "y": 18})
            session.send({"type": "text", "text": "Linux com Xvfb"})
            deadline = time.monotonic() + 10
            while session.frame() == original:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Entrada remota não alterou o quadro")
                time.sleep(0.1)
            assert session.status().open
            print("OK: Chromium headed, screenshot e entrada remota no Xvfb.")
        finally:
            session.close()
            session._thread.join(timeout=10)
            if session._thread.is_alive():
                raise RuntimeError("Navegador não encerrou")


if __name__ == "__main__":
    main()
