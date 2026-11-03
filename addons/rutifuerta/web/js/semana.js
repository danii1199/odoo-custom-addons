/* Pestaña «Plan semanal»: semanas tipo (recomendadas y guardadas) por días y minutos, y la semana tipo en uso. */
const Week = (() => {
  const DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
  const SHORT = ["L", "M", "X", "J", "V", "S", "D"];
  const WEEK_GROUPS = ["Pierna y glúteo", "Torso", "Core", "Fullbody", "Cardio", "Cuerpo-Mente"];
  const TIMES = [30, 45, 50, 60];  // duraciones con semana recomendada
  const sameWeek = (a, b) => [0, 1, 2, 3, 4, 5, 6].every(i => JSON.stringify(a[i] || []) === JSON.stringify(b[i] || []));
  const summary = w => [0, 1, 2, 3, 4, 5, 6].filter(i => (w[i] || []).length)
    .map(i => `${SHORT[i]} ${w[i].join(" + ")}`).join(" · ") || "Todo descanso";
  const daysOf = w => [0, 1, 2, 3, 4, 5, 6].filter(i => (w[i] || []).length).length;
  const uniq = list => [...new Set(list)].sort((a, b) => a - b);

  let s = null;        // ajustes (s.week = semana tipo en uso, s.dailyMinutes = minutos)
  let weeks = [];      // [{id, name, week, days, minutes, recommended, description}]
  let current = null;  // id de la semana que se está usando/editando
  let world = 3;       // «mundo» que se ve: semanas de 3 días, de 4, de 5…
  let time = 45;       // y de cuántos minutos

  function setWorld(n) { world = n; store("fuertaWorld", n); renderWeeks(); }
  function setTime(m) { time = m; store("fuertaTime", m); renderWeeks(); }

  /* Al elegir días o tiempo en los filtros, la semana tipo se rellena con la recomendada de esa combinación. */
  async function pick(days, minutes) {
    setWorld(days);
    setTime(minutes);
    const rec = weeks.find(w => w.recommended && w.days === days && w.minutes === minutes);
    if (rec) await useWeek(rec.id);
    else msg(`No hay semana recomendada de ${days} días y ${minutes} min: prepárala abajo y guárdala como tuya.`);
  }

  function filterChips(id, values, active, label, count, fn) {
    $(id).innerHTML = `<label class="title">${id === "wkWorlds" ? "Días" : "Tiempo"}</label>` + values.map(v =>
      `<span class="chip${v === active ? " on" : ""}" onclick="Week.${fn}(${v})">${label(v)} <small>${count(v)}</small></span>`).join("");
  }

  function renderWeeks() {
    filterChips("wkWorlds", uniq([3, 4, 5, world, ...weeks.map(w => w.days)]), world, n => `${n} días`,
                n => weeks.filter(w => w.days === n).length, "pickDays");
    filterChips("wkTimes", uniq([...TIMES, time, ...weeks.map(w => w.minutes)]), time, m => `${m} min`,
                m => weeks.filter(w => w.days === world && w.minutes === m).length, "pickTime");
    $("templates").innerHTML = weeks.filter(w => w.days === world && w.minutes === time).map(w => {
      const changed = w.id === current && (!sameWeek(s.week, w.week) || w.minutes !== DEFAULT_MIN);
      return `
      <div class="tpl${w.recommended ? " rec" : ""}${w.id === current ? " on" : ""}" onclick="Week.useWeek(${w.id})">
        ${w.recommended ? '<span class="tpl-badge">★ Recomendada</span>' : ""}
        <strong>${esc(w.name)}${changed ? ' <small class="muted">(cambios sin guardar)</small>' : ""}</strong>
        <span class="muted">${esc(summary(w.week))}</span>
        ${w.description ? `<small class="muted">${esc(w.description)}</small>` : ""}
        ${w.recommended ? "" : `<button class="tpl-del" title="Borrar esta semana" onclick="event.stopPropagation(); Week.removeWeek(${w.id})">✕</button>`}
      </div>`;
    }).join("") || `<p class="muted">No hay semanas de ${world} días y ${time} min: prepárala abajo y guárdala.</p>`;
    const cur = weeks.find(w => w.id === current);
    const own = cur && !cur.recommended;
    const n = daysOf(s.week);
    $("wkUpdate").hidden = !own;
    if (own) {
      const moves = n !== cur.days || DEFAULT_MIN !== cur.minutes;
      $("wkUpdate").textContent = `Guardar cambios en «${cur.name}»${moves ? ` (pasa a ${n} días · ${DEFAULT_MIN} min)` : ""}`;
    }
    $("wkNew").textContent = `Guardar como semana nueva (${n} días · ${DEFAULT_MIN} min)`;
  }

  /* Los minutos de la semana pasan a ser la duración por defecto (la de la cabecera). */
  function setMinutes(m) {
    DEFAULT_MIN = m;
    $("defMin").value = m;
    Hoy.setDefault(m);
    Cal.refreshDefault();
  }

  async function useWeek(id) {
    const w = weeks.find(x => x.id === id);
    current = id;
    world = w.days;
    time = w.minutes;
    s.week = JSON.parse(JSON.stringify(w.week));
    setMinutes(w.minutes);
    $("wkName").value = w.recommended ? "" : w.name;
    await save(true);
    msg(`Semana tipo rellenada con «${esc(w.name)}» (${w.minutes} min por sesión) y guardada. Los días ya planificados
         no cambian: usa «Generar…» con «sustituir» si quieres rehacerlos.`);
  }

  async function saveWeek(asNew) {
    const name = $("wkName").value.trim();
    if (!name) { msg("Ponle un nombre a la semana."); $("wkName").focus(); return; }
    const r = await api("/api/weeks", { id: asNew ? null : current, name, week: s.week, minutes: DEFAULT_MIN });
    if (r.error) { msg(esc(r.error)); return; }
    weeks = r.weeks;
    current = r.id;
    const w = weeks.find(x => x.id === r.id);
    setWorld(w.days);
    setTime(w.minutes);
    await save(true);  // la que acabas de guardar pasa a ser la semana tipo en uso
    msg(`Semana «${esc(name)}» guardada en «${w.days} días · ${w.minutes} min» y en uso.`);
  }

  async function removeWeek(id) {
    const w = weeks.find(x => x.id === id);
    if (!confirm(`¿Borrar la semana «${w.name}»? Tu semana tipo en uso no cambia.`)) return;
    weeks = await api("/api/weeks/remove", { id });
    if (current === id) current = null;
    renderWeeks();
  }

  function render() {
    renderWeeks();
    $("weekGrid").innerHTML = "";
    DAYS.forEach((name, i) => {
      // Siempre la lista de los ajustes actuales: save() sustituye `s` por la respuesta del servidor.
      const sel = () => s.week[i] || (s.week[i] = []);
      const row = document.createElement("div");
      row.className = "wday";
      row.innerHTML = `<div class="dn">${name}</div><div class="chips"></div>`;
      const chips = row.querySelector(".chips");
      const rest = chip("Descanso", !sel().length, () => {});
      rest.classList.add("rest");
      const groupChips = WEEK_GROUPS.map(g => chip(g, sel().includes(g), () => {
        toggle(sel(), g); rest.classList.toggle("on", !sel().length); renderWeeks();
      }));
      rest.onclick = () => { sel().length = 0; groupChips.forEach(c => c.classList.remove("on")); rest.classList.add("on"); renderWeeks(); };
      [rest, ...groupChips].forEach(c => chips.appendChild(c));
      $("weekGrid").appendChild(row);
    });
    const mats = $("wMaterials");
    mats.querySelectorAll(".chip").forEach(c => c.remove());
    Object.keys(META.materials).forEach(m => mats.appendChild(chip(m, s.materials.includes(m), () => toggle(s.materials, m))));
    for (const [id, key] of [["wWarmup", "warmup"], ["wCooldown", "cooldown"], ["wAuto", "autoPlan"]]) {
      $(id).classList.toggle("on", !!s[key]);
      $(id).onclick = () => { s[key] = !s[key]; $(id).classList.toggle("on", s[key]); };
    }
  }

  async function save(quiet) {
    s.dailyMinutes = DEFAULT_MIN;
    s = await api("/api/settings", s);
    render();
    if (!quiet) msg("Guardado ✓");
  }

  function msg(text) { $("wMsg").innerHTML = text; }

  async function fill(offsetWeeks) {
    await save(true);
    const d = new Date(); d.setDate(d.getDate() + 7 * offsetWeeks);
    const created = await api("/api/plan/week", { start: iso(d), overwrite: $("wOverwrite").checked });
    const days = Object.keys(created);
    msg(days.length
      ? `Planificados ${days.length} días: ${days.map(k => `<a href="#/calendario" onclick="Cal.goTo('${k}')">${esc(fmtDay(k))}</a>`).join(", ")}.`
      : "No había días que rellenar (ya estaban planificados o ya han pasado). Marca «sustituir» para rehacerlos.");
  }

  $("wSave").onclick = () => save();
  $("wThis").onclick = () => fill(0);
  $("wNext").onclick = () => fill(1);
  $("wkUpdate").onclick = () => saveWeek(false);
  $("wkNew").onclick = () => saveWeek(true);

  return {
    async show() {
      [s, weeks] = await Promise.all([api("/api/settings"), api("/api/weeks")]);
      // La semana en uso: primero una propia con los mismos grupos y minutos, luego una recomendada.
      const same = weeks.filter(w => sameWeek(s.week, w.week));
      const match = same.find(w => !w.recommended && w.minutes === s.dailyMinutes)
        || same.find(w => w.minutes === s.dailyMinutes) || same[0];
      current = match ? match.id : null;
      world = match ? match.days : (store("fuertaWorld") || daysOf(s.week) || 3);
      time = match ? match.minutes : (store("fuertaTime") || s.dailyMinutes || 45);
      $("wkName").value = match && !match.recommended ? match.name : "";
      render();
      msg("");
    },
    useWeek, removeWeek,
    pickDays: n => pick(n, time),
    pickTime: m => pick(world, m),
  };
})();
