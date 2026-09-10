(function () {
    const editor = document.getElementById("editor");
    const preview = document.getElementById("preview");
    const status = document.getElementById("save-status");
    const noteName = window.NOTE_NAME;

    let saveTimer = null;
    let dirty = false;

    function renderPreview() {
        preview.innerHTML = marked.parse(editor.value);
    }

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
        renderPreview();
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

    renderPreview();
})();
