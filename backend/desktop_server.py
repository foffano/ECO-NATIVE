import os

import uvicorn

from backend.app.main import app


def main() -> None:
    host = os.getenv("ECO_NATIVE_HOST", "127.0.0.1")
    port = int(os.getenv("ECO_NATIVE_PORT", "8765"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
