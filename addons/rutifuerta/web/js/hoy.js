/* Pestaña «Hoy»: plan del día y generador de rutinas. */
const Hoy = (() => {
  const state = Object.assign({ minutes: 30, groups: [], types: [], intensities: [], materials: [], cooldown: false, warmup: false, avoidDays: 14 },
                              store("ff-filters") || {});
  const save = () => store("ff-filters", state);
  let current = null, todayData = null;

  const minuteChips = {};
  const custom = document.createElement("input");

  // Marca los minutos elegidos: chip si es un valor típico, si no en el campo "otro".
  function selectMinutes(m) {
    state.minutes = m;
    Object.entries(minuteChips).forEach(([v, el]) => el.classList.toggle("on", +v === m));
    custom.value = MINUTES.includes(m) ? "" : m;
  }

  function setup() {
    const mRow = $("minutesRow");
    MINUTES.forEach(m => {
      const el = chip(m, false, () => {});
      el.onclick = () => { selectMinutes(m); save(); };
      minuteChips[m] = el; mRow.appendChild(el);
    });
    custom.type = "number"; custom.placeholder = "otro"; custom.min = 5; custom.max = 180;
    custom.oninput = () => { if (+custom.value) { state.minutes = +custom.value; Object.values(minuteChips).forEach(c => c.classList.remove("on")); save(); } };
    mRow.appendChild(custom);
    selectMinutes(DEFAULT_MIN);  // cada vez que entras, empieza en la duración por defecto

    const add = (rowId, entries, list, labelFn = k => k) =>
      Object.entries(entries).forEach(([k, n]) =>
        $(rowId).appendChild(chip(`${labelFn(k)} <small>${n}</small>`, list.includes(k), () => { toggle(list, k); save(); })));
    add("groupsRow", META.groups, state.groups);
    add("typesRow", META.types, state.types);
    add("intensityRow", META.intensities, state.intensities, k => INTENSITY_LABEL[k] || k);
    add("materialsRow", META.materials, state.materials);

    for (const [id, key] of [["warmupChip", "warmup"], ["cooldownChip", "cooldown"]]) {
      const el = $(id);
      el.classList.toggle("on", state[key]);
      el.onclick = () => { state[key] = !state[key]; el.classList.toggle("on", state[key]); save(); };
    }
    $("avoidDays").value = state.avoidDays;
    $("avoidDays").oninput = () => { state.avoidDays = +$("avoidDays").value || 0; save(); };
    $("saveDay").value = today();
    $("generateBtn").onclick = generate;
    $("regenBtn").onclick = generate;
    $("saveBtn").onclick = savePlan;
  }

  function params(extra = {}) {
    return { minutes: state.minutes, groups: state.groups, types: state.types, intensities: state.intensities,
             materials: state.materials.length ? state.materials : null,
             cooldown: state.cooldown, warmup: state.warmup, avoidDays: state.avoidDays, ...extra };
  }

  async function generate() { current = await api("/api/generate", params({ seed: Math.random() })); renderResult(); }

  async function swap(i) {
    const b = current.blocks[i];
    const res = await api("/api/generate", params({
      minutes: b.durationMinutes, tolerance: 0, cooldown: false, warmup: false, seed: Math.random(),
      exclude: current.blocks.map(x => x.id),
      ...(SIDE_TYPES.includes(b.trainingType) ? { types: [b.trainingType], groups: [], intensities: [] }
        : state.groups.length > 1 ? { groups: [b.group] } : {}),
    }));
    const alt = res.blocks.find(x => x.durationMinutes === b.durationMinutes) || res.blocks[0];
    if (alt) { current.blocks[i] = alt; current.total = current.blocks.reduce((s, x) => s + x.durationMinutes, 0); renderResult(); }
  }

  async function savePlan() {
    const day = $("saveDay").value || today();
    await api("/api/plan", { day, postIds: current.blocks.map(b => b.id), note: `Generada: ${current.total} min` });
    $("saveBtn").textContent = "¡Guardada!";
    setTimeout(() => $("saveBtn").textContent = "Guardar en el calendario", 1500);
    if (day === today()) loadToday();
  }

  function renderResult() {
    $("resultSection").hidden = false;
    $("totalMin").textContent = `${current.total} min`;
    $("poolInfo").textContent = ` · objetivo ${current.minutes} min · ${current.poolSize} rutinas posibles`;
    $("blocks").innerHTML = current.blocks.length
      ? current.blocks.map((b, i) => blockCard(b, i, { numbered: true, extra: `<button class="ghost" onclick="Hoy.swap(${i})">Cambiar</button>` })).join("")
      : `<p class="muted">No hay rutinas que encajen con esos filtros. Prueba a quitar alguno.</p>`;
  }

  async function loadToday() {
    const t = today();
    todayData = (await api(`/api/plans?from=${t}&to=${t}`))[t] || { blocks: [], done: [], extra: [] };
    const box = $("todayPlan"), d = todayData;
    const all = [...d.blocks, ...d.extra];
    if (d.status === "away" || d.status === "moved") {
      box.innerHTML = `<h2>Hoy · ${esc(fmtDay(t))}</h2><p class="muted">${d.status === "away" ? "🏖 " + esc(d.statusNote || "Hoy no estás") : "↪ " + esc(d.statusNote)}.
        Puedes cambiarlo en el <a href="#/calendario">calendario</a>.</p>`;
      return;
    }
    if (!all.length) {
      box.innerHTML = `<h2>Hoy · ${esc(fmtDay(t))}</h2>
        <p class="muted">No tienes nada planificado para hoy. Genera una rutina aquí abajo y guárdala,
        o haz el <a href="#/sigilo">Plan sigilo</a> (30 min en silencio).</p>`;
      return;
    }
    const mins = d.blocks.reduce((s, b) => s + b.durationMinutes, 0);
    const doneCount = d.blocks.filter(b => d.done.includes(b.id)).length;
    box.innerHTML = `
      <div class="spread">
        <h2>Hoy · ${esc(fmtDay(t))}</h2>
        <span class="badge">${doneCount}/${d.blocks.length} hechas · ${mins} min</span>
      </div>
      ${d.note ? `<p class="muted" style="margin-top:-6px">${esc(d.note)}${d.source === "bot" ? " · por tu entrenador" : ""}</p>` : ""}
      <div class="blocks">${all.map((b, i) => blockCard(b, i, {
        numbered: i < d.blocks.length, done: d.done.includes(b.id), onCheck: `Hoy.check(${b.id})`,
        note: i >= d.blocks.length ? "Hecha hoy fuera del plan" : "" })).join("")}</div>`;
  }

  async function check(id) { await setDone(id, today(), !todayData.done.includes(id)); loadToday(); }

  let ready = false;
  return {
    show() { if (!ready) { setup(); ready = true; } loadToday(); },
    setDefault(m) { if (ready) { selectMinutes(m); save(); } },
    swap, check,
  };
})();
