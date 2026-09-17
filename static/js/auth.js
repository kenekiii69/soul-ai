
/* ==========================================================
   Soul AI Premium
   auth.js
========================================================== */


/* ==========================================================
   DOM READY
========================================================== */

document.addEventListener("DOMContentLoaded", () => {

    initializeAuth();

    initializeLoginForm();

});


/* ==========================================================
   Initialize Authentication
========================================================== */

async function initializeAuth() {

    try {

        const res = await fetch("/profile");

        // Guest user — 401 is expected
        if (res.status === 401) {

            console.log("👤 Guest Mode");

            return false;
        }

        const data = await res.json();

        if (data.success) {

            console.log(
                `👋 Welcome back, ${data.user.username}`
            );

            return true;

        }

        console.log("👤 Guest Mode");

        return false;

    } catch (err) {

        console.log("👤 Guest Mode");

        return false;

    }

}

/* ==========================================================
   LOGIN FORM
========================================================== */

function initializeLoginForm() {

    const loginForm = document.getElementById("loginForm");

    if (!loginForm) {

        return;

    }

    loginForm.addEventListener("submit", async (event) => {

        event.preventDefault();

        const emailInput = document.getElementById("email");
        const passwordInput = document.getElementById("password");
        const message = document.getElementById("login-message");

        const email = emailInput.value.trim();
        const password = passwordInput.value;

        if (!email || !password) {

            if (message) {

                message.textContent = "Please enter email and password.";

            }

            return;

        }

        try {

            const data = await login(email, password);

            if (data.success) {

                if (message) {

                    message.textContent = data.message;

                }

                /*
                 * Login successful.
                 *
                 * Small delay so the user can see
                 * the success message.
                 */

                setTimeout(() => {

                    window.location.href = "/";

                }, 700);

            } else {

                if (message) {

                    message.textContent = data.message;

                }

            }

        } catch (error) {

            console.error("Login Error:", error);

            if (message) {

                message.textContent =
                    "Unable to connect to server.";

            }

        }

    });

}


/* ==========================================================
   REGISTER
========================================================== */

async function register(username, email, password) {

    const res = await fetch("/register", {

        method: "POST",

        headers: {

            "Content-Type": "application/json"

        },

        body: JSON.stringify({

            username,
            email,
            password

        })

    });

    const data = await res.json();

    if (window.showToast) {

        if (data.success) {

            showToast(data.message);

        } else {

            showToast(data.message, "error");

        }

    }

    return data;

}


/* ==========================================================
   LOGIN API
========================================================== */

async function login(email, password) {

    const res = await fetch("/login", {

        method: "POST",

        headers: {

            "Content-Type": "application/json"

        },

        body: JSON.stringify({

            email,
            password

        })

    });

    const data = await res.json();

    if (data.success) {

        if (window.showToast) {

            showToast(
                `Welcome ${data.user.username} 👋`
            );

        }

    } else {

        if (window.showToast) {

            showToast(
                data.message,
                "error"
            );

        }

    }

    return data;

}


/* ==========================================================
   LOGOUT
========================================================== */

async function logout() {

    await fetch("/logout", {

        method: "POST"

    });

    if (window.showToast) {

        showToast("Logged out successfully");

    }

    location.reload();

}


/* ==========================================================
   CURRENT USER
========================================================== */

async function getCurrentUser() {

    const res = await fetch("/profile");

    return await res.json();

}


/* ==========================================================
   CHECK LOGIN
========================================================== */

async function isLoggedIn() {

    const data = await getCurrentUser();

    return data.success;

}


/* ==========================================================
   REQUIRE LOGIN
========================================================== */

async function requireLogin(callback) {

    const logged = await isLoggedIn();

    if (!logged) {

        if (window.showToast) {

            showToast(
                "Please login first",
                "error"
            );

        }

        return false;

    }

    if (typeof callback === "function") {

        callback();

    }

    return true;

}


/* ==========================================================
   EXPORT
========================================================== */

window.login = login;
window.logout = logout;
window.register = register;
window.getCurrentUser = getCurrentUser;
window.isLoggedIn = isLoggedIn;
window.requireLogin = requireLogin;