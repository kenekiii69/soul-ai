/* ==========================================================
   Soul AI Premium Theme Manager
========================================================== */

document.addEventListener("DOMContentLoaded", () => {

    const themeBtn = document.getElementById("theme-btn");
    const body = document.body;

    /* ==========================
       Load Saved Theme
    ========================== */

    const savedTheme = localStorage.getItem("soul_theme");

    if (savedTheme === "light") {
        body.classList.add("light-mode");
        themeBtn.innerHTML = "🌞 Light Mode";
    } else {
        body.classList.remove("light-mode");
        themeBtn.innerHTML = "🌙 Dark Mode";
    }

    /* ==========================  
       Toggle Theme
    ========================== */

    themeBtn.addEventListener("click", () => {

        body.classList.toggle("light-mode");

        const isLight = body.classList.contains("light-mode");

        localStorage.setItem(
            "soul_theme",
            isLight ? "light" : "dark"
        );

        themeBtn.innerHTML = isLight
            ? "🌞 Light Mode"
            : "🌙 Dark Mode";

    });

});