/* Pestaña «Calendario»: vista mensual, detalle del día, mover/saltar y vacaciones. */
// Clase CSS por grupo muscular (color del punto en el listado de cada día).
const GROUP_CLS = { "Pierna y glúteo": "pierna", "Torso": "torso", "Core": "core", "Fullbody": "full",
                    "Cardio": "cardio", "Cuerpo-Mente": "mente", "Calentamiento": "calen" };
const Cal = (() => {
  let month = new Date(); month.setDate(1);
  let selected = today(), data = {};

  async function load() {
    const first = new Date(month), start = new Date(first);
    start.setDate(1 - ((first.getDay() + 6) % 7));  // lunes de la primera semana
    const end = new Date(start); end.setDate(start.getDate() + 41);
    data = await api(`/api/plans?from=${iso(start)}&to=${iso(end)}`);
    $("monthTitle").textContent = `${MONTHS[month.getMonth()]} ${month.getFullYear()}`;
    const cells = ["L", "M", "X", "J", "V", "S", "D"].map(d => `<div class="dow">${d}</div>`);
    for (let i = 0; i < 42; i++) {
      const d = new Date(start); d.setDate(start.getDate() + i);
      const key = iso(d), p = data[key];
      const planned = p?.blocks || [], done = p?.done || [];
      const doneInPlan = planned.filter(b => done.includes(b.id)).length;
      const mins = planned.reduce((s, b) => s + b.durationMinutes, 0);
      let cls = "day";
      if (d.getMonth() !== month.getMonth()) cls += " out";
      if (key === today()) cls += " today";
      if (key === selected) cls += " sel";
      if (planned.length && doneInPlan === planned.length) cls += " full";
      else if (done.length) cls += " partial";
      if (p?.status) cls += " " + p.status;
      let info = "";
      const ST = { away: "🏖 " + (p?.statusNote || "Fuera"), skipped: "⏭ Saltado", moved: "↪ Movida" };
      if (p?.status) info += `<span class="i st">${esc(ST[p.status])}</span>`;
      if (planned.length) info += `<span class="i">${mins} min${done.length ? ` · <b class="ok">✓ ${doneInPlan}/${planned.length}</b>` : ""}</span>`;
      else if (done.length) info += `<span class="i ok">✓ ${done.length} hecha${done.length > 1 ? "s" : ""}</span>`;
      // Listado de rutinas del día (las hechas fuera del plan también).
      const items = [...planned, ...(p?.extra || [])];
      if (items.length) info += `<ul class="rl">${items.map(b => {
        const ok = done.includes(b.id);
        return `<li class="${ok ? "ok" : ""} g-${GROUP_CLS[b.group] || "x"}" title="${esc(b.title)} · ${b.durationMinutes} min">`
          + `<span class="dot"></span>${ok ? "✓ " : ""}${b.durationMinutes}' ${esc(b.title.trim())}</li>`;
      }).join("")}</ul>`;
      const drag = planned.length ? ` draggable="true" title="Arrastra para mover su rutina a otro día"` : "";
      cells.push(`<button class="${cls}" data-day="${key}"${drag} onclick="Cal.select('${key}')"><span class="n">${d.getDate()}</span>${info}</button>`);
    }
    $("cal").innerHTML = cells.join("");
    renderDay();
  }

  function renderDay() {
    const p = data[selected] || { blocks: [], done: [], extra: [] };
    const all = [...p.blocks, ...p.extra];
    const mins = p.blocks.reduce((s, b) => s + b.durationMinutes, 0);
    const BANNER = { away: `🏖 ${esc(p.statusNote || "Fuera")}: este día no estás`,
                     skipped: "⏭ Día saltado: no cuenta como pendiente", moved: `↪ ${esc(p.statusNote || "Rutina movida")}` };
    const tomorrow = new Date(selected + "T12:00"); tomorrow.setDate(tomorrow.getDate() + 1);
    $("dayDetail").innerHTML = `
      <div class="spread">
        <h2 style="text-transform:capitalize">${esc(fmtDay(selected))}</h2>
      </div>
      ${p.status ? `<div class="banner"><span>${BANNER[p.status]}</span>
          <button class="ghost" onclick="Cal.clearStatus()">${p.status === "away" ? "Quitar ausencia de este día" : "Deshacer"}</button></div>` : ""}
      <div class="dayactions">
        <span class="daymin addform"><input type="number" id="dayMin" min="5" max="180" step="5" value="${DEFAULT_MIN}"
              title="Minutos solo para este día">min
          <button class="ghost" onclick="Cal.generate()">${p.blocks.length ? "Regenerar" : "Generar rutina"}</button></span>
        ${p.blocks.length ? `
        <span class="addform"><input type="date" id="moveTo" value="${iso(tomorrow)}">
          <button class="ghost" onclick="Cal.move()" title="Si ese día ya tiene rutina, se intercambian">Mover</button></span>
        ${p.status !== "skipped" ? `<button class="ghost" onclick="Cal.skip()">Saltar este día</button>` : ""}
        <button class="ghost danger" onclick="Cal.remove()">Borrar</button>` : ""}
        <button class="ghost" onclick="Cal.fillWeek()">Rellenar su semana</button>
        ${META.bot ? `<button class="ghost" onclick="Cal.askBot()">Pedir al entrenador</button>` : ""}
      </div>
      ${p.note ? `<p class="muted" style="margin-top:-6px">${esc(p.note)}${p.source === "bot" ? " · por tu entrenador" : p.source === "auto" ? " · automática" : ""}</p>` : ""}
      ${p.blocks.length ? `<p class="muted">${mins} min planificados</p>` : ""}
      ${all.length ? `<div class="blocks">${all.map((b, i) => blockCard(b, i, {
          numbered: i < p.blocks.length, done: p.done.includes(b.id), onCheck: `Cal.check(${b.id})`,
          note: i >= p.blocks.length ? "Hecha fuera del plan" : "" })).join("")}</div>`
        : `<p class="muted">Nada planificado ni hecho este día.</p>`}`;
  }

  async function check(id) {
    const p = data[selected] || { done: [] };
    await setDone(id, selected, !p.done.includes(id));
    load();
  }

  async function generate() {
    const res = await api("/api/plan/auto", { day: selected, minutes: +$("dayMin").value || DEFAULT_MIN });
    if (!res.postIds.length) {
      $("dayDetail").insertAdjacentHTML("beforeend", `<p class="muted">No hay rutinas que encajen con tu plan semanal.</p>`);
      return;
    }
    load();
  }

  async function fillWeek() { await api("/api/plan/week", { start: selected }); load(); }

  async function remove() { await api("/api/plan/remove", { day: selected }); load(); }

  async function move() {
    const to = $("moveTo").value;
    if (!to || to === selected) return;
    const res = await api("/api/day/move", { from: selected, to });
    if (res.error) { $("dayDetail").insertAdjacentHTML("beforeend", `<p class="muted">${esc(res.error)}</p>`); return; }
    // Te lleva al día de destino (cambiando de mes si hace falta).
    selected = to;
    const d = new Date(to + "T12:00");
    month = new Date(d.getFullYear(), d.getMonth(), 1);
    await load();
  }

  async function skip() { await api("/api/day/skip", { day: selected }); load(); }

  async function clearStatus() { await api("/api/day/clear", { start: selected }); load(); loadAway(); }

  let awayRanges = [];

  async function loadAway() {
    awayRanges = await api("/api/away");
    $("awayList").innerHTML = awayRanges.map((r, i) => `<div id="away-${i}">
        <span>🏖 <strong>${esc(r.note)}</strong> · ${esc(fmtDay(r.start))}${r.end !== r.start ? " → " + esc(fmtDay(r.end)) : ""}</span>
        <span class="actions">
          <button class="ghost" onclick="Cal.editAway(${i})">Editar</button>
          <button class="ghost danger" onclick="Cal.removeAway('${r.start}','${r.end}')">Quitar</button>
        </span></div>`).join("");
  }

  // Convierte la fila de una ausencia en un formulario para cambiar fechas y motivo.
  function editAway(i) {
    const r = awayRanges[i], row = $("away-" + i);
    row.classList.add("editing");
    row.innerHTML = `
      <span class="addform" style="flex-wrap:wrap">
        Del <input type="date" id="ea-from" value="${r.start}"> al <input type="date" id="ea-to" value="${r.end}">
        <input type="text" id="ea-note" value="${esc(r.note)}" placeholder="Motivo" style="min-width:140px">
        <label class="muted"><input type="checkbox" id="ea-remove" checked> quitar rutinas de los días nuevos</label>
      </span>
      <span class="actions">
        <button class="main" onclick="Cal.saveAway(${i})">Guardar</button>
        <button class="ghost" onclick="Cal.cancelAway()">Cancelar</button>
      </span>`;
    $("ea-from").onchange = () => { if ($("ea-to").value < $("ea-from").value) $("ea-to").value = $("ea-from").value; };
  }

  async function saveAway(i) {
    const r = awayRanges[i];
    let start = $("ea-from").value, end = $("ea-to").value || start;
    if (!start) return;
    if (end < start) [start, end] = [end, start];
    await api("/api/away/update", { oldStart: r.start, oldEnd: r.end, start, end,
      note: $("ea-note").value.trim() || "Fuera", removePlans: $("ea-remove").checked });
    await loadAway(); load();
  }

  async function markAway() {
    const start = $("awayFrom").value, end = $("awayTo").value || start;
    if (!start) return;
    await api("/api/away", { start, end, note: $("awayNote").value.trim() || "Fuera", removePlans: $("awayRemove").checked });
    $("awayNote").value = "";
    loadAway(); load();
  }

  $("awayFrom").value = today();
  $("awayFrom").onchange = () => { if (!$("awayTo").value || $("awayTo").value < $("awayFrom").value) $("awayTo").value = $("awayFrom").value; };
  $("awayBtn").onclick = markAway;

  function askBot() { Bot.prefill(`Planifícame el ${fmtDay(selected)} (${selected}). `); location.hash = "#/entrenador"; }

  // Arrastrar un día con rutina sobre otro la mueve (o las intercambia si el destino ya tiene).
  let dragFrom = null;
  const cellOf = e => e.target.closest && e.target.closest(".day[data-day]");
  $("cal").addEventListener("dragstart", e => {
    const c = cellOf(e);
    if (!c) return;
    dragFrom = c.dataset.day;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", dragFrom);
    c.classList.add("dragging");
  });
  $("cal").addEventListener("dragover", e => {
    const c = cellOf(e);
    if (!dragFrom || !c || c.dataset.day === dragFrom) return;
    e.preventDefault();  // permite soltar aquí
    document.querySelectorAll(".day.drop").forEach(x => x !== c && x.classList.remove("drop"));
    c.classList.add("drop");
  });
  $("cal").addEventListener("dragleave", e => { const c = cellOf(e); if (c && !c.contains(e.relatedTarget)) c.classList.remove("drop"); });
  $("cal").addEventListener("dragend", () => {
    dragFrom = null;
    document.querySelectorAll(".day.drop, .day.dragging").forEach(x => x.classList.remove("drop", "dragging"));
  });
  $("cal").addEventListener("drop", async e => {
    e.preventDefault();
    const c = cellOf(e), from = dragFrom;
    if (!c || !from || c.dataset.day === from) return;
    const to = c.dataset.day, swapped = !!data[to]?.blocks?.length;
    const res = await api("/api/day/move", { from, to });
    if (res.error) return;
    selected = to;
    await load();
    $("dayDetail").insertAdjacentHTML("afterbegin", `<p class="muted" style="margin-top:0">${swapped
      ? `Intercambiadas las rutinas del ${esc(fmtDay(from))} y el ${esc(fmtDay(to))}.`
      : `Rutina movida desde el ${esc(fmtDay(from))}.`}</p>`);
  });

  $("prevMonth").onclick = () => { month.setMonth(month.getMonth() - 1); load(); };
  $("nextMonth").onclick = () => { month.setMonth(month.getMonth() + 1); load(); };

  return {
    show() { load(); loadAway(); },
    select(day) { selected = day; const d = new Date(day + "T12:00");
      if (d.getMonth() !== month.getMonth()) { month = new Date(d.getFullYear(), d.getMonth(), 1); load(); } else load(); },
    goTo(day) { selected = day; const d = new Date(day + "T12:00"); month = new Date(d.getFullYear(), d.getMonth(), 1); },
    check, generate, fillWeek, remove, askBot, move, skip, clearStatus,
    async removeAway(start, end) { await api("/api/day/clear", { start, end }); loadAway(); load(); },
    editAway, saveAway, cancelAway: loadAway,
    refreshDefault() { const el = $("dayMin"); if (el) el.value = DEFAULT_MIN; },
  };
})();
