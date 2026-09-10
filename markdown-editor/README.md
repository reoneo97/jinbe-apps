# Markdown Notes

A tiny self-hosted markdown note editor: a note list, a Typora-style
editor with Edit / Split / Preview modes, full GFM markdown (tables,
task lists, strikethrough), LaTeX math, syntax-highlighted code blocks,
paste-to-upload images, and single-tenant login. There's exactly one
account, configured via environment variables — no signup flow, no
user database.

Notes are stored as plain `.md` files on disk, so they're easy to back
up, sync, or edit with other tools (Typora included) if you ever want to.

## How it works

- **FastAPI** app (`main.py`) serves server-rendered pages (Jinja2)
  plus JSON endpoints for saving notes and uploading pasted images.
- **Auth**: a signed session cookie (`itsdangerous`/Starlette
  `SessionMiddleware`) set after checking the submitted username/password
  against `AUTH_USERNAME` / `AUTH_PASSWORD_HASH` (bcrypt). A small
  in-memory guard locks out an IP for 15 minutes after 5 failed logins.
  Every note and every uploaded image is served through an authenticated
  route — nothing is public.
- **Editor**: a `<textarea>` with three view modes — **Edit** (source
  only), **Split** (source + live preview, the default), and **Preview**
  (rendered only, full width, Typora-like typography) — toggled from the
  toolbar and remembered per browser. Autosaves ~800ms after you stop
  typing, or immediately on `Ctrl/Cmd+S`.
- **Markdown rendering**: [marked](https://marked.js.org/) with GFM
  (tables, task lists, strikethrough), [KaTeX](https://katex.org/) for
  `$inline$` and `$$block$$` LaTeX math, and
  [highlight.js](https://highlightjs.org/) for fenced code blocks. All
  three are bundled into one vendored script
  (`static/vendor/editor-bundle.js`) — no CDN calls at runtime, so the
  app works even on a server with no outbound internet. See
  `frontend/README.md` if you ever need to rebuild it.
- **Pasting images**: paste an image (e.g. a screenshot) directly into
  the editor. It uploads to `<NOTES_DIR>/assets/<random-id>.<ext>` and
  inserts `![](assets/<random-id>.<ext>)` at the cursor — a path
  relative to the note file, so it still resolves if you open the same
  folder in another markdown editor.
- **Storage**: every note is `<NOTES_DIR>/<name>.md`. Filenames are
  restricted to letters, numbers, spaces, `-` and `_` to prevent path
  traversal; the same protection applies to the route that serves
  images and note files back to the browser.

## Local setup (no Docker)

Requires Python 3.11+.

```bash
cd markdown-editor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Generate your password hash
python scripts/hash_password.py
# -> prints AUTH_PASSWORD_HASH=$2b$12$...

cp .env.example .env
# edit .env: paste the hash above, set AUTH_USERNAME,
# and set SECRET_KEY to a random string, e.g.:
python -c "import secrets; print(secrets.token_hex(32))"

uvicorn main:app --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000`. The app loads `.env` itself (via
`python-dotenv`), so you don't need to `source` it — that matters here
because bcrypt hashes contain `$`, which a shell will try to expand.

## Run with Docker (recommended for your local server)

```bash
cd markdown-editor
python3 -m venv .venv && source .venv/bin/activate && pip install bcrypt
python scripts/hash_password.py     # copy the AUTH_PASSWORD_HASH line
deactivate && rm -rf .venv

cp .env.example .env    # fill in AUTH_USERNAME, AUTH_PASSWORD_HASH, SECRET_KEY

docker compose up -d --build
```

The app is now on `http://<your-server-ip>:8000`, and notes persist in
`./data` on the host (bind-mounted into the container).

## Deploying to the cloud

The same image works on any VPS. Two common paths, depending on whether
you want a public domain or just remote access to your existing box.

### Option A — VPS + automatic HTTPS (Caddy)

Best if you're fine running this on a small cloud VM (DigitalOcean,
Hetzner, Linode, a spare EC2 instance, etc.) with a domain name pointed
at it.

1. **Provision a small VM** (1 vCPU / 1GB RAM is plenty) and install
   Docker + the Compose plugin:
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
2. **Point DNS** at the VM: create an `A` record, e.g.
   `notes.example.com -> <vm-public-ip>`.
3. **Open ports 80 and 443** in your cloud provider's firewall (Caddy
   needs 80 for the Let's Encrypt HTTP challenge, 443 to serve).
4. **Copy this project to the VM** (`git clone` or `scp`) and configure:
   ```bash
   cd markdown-editor
   cp .env.example .env   # fill in AUTH_USERNAME / AUTH_PASSWORD_HASH / SECRET_KEY
   ```
5. **Bring it up** with the cloud compose file, which adds a Caddy
   reverse proxy that gets a free TLS certificate automatically:
   ```bash
   DOMAIN=notes.example.com docker compose -f docker-compose.cloud.yml up -d --build
   ```
6. Visit `https://notes.example.com`. Caddy renews the certificate on
   its own — nothing else to manage.

To update later: `git pull && DOMAIN=notes.example.com docker compose -f docker-compose.cloud.yml up -d --build`.

### Option B — keep it on your local server, expose it via tunnel

If the app should keep running on your own hardware (no VPS, possibly
behind NAT/CGNAT) but you still want to reach it from the internet:

- **Cloudflare Tunnel** (free, works behind NAT, gives you HTTPS on a
  domain you control):
  ```bash
  # on the machine already running docker compose up (Option "local")
  docker run -d --name cloudflared --network host \
    cloudflare/cloudflared:latest tunnel --no-autoupdate run \
    --token <your-tunnel-token>
  ```
  Create the tunnel and token in the Cloudflare Zero Trust dashboard
  first, and map its public hostname to `http://localhost:8000`.
- **Tailscale Funnel** (simplest if you're comfortable installing
  Tailscale on the box): `tailscale funnel 8000` exposes it at an
  `*.ts.net` HTTPS URL, no separate reverse proxy needed.

Either way, keep `SESSION_HTTPS_ONLY=true` in `.env` once traffic
reaches the app over HTTPS, so the session cookie is marked `Secure`.

## Security notes

- This app assumes **one trusted user**. It intentionally has no
  registration, password reset, or multi-user support.
- Always change the example `SECRET_KEY` — anyone with it can forge
  session cookies.
- Put it behind HTTPS before exposing it to the internet (both
  deployment options above do this) and set `SESSION_HTTPS_ONLY=true`.
- Back up the `data/` directory (or wherever `NOTES_DIR` points) —
  it's the only copy of your notes and pasted images.
- The login endpoint locks out an IP after 5 failed attempts for 15
  minutes; this is in-memory and resets on restart, which is fine for
  a single-instance deployment.
- Pasted images are capped at 15MB and must be PNG, JPEG, GIF or WebP
  (checked by the browser-reported content type, not by decoding the
  file — fine for a trusted single-user tool, not a substitute for
  antivirus scanning if you ever open this up further).

## Project layout

```
markdown-editor/
├── main.py                    # FastAPI app: auth, routes, note + image storage
├── scripts/hash_password.py   # generates AUTH_PASSWORD_HASH
├── templates/                 # login / note list / editor pages
├── static/
│   ├── style.css               # Typora-like typography, mode toggle
│   ├── editor.js                # modes, autosave, paste-to-upload
│   └── vendor/                  # prebuilt: marked + KaTeX + highlight.js
├── frontend/                   # dev-time source for static/vendor/ (see its README)
├── data/                       # notes + data/assets/ pasted images (gitignored)
├── Dockerfile
├── docker-compose.yml         # local/LAN, plain HTTP on :8000
├── docker-compose.cloud.yml   # cloud, Caddy + automatic HTTPS
└── Caddyfile
```
