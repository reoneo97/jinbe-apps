# Frontend build (dev-time only)

This directory is **not** used by the running app — it's how the vendored,
self-contained rendering bundle in `../static/vendor/` was built. The Python
app only ever loads the committed output, so end users never need Node.

Bundles `marked` (markdown parsing), `marked-katex-extension` + `katex` (LaTeX
math), and `marked-highlight` + `highlight.js` (code block syntax
highlighting) into one script that exposes `window.MDRender.render(text)`.
Vendoring instead of using a CDN keeps the app fully self-contained — it
works even if the server hosting it has no outbound internet access.

To rebuild after changing `src/main.js` or bumping a dependency version:

```bash
cd frontend
npm install
npm run build
```

This regenerates `../static/vendor/editor-bundle.js` and refreshes the
KaTeX CSS/fonts under `../static/vendor/katex/`.
