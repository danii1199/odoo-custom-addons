/* Solicitudes IG (/solicitudes-ig). Importa la lista, abre perfiles por packs en pestañas nuevas y guarda el estado.
   Las pestañas tienen que abrirse en el mismo clic (si no, el navegador las bloquea): por eso window.open va antes de
   cualquier await. Las que el navegador bloquee no se marcan como abiertas.
   «Abrir la siguiente» es un enlace de verdad a la siguiente cuenta del pack: con Ctrl+clic o la rueda el navegador
   la abre detrás (una página no puede abrir pestañas en segundo plano por su cuenta); un clic normal no abre nada,
   solo recuerda el gesto (petición del usuario: que nunca le lleve a la pestaña). Tras abrirla, el enlace pasa a
   la siguiente; con todo el pack abierto se bloquea hasta marcarlas como canceladas. */
(function () {
    "use strict";
    const $ = (s) => document.querySelector(s);
    const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
    const NOMBRES = { pendiente: "Pendiente", abierta: "Abierta", hecha: "Cancelada", resuelta: "Ya no sale" };
    let items = [];
    let hoy = 0;
    let pack = []; // ids del pack abierto
    let filtro = "todo";

    async function api(accion, body) {
        const r = await fetch(`/solicitudes-ig/api/${accion}`, body ? {
            method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
        } : { credentials: "same-origin" });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || `Error ${r.status}`);
        items = d.items;
        hoy = d.hoy;
        return d;
    }

    const byId = () => new Map(items.map((i) => [i.id, i]));
    const size = () => +$("#igSize").value;

    function fila(i) {
        const hecha = i.state === "hecha" || i.state === "resuelta";
        return `<li class="ig-row is-${i.state}" data-id="${i.id}">
            <a href="${esc(i.url)}" target="_blank" rel="noopener" data-open="${i.id}">@${esc(i.username)}</a>
            <span class="ig-state">${NOMBRES[i.state]}</span>
            ${hecha ? `<button type="button" class="ig-mini" data-set="pendiente">Deshacer</button>`
                    : `<button type="button" class="ig-mini ig-ok" data-set="hecha">✓ Cancelada</button>`}
        </li>`;
    }

    function render() {
        const n = (s) => items.filter((i) => i.state === s).length;
        const porHacer = n("pendiente") + n("abierta");
        const total = items.length;
        const hechas = n("hecha") + n("resuelta");
        $("#igStats").innerHTML = total ? `
            <div><strong>${porHacer}</strong><span>por hacer</span></div>
            <div><strong>${n("hecha")}</strong><span>canceladas</span></div>
            <div><strong>${n("resuelta")}</strong><span>ya no salen</span></div>
            <div><strong>${hoy}</strong><span>canceladas hoy</span></div>
            <div class="ig-bar" title="${hechas} de ${total}"><i style="width:${total ? (hechas * 100) / total : 0}%"></i></div>`
            : `<p class="ig-muted">Aún no hay nada: importa el archivo de Instagram.</p>`;
        const siguiente = items.filter((i) => i.state === "pendiente").length;
        $("#igOpen").textContent = siguiente ? `Abrir siguientes ${Math.min(size(), siguiente)}` : "No quedan pendientes";
        $("#igOpen").disabled = !siguiente;
        prepararUna();
        const m = byId();
        const enPack = pack.map((id) => m.get(id)).filter(Boolean);
        $("#igPack").innerHTML = enPack.map((i) => fila(i)).join("");
        $("#igAllDone").hidden = !enPack.some((i) => i.state === "abierta");
        const lista = items.filter((i) => filtro === "all" || (filtro === "todo" ? ["pendiente", "abierta"].includes(i.state) : i.state === filtro));
        $("#igCount").textContent = `(${lista.length})`;
        $("#igAll").innerHTML = lista.slice(0, 500).map((i) => fila(i)).join("") +
            (lista.length > 500 ? `<li class="ig-muted">… y ${lista.length - 500} más</li>` : "");
    }

    function aviso(sel, texto, error) {
        const el = $(sel);
        el.textContent = texto;
        el.classList.toggle("is-error", !!error);
    }

    async function marcar(ids, state) {
        try {
            await api("marcar", { ids, state });
        } catch (e) {
            aviso("#igPackMsg", e.message, true);
        }
        render();
    }

    function abrirPack() {
        const siguientes = items.filter((i) => i.state === "pendiente").slice(0, size());
        if (!siguientes.length) return;
        const abiertas = [];
        let bloqueadas = 0;
        pack = siguientes.map((i) => i.id); // también las bloqueadas: se quedan para abrirlas a mano
        for (const i of siguientes) {
            // Sin "noopener" en la llamada: con él devuelve null siempre y no se sabría si el navegador la bloqueó.
            // Se corta el enlace con esta página justo después (lo mismo que hace noopener).
            const w = window.open(i.url, "_blank");
            if (w) {
                try { w.opener = null; } catch { /* nada */ }
                abiertas.push(i.id);
            } else bloqueadas++;
        }
        if (bloqueadas) aviso("#igPackMsg", `El navegador ha bloqueado ${bloqueadas} de ${siguientes.length} pestañas: permite las ventanas emergentes de este sitio (icono en la barra de direcciones) y pulsa otra vez. Mientras, las que faltan están abajo: púlsalas una a una o usa «Abrir la siguiente».`, true);
        else aviso("#igPackMsg", `Abiertas ${abiertas.length} pestañas. Cuando las canceles, pulsa «✓ Todas las del pack, canceladas».`);
        if (abiertas.length) marcar(abiertas, "abierta");
    }

    /** Qué abre ahora «Abrir la siguiente»: la siguiente pendiente del pack; si el pack ya está todo abierto, nada
     *  (hasta cancelarlas); si no hay pack o ya está resuelto, la más antigua pendiente, que empieza uno nuevo. */
    function siguienteDelPack() {
        const m = byId();
        const enPack = pack.map((id) => m.get(id)).filter(Boolean);
        const pendiente = enPack.find((i) => i.state === "pendiente");
        if (pendiente) return { item: pendiente, hechas: enPack.filter((i) => i.state !== "pendiente").length, total: enPack.length };
        if (enPack.some((i) => i.state === "abierta")) return { lleno: true, total: enPack.length };
        const pendientes = items.filter((i) => i.state === "pendiente");
        return pendientes.length ? { item: pendientes[0], hechas: 0, total: Math.min(size(), pendientes.length), nuevo: true } : {};
    }

    function prepararUna() {
        const a = $("#igOpenOne");
        const s = siguienteDelPack();
        a.classList.toggle("disabled", !s.item);
        if (s.item) {
            a.href = s.item.url;
            a.dataset.id = s.item.id;
            a.removeAttribute("aria-disabled");
            a.textContent = `Abrir la siguiente (${s.hechas + 1}/${s.total}) · @${s.item.username}`;
        } else {
            a.removeAttribute("href");
            delete a.dataset.id;
            a.setAttribute("aria-disabled", "true");
            a.textContent = s.lleno ? `Pack abierto (${s.total}/${s.total}): cancélalas y pulsa ✓` : "No quedan pendientes";
        }
    }

    function alAbrirUna(ev) {
        const id = +ev.currentTarget.dataset.id;
        if (!id) return ev.preventDefault();
        // Un clic normal llevaría a la pestaña nueva (y no hay forma de evitarlo desde la página): no abre nada y
        // recuerda el gesto. Ctrl/⌘+clic y la rueda sí la abren detrás.
        if (ev.type === "click" && !ev.ctrlKey && !ev.metaKey) {
            ev.preventDefault();
            return aviso("#igPackMsg", "Para abrirla detrás, sin salir de aquí: Ctrl+clic (⌘+clic en Mac) o clic con la rueda del ratón.", true);
        }
        // Pack nuevo: las siguientes N pendientes, empezando por esta
        if (!pack.includes(id)) pack = items.filter((i) => i.state === "pendiente").slice(0, size()).map((i) => i.id);
        // Después del clic: el navegador ya ha abierto este enlace; ahora sí se puede cambiar a la siguiente
        setTimeout(() => {
            const i = byId().get(id);
            if (i) i.state = "abierta"; // al momento, sin esperar al servidor: así se puede pulsar seguido
            render();
            marcar([id], "abierta");
        }, 0);
    }

    async function importar() {
        const file = $("#igFile").files[0];
        const texto = $("#igText").value.trim();
        if (!file && !texto) return aviso("#igImportMsg", "Elige el archivo o pega los usuarios", true);
        $("#igImport").disabled = true;
        aviso("#igImportMsg", "Importando…");
        try {
            const contenido = file ? await file.text() : texto;
            const { stats } = await api("importar", { contenido, completa: $("#igCompleta").checked });
            if (!stats.leidas) aviso("#igImportMsg", "No he encontrado ninguna cuenta en ese archivo. ¿Es pending_follow_requests?", true);
            else aviso("#igImportMsg", `Leídas ${stats.leidas}: ${stats.nuevas} nuevas, ${stats.ya_estaban} ya estaban` +
                (stats.vuelven ? `, ${stats.vuelven} vuelven a pendiente (siguen sin cancelar)` : "") +
                (stats.resueltas ? `, ${stats.resueltas} ya no salen` : "") + ".");
            $("#igFile").value = "";
            $("#igText").value = "";
            pack = [];
        } catch (e) {
            aviso("#igImportMsg", e.message, true);
        }
        $("#igImport").disabled = false;
        render();
    }

    document.addEventListener("click", (ev) => {
        const b = ev.target.closest("[data-set]");
        if (b) return marcar([+b.closest("[data-id]").dataset.id], b.dataset.set);
        const a = ev.target.closest("[data-open]");
        if (a) {
            const i = byId().get(+a.dataset.open);
            if (i && i.state === "pendiente") marcar([i.id], "abierta");
        }
        const f = ev.target.closest("#igFilter button");
        if (f) {
            filtro = f.dataset.f;
            document.querySelectorAll("#igFilter button").forEach((x) => x.classList.toggle("active", x === f));
            render();
        }
    });
    $("#igOpen").addEventListener("click", abrirPack);
    $("#igOpenOne").addEventListener("click", alAbrirUna);
    $("#igOpenOne").addEventListener("auxclick", (ev) => ev.button === 1 && alAbrirUna(ev)); // clic con la rueda
    // Los nombres de la lista también se pueden abrir con la rueda
    document.addEventListener("auxclick", (ev) => {
        const a = ev.button === 1 && ev.target.closest("[data-open]");
        const i = a && byId().get(+a.dataset.open);
        if (i && i.state === "pendiente") marcar([i.id], "abierta");
    });
    $("#igAllDone").addEventListener("click", () => {
        const m = byId();
        marcar(pack.filter((id) => m.get(id)?.state === "abierta"), "hecha");
    });
    $("#igImport").addEventListener("click", importar);
    $("#igSize").addEventListener("change", render);

    api("estado").then(render).catch((e) => aviso("#igImportMsg", e.message, true));
})();
