/* Pantalla de selección de héroes (/overwatch).
   - Plantilla abajo por roles (tanque, daño, apoyo); clic = ver el héroe (fondo, nombre, rol, datos, habilidades).
   - Favoritos: botón «Añadir a favoritos» o clic derecho en una casilla; se guardan en la cuenta (POST JSON).
     «★ Favoritos» filtra la plantilla. Sin permiso (visitantes) no hay favoritos: data.can_fav = false.
   - Aleatorio: entre los favoritos (o todos) y por rol; recorre las casillas cada vez más despacio hasta pararse.
   - Teclado: ← → cambian de héroe, R sortea, F marca favorito, Enter abre la ficha.
   El héroe elegido se recuerda en la URL (#ana) para volver a él desde la ficha. */
(function () {
    "use strict";
    const data = JSON.parse(document.getElementById("ow-data").textContent);
    const heroes = data.heroes;
    const canFav = data.can_fav;
    const byId = new Map(heroes.map((h) => [h.id, h]));
    const roleNames = Object.fromEntries(data.roles.map((r) => [r.key, r.name]));
    const $ = (sel, root = document) => root.querySelector(sel);
    const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

    const roster = $(".ow-roster");
    const tiles = new Map(); // id → botón
    let current = null;
    let spinning = false;

    // ---------------------------------------------------------------- plantilla
    function buildRoster() {
        for (const group of $$(".ow-roster-group")) {
            const box = $(".ow-roster-tiles", group);
            const list = heroes.filter((h) => h.role === group.dataset.role);
            for (const h of list) {
                const b = document.createElement("button");
                b.type = "button";
                b.className = "ow-tile" + (h.fav ? " fav" : "");
                b.title = `${h.name} (clic derecho: favorito)`;
                b.dataset.id = h.id;
                b.innerHTML = `<span class="ow-tile-frame"></span><span class="ow-tile-inner">${
                    h.portrait ? `<img src="${esc(h.portrait)}" alt="" loading="lazy">` : `<span class="ow-tile-initial">${esc(h.name[0])}</span>`
                }</span><span class="ow-tile-fav">★</span>`;
                b.addEventListener("click", () => !spinning && select(h));
                b.addEventListener("contextmenu", (ev) => {
                    ev.preventDefault();
                    toggleFav(h);
                });
                box.appendChild(b);
                tiles.set(h.id, b);
            }
            if (!list.length) box.innerHTML = '<span class="ow-roster-empty">Sin héroes</span>';
        }
        fitRoster();
        window.addEventListener("resize", fitRoster);
        if (!heroes.length) {
            $(".ow-hero-name").textContent = "Sin héroes";
            $(".ow-hero-desc").textContent = "Importa el catálogo desde el backend: Overwatch → Configuración → Actualizar catálogo.";
            $(".ow-hero-buttons").hidden = true;
        }
    }

    /** Columnas de cada rol: todos en 2 filas en pantallas anchas (3 en medianas, como haga falta en el móvil). */
    function fitRoster() {
        const app = $(".ow-app");
        // Alto que queda bajo la cabecera del sitio: posición de .ow-app en la página (no en la ventana, que cambia
        // al bajar). Solo al cargar o si cambia el ancho: en el móvil, esconder la barra de direcciones cambia el alto
        if (innerWidth !== fitRoster.width) {
            fitRoster.width = innerWidth;
            const top = app.getBoundingClientRect().top + scrollY;
            app.style.setProperty("--ow-alto", `${Math.max(560, innerHeight - top)}px`);
        }
        const rows = innerWidth >= 1200 ? 2 : innerWidth >= 900 ? 3 : 0;
        for (const group of $$(".ow-roster-group")) {
            const n = heroes.filter((h) => h.role === group.dataset.role).length || 1;
            const cols = rows ? Math.ceil(n / rows) : Math.min(n, Math.floor((innerWidth - 40) / 50));
            $(".ow-roster-tiles", group).style.setProperty("--cols", cols);
        }
    }

    // ---------------------------------------------------------------- héroe elegido
    const bgImg = $(".ow-bg-img");
    let bgToken = 0;
    function setBackground(url) {
        const token = ++bgToken;
        bgImg.classList.add("ow-fade");
        const apply = () => {
            if (token !== bgToken) return;
            bgImg.style.backgroundImage = url ? `url("${url}")` : "";
            bgImg.classList.remove("ow-fade");
        };
        if (!url) return setTimeout(apply, 200);
        const img = new Image();
        img.onload = img.onerror = () => setTimeout(apply, 120);
        img.src = url;
    }

    function statBlock(label, value, cls) {
        if (!value) return "";
        const n = Math.max(1, Math.round(value / 25)); // un segmento cada 25 puntos, como la barra del juego
        const segs = `<i class="${cls}"></i>`.repeat(n);
        return `<div class="ow-stat"><span>${label}</span><strong>${value}</strong><div class="ow-stat-bar">${segs}</div></div>`;
    }

    function select(h, { quiet = false } = {}) {
        if (!h) return;
        current = h;
        tiles.forEach((b, id) => b.classList.toggle("selected", id === h.id));
        $(".ow-hero-role-icon").innerHTML = roleIcon(h.role);
        $(".ow-hero-subrole").textContent = [roleNames[h.role], h.subrole].filter(Boolean).join(" · ");
        const name = $(".ow-hero-name");
        name.textContent = h.name;
        name.classList.remove("ow-pop");
        void name.offsetWidth; // reinicia la animación
        name.classList.add("ow-pop");
        $(".ow-hero-desc").textContent = h.description;
        $(".ow-hero-stats").innerHTML =
            statBlock("Salud", h.health, "hp") + statBlock("Armadura", h.armor, "ar") + statBlock("Escudos", h.shields, "sh");
        $(".ow-abilities").innerHTML = h.abilities
            .map((a, i) => `<div class="ow-ability" style="animation-delay:${i * 50}ms"><span>${esc(a.name)}</span>${a.icon ? `<img src="${esc(a.icon)}" alt="">` : ""}</div>`)
            .join("");
        $(".ow-btn-details").href = `/overwatch/heroe/${encodeURIComponent(h.key)}`;
        updateFavButton();
        setBackground(h.background);
        if (!quiet) history.replaceState(null, "", `#${h.key}`);
    }

    function roleIcon(role) {
        const svg = $(`.ow-roster-group[data-role="${role}"] .ow-role-icon`);
        return svg ? svg.outerHTML : "";
    }

    // ---------------------------------------------------------------- favoritos
    function updateFavButton() {
        const btn = $(".ow-btn-fav");
        if (!btn) return;
        const fav = current && current.fav;
        btn.classList.toggle("active", !!fav);
        $(".ow-star", btn).textContent = fav ? "★" : "☆";
        $(".ow-fav-label", btn).textContent = fav ? "Favorito" : "Añadir a favoritos";
    }

    async function toggleFav(h) {
        if (!canFav) return;
        h.fav = !h.fav;
        tiles.get(h.id).classList.toggle("fav", h.fav);
        if (h === current) updateFavButton();
        try {
            const r = await fetch("/overwatch/api/favorito", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ hero_id: h.id, fav: h.fav }),
            });
            if (!r.ok) throw new Error(r.status);
            const res = await r.json();
            const favs = new Set(res.favorites);
            heroes.forEach((x) => {
                x.fav = favs.has(x.id);
                tiles.get(x.id).classList.toggle("fav", x.fav);
            });
            updateFavButton();
        } catch {
            h.fav = !h.fav; // no se pudo guardar: se deshace
            tiles.get(h.id).classList.toggle("fav", h.fav);
            if (h === current) updateFavButton();
            message("No se ha podido guardar el favorito");
        }
    }

    // ---------------------------------------------------------------- aleatorio
    let randomRole = "";
    const msg = $(".ow-random-msg");
    function message(t) {
        msg.textContent = t;
        clearTimeout(message.t);
        message.t = setTimeout(() => (msg.textContent = ""), 4000);
    }

    function pool() {
        const onlyFavs = canFav && $("[data-random-favs]").checked;
        let list = heroes.filter((h) => !randomRole || h.role === randomRole);
        if (onlyFavs) {
            const favs = list.filter((h) => h.fav);
            if (!favs.length) {
                message(`No tienes favoritos${randomRole ? " de " + roleNames[randomRole].toLowerCase() : ""}: sorteo entre todos`);
                return list;
            }
            return favs;
        }
        return list;
    }

    async function spin() {
        if (spinning) return;
        const list = pool();
        if (!list.length) return message("No hay héroes para sortear");
        spinning = true;
        $("[data-action=random]").disabled = true;
        // Atenúa los que no entran en el sorteo
        const ids = new Set(list.map((h) => h.id));
        tiles.forEach((b, id) => b.classList.toggle("dim", !ids.has(id)));
        if (roster.classList.contains("only-favs") && list.some((h) => !h.fav)) setShow("all");
        // Nunca el que ya está elegido (salvo que sea el único posible)
        const options = list.length > 1 ? list.filter((h) => h !== current) : list;
        const winner = options[Math.floor(Math.random() * options.length)];
        // Recorrido: unas cuantas casillas al azar cada vez más despacio, terminando en la ganadora
        const steps = Math.min(26, 10 + list.length);
        let prev = null;
        for (let i = 0; i < steps; i++) {
            let h = i === steps - 1 ? winner : list[Math.floor(Math.random() * list.length)];
            if (list.length > 1 && h === prev && i !== steps - 1) h = list[(list.indexOf(h) + 1) % list.length];
            if (prev) tiles.get(prev.id).classList.remove("spin");
            tiles.get(h.id).classList.add("spin");
            prev = h;
            await sleep(45 + Math.pow(i / steps, 3) * 380);
        }
        tiles.get(winner.id).classList.remove("spin");
        tiles.forEach((b) => b.classList.remove("dim"));
        select(winner);
        message(`¡Te toca ${winner.name}!`);
        spinning = false;
        $("[data-action=random]").disabled = false;
    }

    // ---------------------------------------------------------------- filtros y eventos
    function setShow(what) {
        roster.classList.toggle("only-favs", what === "favs");
        $$(".ow-roster-filter button").forEach((b) => b.classList.toggle("active", b.dataset.show === what));
        if (what === "favs" && !heroes.some((h) => h.fav)) message("Aún no tienes favoritos: clic derecho en un héroe o «Añadir a favoritos»");
    }

    function visibleList() {
        const favsOnly = roster.classList.contains("only-favs");
        return heroes.filter((h) => !favsOnly || h.fav);
    }

    function bind() {
        if (canFav) $("[data-action=fav]").addEventListener("click", () => current && toggleFav(current));
        $("[data-action=random]").addEventListener("click", spin);
        $$("[data-random-role]").forEach((b) =>
            b.addEventListener("click", () => {
                randomRole = b.dataset.randomRole;
                $$("[data-random-role]").forEach((x) => x.classList.toggle("active", x === b));
            }));
        $$(".ow-roster-filter button").forEach((b) => b.addEventListener("click", () => setShow(b.dataset.show)));
        document.addEventListener("keydown", (ev) => {
            if (ev.target.closest("input, textarea, select") || spinning || ev.ctrlKey || ev.metaKey || ev.altKey) return;
            const list = visibleList();
            if ((ev.key === "ArrowRight" || ev.key === "ArrowLeft") && list.length) {
                const i = Math.max(0, list.indexOf(current));
                select(list[(i + (ev.key === "ArrowRight" ? 1 : list.length - 1)) % list.length]);
                ev.preventDefault();
            } else if (ev.key.toLowerCase() === "r") spin();
            else if (ev.key.toLowerCase() === "f" && current) toggleFav(current);
            else if (ev.key === "Enter" && current) location.href = $(".ow-btn-details").href;
        });
    }

    buildRoster();
    bind();
    const fromHash = heroes.find((h) => h.key === decodeURIComponent(location.hash.slice(1)));
    select(fromHash || heroes.find((h) => h.fav) || heroes[0], { quiet: !fromHash });
})();
