import os
import sys

import uvicorn

from backend.app.main import app


def main() -> None:
    # No app empacotado (PyInstaller) sys.executable e o proprio binario do backend,
    # que nao entende "-m modulo". Por isso a janela de login se reexecuta o binario
    # neste modo, em vez de subir mais um servidor uvicorn.
    if os.getenv("ECO_NATIVE_MODE") == "makerworld-login" or "--makerworld-login" in sys.argv:
        from backend.app.services.makerworld_login_window import main as login_main

        login_main()
        return

    host = os.getenv("ECO_NATIVE_HOST", "127.0.0.1")
    port = int(os.getenv("ECO_NATIVE_PORT", "8765"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
