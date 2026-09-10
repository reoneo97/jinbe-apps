import os
import re
import time
import secrets
from pathlib import Path
from collections import defaultdict, deque

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import RedirectResponse, PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import bcrypt

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- Configuration (single tenant: one username/password from env) ---
AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "admin")
AUTH_PASSWORD_HASH = os.environ.get("AUTH_PASSWORD_HASH", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "")
NOTES_DIR = Path(os.environ.get("NOTES_DIR", BASE_DIR / "data"))
SESSION_MAX_AGE = int(os.environ.get("SESSION_MAX_AGE_SECONDS", 60 * 60 * 24 * 14))  # 14 days

if not AUTH_PASSWORD_HASH:
    raise RuntimeError(
        "AUTH_PASSWORD_HASH is not set. Generate one with scripts/hash_password.py "
        "and set it (along with AUTH_USERNAME and SECRET_KEY) as an environment variable."
    )
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set. Set it to a long random string (e.g. `openssl rand -hex 32`)."
    )

NOTES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Markdown Notes")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=os.environ.get("SESSION_HTTPS_ONLY", "false").lower() == "true",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# --- Very small in-memory brute-force guard for the login form ---
_FAILED_ATTEMPTS: dict[str, deque] = defaultdict(deque)
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 15 * 60


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_locked_out(key: str) -> bool:
    now = time.time()
    attempts = _FAILED_ATTEMPTS[key]
    while attempts and now - attempts[0] > _WINDOW_SECONDS:
        attempts.popleft()
    return len(attempts) >= _MAX_ATTEMPTS


def _record_failure(key: str) -> None:
    _FAILED_ATTEMPTS[key].append(time.time())


def _clear_failures(key: str) -> None:
    _FAILED_ATTEMPTS.pop(key, None)


# --- Auth helpers ---
def require_login(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,119}$")


def sanitize_note_name(raw_name: str) -> str:
    name = (raw_name or "").strip()
    if name.lower().endswith(".md"):
        name = name[:-3]
    name = name.strip()
    if not name or not FILENAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail="Note names may only contain letters, numbers, spaces, hyphens and underscores.",
        )
    return f"{name}.md"


def note_path(name: str) -> Path:
    filename = sanitize_note_name(name)
    path = (NOTES_DIR / filename).resolve()
    if NOTES_DIR.resolve() not in path.parents and path != NOTES_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid note name.")
    return path


def list_notes() -> list[dict]:
    notes = []
    for path in NOTES_DIR.glob("*.md"):
        stat = path.stat()
        notes.append({"name": path.stem, "modified": stat.st_mtime, "size": stat.st_size})
    notes.sort(key=lambda n: n["modified"], reverse=True)
    return notes


# --- Routes: auth ---
@app.get("/login")
def login_form(request: Request):
    if request.session.get("user"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    key = _client_key(request)
    if _is_locked_out(key):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Too many failed attempts. Try again in a few minutes."},
            status_code=429,
        )

    valid_user = secrets.compare_digest(username.strip(), AUTH_USERNAME)
    valid_pass = bool(password) and bcrypt.checkpw(
        password.encode("utf-8"), AUTH_PASSWORD_HASH.encode("utf-8")
    )

    if not (valid_user and valid_pass):
        _record_failure(key)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password."},
            status_code=401,
        )

    _clear_failures(key)
    request.session.clear()
    request.session["user"] = AUTH_USERNAME
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# --- Routes: notes ---
@app.get("/")
def index(request: Request, user: str = Depends(require_login)):
    return templates.TemplateResponse(
        "index.html", {"request": request, "notes": list_notes(), "user": user}
    )


@app.post("/notes")
def create_note(request: Request, name: str = Form(...), user: str = Depends(require_login)):
    path = note_path(name)
    if not path.exists():
        path.write_text(f"# {path.stem}\n\n", encoding="utf-8")
    return RedirectResponse(f"/notes/{path.stem}/edit", status_code=303)


@app.get("/notes/{name}/edit")
def edit_note(request: Request, name: str, user: str = Depends(require_login)):
    path = note_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Note not found.")
    content = path.read_text(encoding="utf-8")
    return templates.TemplateResponse(
        "edit.html", {"request": request, "name": path.stem, "content": content}
    )


@app.put("/api/notes/{name}")
async def save_note(request: Request, name: str, user: str = Depends(require_login)):
    path = note_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Note not found.")
    body = await request.json()
    content = body.get("content", "")
    path.write_text(content, encoding="utf-8")
    return {"status": "ok", "saved_at": time.time()}


@app.post("/notes/{name}/delete")
def delete_note(request: Request, name: str, user: str = Depends(require_login)):
    path = note_path(name)
    if path.exists():
        path.unlink()
    return RedirectResponse("/", status_code=303)


@app.get("/notes/{name}/raw")
def raw_note(request: Request, name: str, user: str = Depends(require_login)):
    path = note_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Note not found.")
    return FileResponse(path, media_type="text/markdown", filename=path.name)


@app.get("/healthz")
def healthz():
    return PlainTextResponse("ok")
