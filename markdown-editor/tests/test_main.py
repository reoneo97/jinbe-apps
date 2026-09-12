import base64

import pytest
from fastapi import HTTPException

import main as app_module

# Kept in sync with tests/conftest.py, which sets these as the app's
# configured single-tenant credentials before importing main.
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass123"

# A valid, minimal 1x1 pixel PNG for upload tests.
ONE_PX_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


# --- Auth ---


def test_root_redirects_to_login_when_unauthenticated(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_rejects_wrong_password(client):
    response = client.post("/login", data={"username": TEST_USERNAME, "password": "wrong"})
    assert response.status_code == 401
    assert "Invalid username or password" in response.text


def test_login_accepts_correct_credentials(client):
    response = client.post(
        "/login",
        data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"

    home = client.get("/")
    assert home.status_code == 200
    assert "No notes yet" in home.text


def test_login_locks_out_after_five_failed_attempts(client):
    for _ in range(5):
        response = client.post("/login", data={"username": TEST_USERNAME, "password": "wrong"})
        assert response.status_code == 401

    locked = client.post("/login", data={"username": TEST_USERNAME, "password": "wrong"})
    assert locked.status_code == 429

    # Even the correct password is refused while locked out.
    still_locked = client.post(
        "/login", data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    assert still_locked.status_code == 429


def test_logout_clears_session(logged_in_client):
    assert logged_in_client.get("/").status_code == 200
    logged_in_client.get("/logout")
    response = logged_in_client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_protected_routes_require_login(client):
    for method, path in [
        ("get", "/"),
        ("post", "/notes"),
        ("get", "/notes/anything/edit"),
        ("put", "/api/notes/anything"),
        ("post", "/notes/anything/delete"),
        ("get", "/notes/anything/raw"),
        ("post", "/api/images"),
        ("get", "/files/assets/anything.png"),
    ]:
        response = getattr(client, method)(path, follow_redirects=False)
        assert response.status_code == 303, f"{method.upper()} {path} should require login"
        assert response.headers["location"] == "/login"


# --- Notes CRUD ---


def test_create_note_seeds_content_and_redirects_to_editor(logged_in_client):
    response = logged_in_client.post(
        "/notes", data={"name": "My First Note"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/notes/My%20First%20Note/edit"

    edit_page = logged_in_client.get("/notes/My First Note/edit")
    assert edit_page.status_code == 200
    assert "# My First Note" in edit_page.text


def test_create_note_rejects_path_traversal_name(logged_in_client):
    response = logged_in_client.post("/notes", data={"name": "../evil"})
    assert response.status_code == 400


def test_save_note_persists_content_to_disk(logged_in_client):
    logged_in_client.post("/notes", data={"name": "Save Test"})
    save_response = logged_in_client.put(
        "/api/notes/Save Test", json={"content": "# Save Test\n\nHello world."}
    )
    assert save_response.status_code == 200

    on_disk = (app_module.NOTES_DIR / "Save Test.md").read_text()
    assert on_disk == "# Save Test\n\nHello world."


def test_save_note_404s_for_missing_note(logged_in_client):
    response = logged_in_client.put("/api/notes/Does Not Exist", json={"content": "x"})
    assert response.status_code == 404


def test_note_list_shows_created_notes(logged_in_client):
    logged_in_client.post("/notes", data={"name": "Alpha"})
    logged_in_client.post("/notes", data={"name": "Beta"})

    home = logged_in_client.get("/")
    assert "Alpha" in home.text
    assert "Beta" in home.text


def test_delete_note_removes_file_and_listing(logged_in_client):
    logged_in_client.post("/notes", data={"name": "Temp Note"})
    assert (app_module.NOTES_DIR / "Temp Note.md").exists()

    response = logged_in_client.post("/notes/Temp Note/delete", follow_redirects=False)
    assert response.status_code == 303
    assert not (app_module.NOTES_DIR / "Temp Note.md").exists()

    home = logged_in_client.get("/")
    assert "Temp Note" not in home.text


def test_raw_download_returns_markdown_content_type(logged_in_client):
    logged_in_client.post("/notes", data={"name": "Raw Test"})
    response = logged_in_client.get("/notes/Raw Test/raw")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# Raw Test" in response.text


# --- Image upload + protected file serving ---


def test_image_upload_returns_relative_asset_path(logged_in_client):
    response = logged_in_client.post(
        "/api/images", files={"file": ("photo.png", ONE_PX_PNG, "image/png")}
    )
    assert response.status_code == 200
    path = response.json()["path"]
    assert path.startswith("assets/")
    assert path.endswith(".png")
    assert (app_module.NOTES_DIR / path).read_bytes() == ONE_PX_PNG


def test_image_upload_rejects_non_image_content_type(logged_in_client):
    response = logged_in_client.post(
        "/api/images", files={"file": ("notes.txt", b"just text", "text/plain")}
    )
    assert response.status_code == 400


def test_image_upload_rejects_oversized_file(logged_in_client, monkeypatch):
    monkeypatch.setattr(app_module, "MAX_IMAGE_BYTES", 10)
    response = logged_in_client.post(
        "/api/images", files={"file": ("photo.png", ONE_PX_PNG, "image/png")}
    )
    assert response.status_code == 413


def test_uploaded_image_is_served_only_to_authenticated_users(client, logged_in_client):
    upload = logged_in_client.post(
        "/api/images", files={"file": ("photo.png", ONE_PX_PNG, "image/png")}
    )
    path = upload.json()["path"]

    authed = logged_in_client.get(f"/files/{path}")
    assert authed.status_code == 200
    assert authed.headers["content-type"] == "image/png"
    assert authed.content == ONE_PX_PNG

    anonymous = client.get(f"/files/{path}", follow_redirects=False)
    assert anonymous.status_code == 303
    assert anonymous.headers["location"] == "/login"


def test_files_route_missing_file_is_404(logged_in_client):
    response = logged_in_client.get("/files/assets/does-not-exist.png")
    assert response.status_code == 404


# --- Path-traversal protection (unit-level: HTTP clients normalize ".." in
# URLs before sending, so this exercises the guard functions directly) ---


@pytest.mark.parametrize("bad_path", ["../main.py", "assets/../../main.py", "/etc/passwd"])
def test_resolve_within_notes_dir_blocks_traversal(bad_path):
    with pytest.raises(HTTPException) as exc_info:
        app_module.resolve_within_notes_dir(bad_path)
    assert exc_info.value.status_code == 400


def test_resolve_within_notes_dir_allows_paths_inside_notes_dir():
    resolved = app_module.resolve_within_notes_dir("assets/photo.png")
    assert resolved == (app_module.NOTES_DIR / "assets" / "photo.png").resolve()


@pytest.mark.parametrize("bad_name", ["../evil", "a/b", "", "   ", "a" * 200])
def test_sanitize_note_name_rejects_invalid_names(bad_name):
    with pytest.raises(HTTPException) as exc_info:
        app_module.sanitize_note_name(bad_name)
    assert exc_info.value.status_code == 400


def test_sanitize_note_name_accepts_valid_names():
    assert app_module.sanitize_note_name("My Note") == "My Note.md"
    assert app_module.sanitize_note_name("My Note.md") == "My Note.md"
