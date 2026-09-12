import os
import secrets
import shutil
import tempfile
from pathlib import Path

import bcrypt
import pytest
from starlette.testclient import TestClient

TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass123"

# main.py reads its configuration from the environment at import time, so
# these must be set before "import main" runs anywhere in the test session.
_TEMP_NOTES_DIR = Path(tempfile.mkdtemp(prefix="md-notes-test-"))
os.environ["AUTH_USERNAME"] = TEST_USERNAME
os.environ["AUTH_PASSWORD_HASH"] = bcrypt.hashpw(
    TEST_PASSWORD.encode("utf-8"), bcrypt.gensalt()
).decode("utf-8")
os.environ["SECRET_KEY"] = secrets.token_hex(32)
os.environ["NOTES_DIR"] = str(_TEMP_NOTES_DIR)
os.environ["SESSION_HTTPS_ONLY"] = "false"

import main as app_module  # noqa: E402  (must follow the env var setup above)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_temp_notes_dir():
    yield
    shutil.rmtree(_TEMP_NOTES_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def _isolate_state():
    """Give every test a clean notes dir and a clean login-lockout state."""
    for path in app_module.NOTES_DIR.glob("*.md"):
        path.unlink()
    for path in app_module.ASSETS_DIR.glob("*"):
        if path.is_file():
            path.unlink()
    app_module._FAILED_ATTEMPTS.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app_module.app)


@pytest.fixture
def logged_in_client():
    c = TestClient(app_module.app)
    response = c.post(
        "/login",
        data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return c
