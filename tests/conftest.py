import os
import tempfile

import pytest

_data = tempfile.TemporaryDirectory(prefix="eco-tests-")
os.environ["ECO_NATIVE_DATA_DIR"] = _data.name
os.environ["ECO_NATIVE_ENV_PATH"] = _data.name + "/.env"


@pytest.fixture(autouse=True)
def isolated_state():
    from backend.app.db.store import store
    from backend.app.db.models import StudioState
    from backend.app.services.auth import AUTH_PATH
    from backend.app.core.paths import DATA_DIR
    store.replace(StudioState())
    AUTH_PATH.unlink(missing_ok=True)
    (DATA_DIR / ".maintenance").unlink(missing_ok=True)
    yield
    (DATA_DIR / ".maintenance").unlink(missing_ok=True)
