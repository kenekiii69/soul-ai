/* ==========================================================
   Soul AI Premium
   settings.js
========================================================== */

document.addEventListener("DOMContentLoaded", () => {

    loadSettings();

});

/* ==========================================================
   Default Settings
========================================================== */

const defaultSettings = {

    theme: "dark",

    fontSize: 16,

    animations: true,

    autoScroll: true,

    markdown: true

};

/* ==========================================================
   Load Settings
========================================================== */

function loadSettings() {

    const settings = getSettings();

    document.documentElement.style.fontSize =
        settings.fontSize + "px";

    if (settings.theme === "light") {

        document.body.classList.add("light-mode");

    }

}

/* ==========================================================
   Get Settings
========================================================== */

function getSettings() {

    const saved = localStorage.getItem("soul_settings");

    return saved
        ? JSON.parse(saved)
        : { ...defaultSettings };

}

/* ==========================================================
   Save Settings
========================================================== */

function saveSettings(settings) {

    localStorage.setItem(

        "soul_settings",

        JSON.stringify(settings)

    );

}

/* ==========================================================
   Theme
========================================================== */

function setTheme(theme) {

    const settings = getSettings();

    settings.theme = theme;

    saveSettings(settings);

    document.body.classList.toggle(

        "light-mode",

        theme === "light"

    );

}

/* ==========================================================
   Font Size
========================================================== */

function setFontSize(size) {

    const settings = getSettings();

    settings.fontSize = size;

    saveSettings(settings);

    document.documentElement.style.fontSize =
        size + "px";

}

/* ==========================================================
   Animation
========================================================== */

function toggleAnimations() {

    const settings = getSettings();

    settings.animations = !settings.animations;

    saveSettings(settings);

    showToast(

        settings.animations

            ? "✨ Animations Enabled"

            : "🚫 Animations Disabled"

    );

}

/* ==========================================================
   Auto Scroll
========================================================== */

function toggleAutoScroll() {

    const settings = getSettings();

    settings.autoScroll = !settings.autoScroll;

    saveSettings(settings);

}

/* ==========================================================
   Markdown
========================================================== */

function toggleMarkdown() {

    const settings = getSettings();

    settings.markdown = !settings.markdown;

    saveSettings(settings);

}

/* ==========================================================
   Export Settings
========================================================== */

function exportSettings() {

    const blob = new Blob(

        [

            JSON.stringify(

                getSettings(),

                null,

                2

            )

        ],

        {

            type: "application/json"

        }

    );

    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");

    a.href = url;

    a.download = "SoulAI-Settings.json";

    a.click();

    URL.revokeObjectURL(url);

}

/* ==========================================================
   Reset Settings
========================================================== */

function resetSettings() {

    if (!confirm("Reset all settings?")) {

        return;

    }

    localStorage.removeItem("soul_settings");

    location.reload();

}

/* ==========================================================
   Global
========================================================== */

window.getSettings = getSettings;

window.setTheme = setTheme;

window.setFontSize = setFontSize;

window.toggleAnimations = toggleAnimations;

window.toggleAutoScroll = toggleAutoScroll;

window.toggleMarkdown = toggleMarkdown;

window.exportSettings = exportSettings;

window.resetSettings = resetSettings;