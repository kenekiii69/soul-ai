/* ==========================================================
   Soul AI Premium
   script.js
========================================================== */

document.addEventListener("DOMContentLoaded", () => {

    console.log("🚀 Soul AI Started");

    initializeApp();

});

/* ==========================================
   Initialize
========================================== */

function initializeApp() {

    autoFocusInput();

    registerKeyboardShortcuts();

}

/* ==========================================
   Auto Focus
========================================== */

function autoFocusInput() {

    const input = document.getElementById("msg");

    if (input) {

        setTimeout(() => input.focus(), 100);

    }

}

/* ==========================================
   Toast
========================================== */

function showToast(message, type = "success") {

    const old = document.querySelector(".toast");

    if (old) old.remove();

    const toast = document.createElement("div");

    toast.className = `toast ${type}`;

    toast.innerText = message;

    document.body.appendChild(toast);

    requestAnimationFrame(() => {

        toast.classList.add("show");

    });

    setTimeout(() => {

        toast.classList.remove("show");

        setTimeout(() => {

            toast.remove();

        }, 300);

    }, 2500);

}

/* ==========================================
   Loader
========================================== */

function showLoader() {

    if (document.getElementById("loader")) return;

    const loader = document.createElement("div");

    loader.id = "loader";

    loader.innerHTML = `

        <div class="loader-box">

            <div class="loader-spinner"></div>

            <p>Loading...</p>

        </div>

    `;

    document.body.appendChild(loader);

}

function hideLoader() {

    document.getElementById("loader")?.remove();

}

/* ==========================================
   Keyboard Shortcuts
========================================== */

function registerKeyboardShortcuts() {

    document.addEventListener("keydown", e => {

        /* Ctrl + K */

        if (e.ctrlKey && e.key.toLowerCase() === "k") {

            e.preventDefault();

            document.getElementById("msg")?.focus();

        }

        /* ESC */

        if (e.key === "Escape") {

            document.getElementById("msg")?.blur();

        }

    });

}

/* ==========================================
   Helpers
========================================== */

function escapeHTML(text) {

    const div = document.createElement("div");

    div.innerText = text;

    return div.innerHTML;

}

function generateID() {

    return Date.now().toString(36) +

           Math.random().toString(36).substring(2, 8);

}

/* ==========================================
   Global
========================================== */

window.showToast = showToast;
window.showLoader = showLoader;
window.hideLoader = hideLoader;
window.escapeHTML = escapeHTML;
window.generateID = generateID;