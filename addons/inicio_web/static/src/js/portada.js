/* Portada (inicio_web): reloj en vivo, saludo según la hora y un foco de luz que sigue al ratón en las tarjetas. */
(function () {
    "use strict";
    const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
    const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
        "octubre", "noviembre", "diciembre"];

    function saludo(h) {
        if (h >= 6 && h < 13) return "Buenos días";
        if (h >= 13 && h < 21) return "Buenas tardes";
        return "Buenas noches";
    }

    function iniciar() {
        const app = document.querySelector(".ini-app");
        if (!app) return;
        const reloj = app.querySelector("[data-ini-reloj]");
        const fecha = app.querySelector("[data-ini-fecha]");
        const sal = app.querySelector("[data-ini-saludo]");
        const pad = (n) => String(n).padStart(2, "0");

        function tic() {
            const d = new Date();
            reloj.innerHTML = `${pad(d.getHours())}<span class="ini-dos">:</span>${pad(d.getMinutes())}`;
            const dia = DIAS[d.getDay()];
            fecha.textContent = `${dia[0].toUpperCase()}${dia.slice(1)}, ${d.getDate()} de ${MESES[d.getMonth()]}`;
            sal.textContent = saludo(d.getHours());
        }
        tic();
        setInterval(tic, 10000);

        app.querySelectorAll(".ini-tarjeta").forEach((t) => {
            t.addEventListener("pointermove", (ev) => {
                const r = t.getBoundingClientRect();
                t.style.setProperty("--x", `${ev.clientX - r.left}px`);
                t.style.setProperty("--y", `${ev.clientY - r.top}px`);
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", iniciar);
    } else {
        iniciar();
    }
})();
