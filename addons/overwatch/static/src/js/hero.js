/* Ficha y galería de un héroe (/overwatch/heroe/<clave>).
   - Pestañas: Resumen, Historia y una por tipo de cosmético (#aspectos… en la URL para enlazarlas).
   - Resumen: clic en una habilidad = su vídeo en el reproductor de la derecha.
   - Historia: el vídeo de YouTube se carga al abrir la pestaña.
   - Galería: casillas con el color de su rareza, filtro por rareza y buscador; clic = vista grande a la derecha
     (imagen o vídeo). Las imágenes y vídeos vienen de la wiki: se cargan solo al verse (IntersectionObserver) y
     los vídeos se reproducen al pasar el ratón. Si una no carga, la casilla muestra la inicial.
   - Favorito: el mismo botón que en la selección. */
(function () {
    "use strict";
    const data = JSON.parse(document.getElementById("ow-data").textContent);
    const $ = (sel, root = document) => root.querySelector(sel);
    const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
    const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
    const rarityName = Object.fromEntries(data.rarities.map((r) => [r.key, r.name]));
    const typeKeys = data.types.map((t) => t.key);
    const SLUGS = { summary: "resumen", story: "historia", skin: "aspectos", emote: "gestos", victory_pose: "poses", highlight_intro: "presentaciones", spray: "grafitis" };
    const FROM_SLUG = Object.fromEntries(Object.entries(SLUGS).map(([k, v]) => [v, k]));

    // ---------------------------------------------------------------- pestañas
    function openTab(tab, { push = true } = {}) {
        const btn = $(`.ow-tabs [data-tab="${tab}"]`);
        if (!btn || btn.disabled) tab = "summary";
        $$(".ow-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
        const isCosmetic = typeKeys.includes(tab);
        $$(".ow-panel").forEach((p) => (p.hidden = p.dataset.panel !== (isCosmetic ? "cosmetics" : tab)));
        if (tab === "story") {
            const frame = $(".ow-video-frame iframe");
            if (frame && !frame.src) frame.src = frame.dataset.src;
        }
        const video = $(".ow-ability-video");
        if (video) tab === "summary" ? video.play().catch(() => {}) : video.pause();
        if (isCosmetic) locker.show(tab);
        if (push) history.replaceState(null, "", `#${SLUGS[tab]}`);
    }

    // ---------------------------------------------------------------- resumen
    function buildAbilities() {
        const player = $(".ow-ability-video");
        const caption = $(".ow-ability-caption");
        for (const list of $$(".ow-ability-list")) {
            const items = data.abilities.filter((a) => a.kind === list.dataset.kind);
            list.innerHTML = items
                .map((a, i) => `<button type="button" class="ow-ab" data-i="${data.abilities.indexOf(a)}">
                    ${a.icon ? `<img src="${esc(a.icon)}" alt="">` : "<span></span>"}
                    <span><strong>${esc(a.name)}</strong><small>${esc(a.description)}</small></span></button>`)
                .join("");
        }
        if (!data.abilities.some((a) => a.kind.startsWith("perk"))) {
            $(".ow-perks").hidden = true;
            $(".ow-perks-title").hidden = true;
        }
        function play(a, btn) {
            $$(".ow-ab").forEach((b) => b.classList.toggle("active", b === btn));
            $("strong", caption).textContent = a.name;
            $("p", caption).textContent = a.description;
            if (a.video || a.webm) {
                player.poster = a.thumb || "";
                player.innerHTML = (a.webm ? `<source src="${esc(a.webm)}" type="video/webm">` : "") + (a.video ? `<source src="${esc(a.video)}" type="video/mp4">` : "");
                player.load();
                player.play().catch(() => {});
                player.hidden = false;
            } else {
                player.pause();
                player.hidden = true;
            }
        }
        $$(".ow-ab").forEach((btn) => {
            const a = data.abilities[+btn.dataset.i];
            if (a.kind === "ability") btn.addEventListener("click", () => play(a, btn));
        });
        const first = data.abilities.find((a) => a.kind === "ability" && (a.video || a.webm));
        if (first) play(first, $(`.ow-ab[data-i="${data.abilities.indexOf(first)}"]`));
        else $(".ow-ability-player").hidden = true;
    }

    // ---------------------------------------------------------------- galería de cosméticos
    const locker = (() => {
        const grid = $(".ow-locker-grid");
        const chips = $(".ow-rarity-chips");
        const search = $(".ow-search");
        const empty = $(".ow-locker-empty");
        const preview = $(".ow-preview-media");
        let type = null;
        let rarity = "";
        let selected = null;

        // Carga perezosa: el src se pone al entrar en pantalla
        const io = new IntersectionObserver((entries) => {
            for (const e of entries) {
                if (!e.isIntersecting) continue;
                const el = e.target;
                el.src = el.dataset.src;
                io.unobserve(el);
            }
        }, { rootMargin: "300px" });

        function mediaHtml(item, big) {
            if (!item.url) return `<span class="ow-item-missing">${esc(item.name[0])}</span>`;
            if (item.kind === "video") {
                return big
                    ? `<video src="${esc(item.url)}" autoplay loop muted playsinline controls></video>`
                    : `<video data-src="${esc(item.url)}" muted loop playsinline preload="metadata"></video>`;
            }
            return big ? `<img src="${esc(item.url)}" alt="">` : `<img data-src="${esc(item.url)}" alt="">`;
        }

        function onMediaError(el) {
            const box = el.closest(".ow-item, .ow-preview-media");
            if (!box) return;
            const name = box.dataset.name || ($(".ow-preview-name") || {}).textContent || "?";
            el.replaceWith(Object.assign(document.createElement("span"), { className: "ow-item-missing", textContent: name[0] || "?" }));
        }

        function render() {
            const q = search.value.trim().toLowerCase();
            const items = (data.cosmetics[type] || []).filter((c) => (!rarity || c.rarity === rarity) && (!q || c.name.toLowerCase().includes(q) || c.source.toLowerCase().includes(q)));
            grid.innerHTML = items
                .map((c) => `<button type="button" class="ow-item" data-id="${c.id}" data-rarity="${c.rarity}" data-type="${type}" data-name="${esc(c.name)}" title="${esc(c.name)}">
                    ${mediaHtml(c, false)}<span class="ow-item-name">${esc(c.name)}</span></button>`)
                .join("");
            empty.hidden = !!items.length;
            $$("img[data-src], video[data-src]", grid).forEach((el) => {
                el.addEventListener("error", () => onMediaError(el), { once: true });
                io.observe(el);
            });
            $$(".ow-item", grid).forEach((b) => {
                const c = items.find((x) => x.id === +b.dataset.id);
                b.addEventListener("click", () => pick(c));
                const v = $("video", b);
                if (v) {
                    b.addEventListener("mouseenter", () => v.src && v.play().catch(() => {}));
                    b.addEventListener("mouseleave", () => v.pause());
                }
            });
            if (!items.some((c) => c === selected)) pick(items[0] || null);
            else markSelected();
        }

        function markSelected() {
            $$(".ow-item", grid).forEach((b) => b.classList.toggle("active", selected && +b.dataset.id === selected.id));
        }

        function pick(c) {
            selected = c;
            markSelected();
            const box = $(".ow-locker-preview");
            box.hidden = !c;
            if (!c) return;
            preview.style.setProperty("--rc", `var(--r-${c.rarity})`);
            $(".ow-preview-info").style.setProperty("--rc", `var(--r-${c.rarity})`);
            preview.innerHTML = mediaHtml(c, true);
            const el = $("img, video", preview);
            if (el) el.addEventListener("error", () => onMediaError(el), { once: true });
            const r = $(".ow-preview-rarity");
            r.textContent = rarityName[c.rarity] || c.rarity;
            r.className = `ow-preview-rarity ow-rc-${c.rarity}`;
            $(".ow-preview-name").textContent = c.name;
            $(".ow-preview-source").textContent = c.source || "";
        }

        function show(t) {
            if (type !== t) {
                type = t;
                rarity = "";
                search.value = "";
                selected = null;
                const present = new Set((data.cosmetics[t] || []).map((c) => c.rarity));
                chips.innerHTML = `<button type="button" class="active" data-r="">Todas</button>` +
                    data.rarities.filter((r) => present.has(r.key))
                        .map((r) => `<button type="button" class="ow-rc-${r.key}" data-r="${r.key}">${esc(r.name)}</button>`).join("");
                $$("button", chips).forEach((b) => b.addEventListener("click", () => {
                    rarity = b.dataset.r;
                    $$("button", chips).forEach((x) => x.classList.toggle("active", x === b));
                    render();
                }));
            }
            render();
        }
        search.addEventListener("input", render);
        return { show };
    })();

    // ---------------------------------------------------------------- favorito
    function bindFav() {
        const btn = $("[data-action=fav]");
        if (!btn) return; // visitante sin permiso: sin favoritos
        const paint = () => {
            btn.classList.toggle("active", data.hero.fav);
            $(".ow-star", btn).textContent = data.hero.fav ? "★" : "☆";
            $(".ow-fav-label", btn).textContent = data.hero.fav ? "Favorito" : "Añadir a favoritos";
        };
        btn.addEventListener("click", async () => {
            data.hero.fav = !data.hero.fav;
            paint();
            try {
                const r = await fetch("/overwatch/api/favorito", {
                    method: "POST", credentials: "same-origin",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ hero_id: data.hero.id, fav: data.hero.fav }),
                });
                if (!r.ok) throw new Error(r.status);
            } catch {
                data.hero.fav = !data.hero.fav;
                paint();
            }
        });
        paint();
    }

    $$(".ow-tabs button").forEach((b) => b.addEventListener("click", () => openTab(b.dataset.tab)));
    buildAbilities();
    bindFav();
    openTab(FROM_SLUG[location.hash.slice(1)] || "summary", { push: false });
    window.addEventListener("hashchange", () => openTab(FROM_SLUG[location.hash.slice(1)] || "summary", { push: false }));
})();
