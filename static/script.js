// ============================================================
// SETTINGS (Dark Mode, text size, table density)
// Stored in localStorage only — this project uses no database,
// so these are per-browser preferences.
// ============================================================

const SETTINGS_KEY = "srms_settings";

function loadSettings() {
    try {
        const raw = localStorage.getItem(SETTINGS_KEY);
        if (!raw) return { theme: "light", fontSize: "normal", density: "comfortable" };
        const parsed = JSON.parse(raw);
        return {
            theme: parsed.theme || "light",
            fontSize: parsed.fontSize || "normal",
            density: parsed.density || "comfortable"
        };
    } catch (e) {
        return { theme: "light", fontSize: "normal", density: "comfortable" };
    }
}

function saveSettings(settings) {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

function applySettings(settings) {
    const root = document.documentElement;
    root.setAttribute("data-theme", settings.theme);
    root.setAttribute("data-fontsize", settings.fontSize);
    root.setAttribute("data-density", settings.density);
}

// Applied immediately (also mirrored inline in base.html <head> to avoid flash)
applySettings(loadSettings());

function updateSetting(key, value) {
    const settings = loadSettings();
    settings[key] = value;
    saveSettings(settings);
    applySettings(settings);
}

function initSettingsPage() {
    const themeToggle = document.getElementById("darkModeToggle");
    const fontToggle = document.getElementById("largeTextToggle");
    const densityToggle = document.getElementById("compactTableToggle");

    if (!themeToggle) return; // Not on the settings page.

    const current = loadSettings();
    themeToggle.checked = current.theme === "dark";
    fontToggle.checked = current.fontSize === "large";
    densityToggle.checked = current.density === "compact";

    themeToggle.addEventListener("change", () => {
        updateSetting("theme", themeToggle.checked ? "dark" : "light");
    });

    fontToggle.addEventListener("change", () => {
        updateSetting("fontSize", fontToggle.checked ? "large" : "normal");
    });

    densityToggle.addEventListener("change", () => {
        updateSetting("density", densityToggle.checked ? "compact" : "comfortable");
    });
}

// ============================================================
// PASSWORD SHOW/HIDE EYE ICONS
// Automatically attached to every password field on the site.
// ============================================================

function eyeIconSVG(showing) {
    if (showing) {
        // "Hide" icon (eye with a slash)
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
            'stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-10-8-10-8a18.6 18.6 0 0 1 4.22-5.94M9.9 4.24A10.9 10.9 0 0 1 12 4c7 0 10 8 10 8a18.6 18.6 0 0 1-2.16 3.19M14.12 14.12A3 3 0 1 1 9.88 9.88"></path>' +
            '<line x1="1" y1="1" x2="23" y2="23"></line></svg>';
    }
    // "Show" icon (plain eye)
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
        'stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>' +
        '<circle cx="12" cy="12" r="3"></circle></svg>';
}

function setupPasswordToggles() {
    document.querySelectorAll('input[type="password"]').forEach((input) => {
        if (input.dataset.eyeAttached) return;
        input.dataset.eyeAttached = "true";

        const wrap = document.createElement("div");
        wrap.className = "password-wrap";
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "password-eye";
        btn.setAttribute("aria-label", "Show password");
        btn.innerHTML = eyeIconSVG(false);
        wrap.appendChild(btn);

        btn.addEventListener("click", () => {
            const nowShowing = input.type === "password";
            input.type = nowShowing ? "text" : "password";
            btn.innerHTML = eyeIconSVG(nowShowing);
            btn.setAttribute("aria-label", nowShowing ? "Hide password" : "Show password");
        });
    });
}

// ============================================================
// SIDEBAR MENU TOGGLE (mobile)
// ============================================================

function initNavToggle() {
    const toggleBtn = document.getElementById("navToggle");
    const nav = document.getElementById("sideNav");
    const backdrop = document.getElementById("sidebarBackdrop");

    if (!toggleBtn || !nav || !backdrop) return;

    function setOpen(isOpen) {
        nav.classList.toggle("open", isOpen);
        backdrop.classList.toggle("open", isOpen);
        toggleBtn.setAttribute("aria-expanded", String(isOpen));
        toggleBtn.setAttribute("aria-label", isOpen ? "Close navigation" : "Open navigation");
    }

    toggleBtn.addEventListener("click", () => {
        setOpen(!nav.classList.contains("open"));
    });

    backdrop.addEventListener("click", () => setOpen(false));
    nav.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => setOpen(false));
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") setOpen(false);
    });
}

// ============================================================
// SIGN UP FORM: role-based fields (Student vs Teacher)
// ============================================================

function toggleRoleFields() {
    const selectedInput = document.querySelector('input[name="role"]:checked');
    if (!selectedInput) return;

    const selected = selectedInput.value;
    const studentBox = document.getElementById("studentFields");
    const teacherBox = document.getElementById("teacherFields");
    if (!studentBox || !teacherBox) return;

    const studentInputs = studentBox.querySelectorAll("input, select");
    const teacherInputs = teacherBox.querySelectorAll("input, select");

    if (selected === "student") {
        studentBox.style.display = "block";
        teacherBox.style.display = "none";
        studentInputs.forEach((el) => (el.required = true));
        teacherInputs.forEach((el) => {
            el.required = false;
        });
    } else {
        studentBox.style.display = "none";
        teacherBox.style.display = "block";
        studentInputs.forEach((el) => {
            el.required = false;
        });
        teacherInputs.forEach((el) => (el.required = true));
    }
}

function initSignupForm() {
    const roleInputs = document.querySelectorAll('input[name="role"]');
    if (roleInputs.length === 0) return;

    roleInputs.forEach((el) => el.addEventListener("change", toggleRoleFields));
    toggleRoleFields();

    // Student ID: digits only, capped at 6 characters.
    const studentIdInput = document.getElementById("studentIdInput");
    if (studentIdInput) {
        studentIdInput.addEventListener("input", () => {
            studentIdInput.value = studentIdInput.value.replace(/\D/g, "").slice(0, 6);
        });
    }
}

// ============================================================
// TEACHER DASHBOARD / ADMIN: student-ID fields, digits only
// ============================================================

function initDigitsOnlyFields() {
    const ids = ["studentIdSearchInput", "newStudentIdInput"];
    ids.forEach((id) => {
        const input = document.getElementById(id);
        if (!input) return;
        input.addEventListener("input", () => {
            input.value = input.value.replace(/\D/g, "").slice(0, 6);
        });
    });
}

// ============================================================
// INIT
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    setupPasswordToggles();
    initNavToggle();
    initSignupForm();
    initSettingsPage();
    initDigitsOnlyFields();
});