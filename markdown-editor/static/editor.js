(function () {
    const container = document.getElementById("editor-container");
    const editor = document.getElementById("editor");
    const preview = document.getElementById("preview");
    const status = document.getElementById("save-status");
    const modeButtons = document.querySelectorAll(".mode-toggle button");
    const noteName = window.NOTE_NAME;

    let saveTimer = null;
    let dirty = false;

    // --- Rendering ---
    function renderPreview() {
        preview.innerHTML = window.MDRender.render(editor.value);
    }

    // --- View mode (edit / split / preview), remembered per browser ---
    function setMode(mode) {
        container.classList.remove("mode-edit", "mode-split", "mode-preview");
        container.classList.add(`mode-${mode}`);
        modeButtons.forEach((btn) => {
            const active = btn.dataset.mode === mode;
            btn.classList.toggle("active", active);
            btn.setAttribute("aria-selected", String(active));
        });
        try {
            localStorage.setItem("md-editor-mode", mode);
        } catch (err) {
            /* localStorage unavailable (private mode etc.) — not critical */
        }
        if (mode !== "edit") renderPreview();
        if (mode !== "preview") editor.focus();
    }

    modeButtons.forEach((btn) => {
        btn.addEventListener("click", () => setMode(btn.dataset.mode));
    });

    let initialMode = "split";
    try {
        initialMode = localStorage.getItem("md-editor-mode") || "split";
    } catch (err) {
        /* ignore */
    }
    setMode(initialMode);

    // --- Save ---
    async function save() {
        if (!dirty) return;
        status.textContent = "Saving…";
        try {
            const res = await fetch(`/api/notes/${encodeURIComponent(noteName)}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ content: editor.value }),
            });
            if (res.status === 303 || res.redirected) {
                window.location.href = "/login";
                return;
            }
            if (!res.ok) throw new Error(`Save failed (${res.status})`);
            dirty = false;
            status.textContent = "Saved";
        } catch (err) {
            status.textContent = "Save failed — retrying…";
            saveTimer = setTimeout(save, 3000);
        }
    }

    function scheduleSave() {
        dirty = true;
        status.textContent = "Unsaved changes…";
        clearTimeout(saveTimer);
        saveTimer = setTimeout(save, 800);
    }

    editor.addEventListener("input", () => {
        if (!container.classList.contains("mode-edit")) renderPreview();
        scheduleSave();
    });

    editor.addEventListener("keydown", (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === "s") {
            e.preventDefault();
            clearTimeout(saveTimer);
            save();
        }
    });

    window.addEventListener("beforeunload", (e) => {
        if (dirty) {
            e.preventDefault();
            e.returnValue = "";
        }
    });

    // --- Pasted images ---
    function insertAtCursor(text) {
        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        editor.setRangeText(text, start, end, "end");
        editor.dispatchEvent(new Event("input"));
    }

    async function uploadImage(file) {
        const placeholder = `![Uploading ${file.name || "image"}…]()`;
        insertAtCursor(placeholder);

        const formData = new FormData();
        formData.append("file", file);
        try {
            const res = await fetch("/api/images", { method: "POST", body: formData });
            if (!res.ok) throw new Error(`Upload failed (${res.status})`);
            const { path } = await res.json();
            editor.value = editor.value.replace(placeholder, `![](${path})`);
        } catch (err) {
            editor.value = editor.value.replace(placeholder, "");
            status.textContent = "Image upload failed";
            setTimeout(() => (status.textContent = dirty ? "Unsaved changes…" : "Saved"), 3000);
        }
        editor.dispatchEvent(new Event("input"));
    }

    editor.addEventListener("paste", (e) => {
        const items = Array.from(e.clipboardData ? e.clipboardData.items : []);
        const imageItem = items.find((item) => item.type.startsWith("image/"));
        if (!imageItem) return;
        e.preventDefault();
        const file = imageItem.getAsFile();
        if (file) uploadImage(file);
    });

    renderPreview();
})();
