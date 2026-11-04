/* Pases de batalla (/overwatch/pases y /overwatch/pases/<clave>) y novedades:
   - los vídeos de las recompensas se cargan y reproducen solo mientras se ven;
   - en el detalle de un pase, filtro por tipo (aspectos, grafitis, iconos…): oculta lo demás y las filas vacías;
   - las recompensas que no están en la galería de un héroe (iconos, tarjetas, amuletos…) se abren en grande;
     las que sí, son enlaces a su galería (#aspectos/<id>). */
(function () {
    "use strict";
    const videos = document.querySelectorAll(".ow-reward-media video, .ow-pitem-media video");
    if (videos.length && "IntersectionObserver" in window) {
        const io = new IntersectionObserver((entradas) => {
            for (const e of entradas) {
                const v = e.target;
                if (e.isIntersecting) {
                    if (!v.src && v.dataset.src) v.src = v.dataset.src;
                    v.play().catch(() => {});
                } else {
                    v.pause();
                }
            }
        }, { rootMargin: "150px" });
        videos.forEach((v) => io.observe(v));
    }

    const caja = document.querySelector(".ow-lightbox");
    if (caja && caja.showModal) {
        const media = caja.querySelector(".ow-lightbox-media");
        document.addEventListener("click", (ev) => {
            const it = ev.target.closest("button.ow-pitem[data-big]");
            if (!it) return;
            const url = it.dataset.big;
            media.innerHTML = "";
            const el = document.createElement(it.dataset.video ? "video" : "img");
            Object.assign(el, it.dataset.video ? { src: url, autoplay: true, loop: true, muted: true, playsInline: true, controls: true }
                : { src: url, alt: "" });
            media.appendChild(el);
            const info = it.querySelector(".ow-pitem-info");
            caja.querySelector(".ow-lightbox-name").textContent = info ? info.innerText.replace(/\n+/g, " · ") : "";
            caja.style.setProperty("--rc", getComputedStyle(it).getPropertyValue("--rc"));
            caja.showModal();
        });
        caja.addEventListener("click", (ev) => {  // cerrar: botón o clic fuera de la imagen
            if (ev.target === caja || ev.target.closest("[data-close]")) caja.close();
        });
        caja.addEventListener("close", () => { media.innerHTML = ""; });
    }

    // ---- Cartel ampliado: rueda / doble clic / botones para el zoom, arrastrar para moverse
    const zoom = document.querySelector(".ow-zoom");
    if (zoom && zoom.showModal) {
        const stage = zoom.querySelector(".ow-zoom-stage");
        const img = stage.querySelector("img");
        let escala = 1, x = 0, y = 0, arrastre = null;
        const pintar = () => { img.style.transform = `translate(${x}px, ${y}px) scale(${escala})`; };
        const ajustar = () => { escala = 1; x = 0; y = 0; pintar(); };
        function acercar(factor, cx, cy) {  // cx, cy: punto (relativo al centro) que se queda quieto
            const nueva = Math.min(8, Math.max(1, escala * factor));
            const k = nueva / escala;
            x = cx - (cx - x) * k;
            y = cy - (cy - y) * k;
            escala = nueva;
            if (escala === 1) { x = 0; y = 0; }
            pintar();
        }
        const centro = (ev) => {
            const r = stage.getBoundingClientRect();
            return [ev.clientX - r.left - r.width / 2, ev.clientY - r.top - r.height / 2];
        };
        const abrir = (src, alt) => { img.src = src; img.alt = alt || ""; ajustar(); zoom.showModal(); };
        document.addEventListener("click", (ev) => {
            const el = ev.target.closest("img.ow-zoomable");
            if (el) { ev.preventDefault(); abrir(el.currentSrc || el.src, el.alt); }
        });
        document.addEventListener("keydown", (ev) => {
            const el = ev.target.closest && ev.target.closest("img.ow-zoomable");
            if (el && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); abrir(el.currentSrc || el.src, el.alt); }
        });
        stage.addEventListener("wheel", (ev) => {
            ev.preventDefault();
            acercar(ev.deltaY < 0 ? 1.2 : 1 / 1.2, ...centro(ev));
        }, { passive: false });
        stage.addEventListener("dblclick", (ev) => (escala > 1 ? ajustar() : acercar(2.5, ...centro(ev))));
        stage.addEventListener("pointerdown", (ev) => {
            if (escala === 1) return;
            arrastre = { px: ev.clientX - x, py: ev.clientY - y };
            stage.setPointerCapture(ev.pointerId);
            stage.classList.add("ow-dragging");
        });
        stage.addEventListener("pointermove", (ev) => {
            if (!arrastre) return;
            x = ev.clientX - arrastre.px;
            y = ev.clientY - arrastre.py;
            pintar();
        });
        const soltar = () => { arrastre = null; stage.classList.remove("ow-dragging"); };
        stage.addEventListener("pointerup", soltar);
        stage.addEventListener("pointercancel", soltar);
        zoom.addEventListener("click", (ev) => {
            const b = ev.target.closest("[data-zoom]");
            if (b) return +b.dataset.zoom === 0 ? ajustar() : acercar(+b.dataset.zoom > 0 ? 1.5 : 1 / 1.5, 0, 0);
            if (ev.target === zoom || ev.target.closest("[data-close]")) zoom.close();
        });
        zoom.addEventListener("close", () => { img.removeAttribute("src"); });
    }

    const filtros = document.querySelector(".ow-pass-filters");
    if (!filtros) return;
    filtros.addEventListener("click", (ev) => {
        const btn = ev.target.closest("button[data-kind]");
        if (!btn) return;
        filtros.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === btn));
        const tipo = btn.dataset.kind;
        document.querySelectorAll(".ow-pitem").forEach((it) => {
            it.hidden = !!tipo && it.dataset.kind !== tipo;
        });
        document.querySelectorAll(".ow-pass-row, .ow-pass-prestige-item").forEach((fila) => {
            fila.hidden = !!tipo && !fila.querySelector(".ow-pitem:not([hidden])");
        });
    });
})();
