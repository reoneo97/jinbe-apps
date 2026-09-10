import { Marked } from "marked";
import { markedHighlight } from "marked-highlight";
import markedKatex from "marked-katex-extension";
import hljs from "highlight.js/lib/common";

const marked = new Marked();

marked.use(
    markedHighlight({
        emptyLangClass: "hljs",
        langPrefix: "hljs language-",
        highlight(code, lang) {
            const language = hljs.getLanguage(lang) ? lang : "plaintext";
            return hljs.highlight(code, { language }).value;
        },
    })
);

// throwOnError: false so a typo in a formula renders as an inline error
// instead of blanking out the whole preview pane.
marked.use(markedKatex({ throwOnError: false }));

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// Notes reference pasted images with a path relative to the notes
// directory (e.g. "assets/xyz.png") so the raw .md file stays portable
// (openable in Typora or any other editor pointed at the same folder).
// In the browser we rewrite that relative path to the app's protected
// file-serving route; absolute and remote URLs pass through untouched.
marked.use({
    renderer: {
        image(href, title, text) {
            let src = href || "";
            if (!/^([a-z][a-z0-9+.-]*:)?\/\//i.test(src) && !src.startsWith("/")) {
                const base = window.MD_FILES_BASE || "/files/";
                src = base + src.replace(/^\.\//, "");
            }
            const titleAttr = title ? ` title="${escapeHtml(title)}"` : "";
            return `<img src="${escapeHtml(src)}" alt="${escapeHtml(text || "")}"${titleAttr}>`;
        },
    },
});

window.MDRender = {
    render(markdownText) {
        return marked.parse(markdownText || "");
    },
};
