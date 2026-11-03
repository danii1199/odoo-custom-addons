/* Utilidades compartidas: formato de fechas, llamadas a la API, chips y la tarjeta de rutina. */
const INTENSITY_LABEL = { low: "Baja", medium: "Media", high: "Alta" };
const SIDE_TYPES = ["Calentamiento", "Cuerpo-Mente"];
const MINUTES = [10, 15, 20, 30, 40, 45, 60];
const MONTHS = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const iso = d => d.toLocaleDateString("sv");  // YYYY-MM-DD en hora local
const today = () => iso(new Date());
const fmtDay = s => { const d = new Date(s + "T12:00"); return d.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" }); };

/* Llama a /rutifuerta/api/<path>. Si la sesión de Odoo ha caducado, vuelve al login. */
async function api(path, body) {
  const r = await fetch("/rutifuerta" + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!(r.headers.get("Content-Type") || "").includes("json")) {
    location.href = "/web/login?redirect=" + encodeURIComponent("/rutifuerta" + location.hash);
    return new Promise(() => {});  // la página se va: que nadie siga con datos vacíos
  }
  return r.json();
}
function store(key, val) {
  try { if (val === undefined) return JSON.parse(localStorage.getItem(key) || "null"); localStorage.setItem(key, JSON.stringify(val)); } catch { return null; }
}
function chip(label, on, onClick) {
  const el = document.createElement("span");
  el.className = "chip" + (on ? " on" : "");
  el.innerHTML = label;
  el.onclick = () => { el.classList.toggle("on"); onClick(el.classList.contains("on")); };
  return el;
}
function toggle(list, v) { const i = list.indexOf(v); i >= 0 ? list.splice(i, 1) : list.push(v); }

let META = null;
let DEFAULT_MIN = 30;  // duración por defecto (ajustes del servidor), editable en la cabecera

/* Tarjeta de rutina reutilizable. opts: {done, onCheck, extra (html de botones), numbered} */
function blockCard(b, i, opts = {}) {
  const tags = [b.group, b.trainingType, ...(b.materials || [])].filter(Boolean);
  return `
  <div class="block${opts.done ? " done" : ""}">
    <img src="${esc(b.previewImage)}" alt="" loading="lazy">
    <div class="info">
      <div class="head">
        <div class="t">${opts.numbered ? (i + 1) + ". " : ""}${esc(b.title)}</div>
        ${opts.onCheck ? `<button class="check${opts.done ? " on" : ""}" onclick="${opts.onCheck}" title="${opts.done ? "Desmarcar" : "Marcar como hecha"}" aria-pressed="${!!opts.done}">✓</button>` : ""}
      </div>
      <div class="m">${b.durationMinutes} min${b.format ? " · " + esc(b.format) : ""} · ${esc(INTENSITY_LABEL[b.intensity] || b.intensity || "")}${b.trainers?.length ? " · " + esc(b.trainers.join(", ")) : ""}</div>
      ${opts.note ? `<div class="m">${opts.note}</div>` : ""}
      <div>${tags.map(t => `<span class="tag">${esc(t)}</span>`).join("")}</div>
      <div class="actions">
        <a class="open" href="${esc(b.url)}" target="_blank" rel="noopener">▶ Abrir en FuertaFit</a>
        ${opts.extra || ""}
      </div>
    </div>
  </div>`;
}

/* Marcar / desmarcar una rutina como hecha un día concreto. */
async function setDone(id, day, done) {
  await api(done ? "/api/history" : "/api/history/remove", { postIds: [id], doneOn: day });
}
