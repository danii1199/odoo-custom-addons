/* Pestaña «Rutinas»: buscador del catálogo. */
const Cat = (() => {
  const f = { groups: [], types: [], intensities: [] };
  let items = [], total = 0, doneToday = new Set(), timer = null, ready = false;

  function setup() {
    Object.entries(META.groups).forEach(([k, n]) =>
      $("cGroupsRow").appendChild(chip(`${k} <small>${n}</small>`, false, () => { toggle(f.groups, k); search(); })));
    Object.entries(META.types).forEach(([k, n]) =>
      $("cTypesRow").appendChild(chip(`${k} <small>${n}</small>`, false, () => { toggle(f.types, k); search(); })));
    Object.entries(META.intensities).forEach(([k, n]) =>
      $("cIntensityRow").appendChild(chip(`${INTENSITY_LABEL[k] || k} <small>${n}</small>`, false, () => { toggle(f.intensities, k); search(); })));
    $("q").oninput = () => { clearTimeout(timer); timer = setTimeout(search, 250); };
    $("maxMin").onchange = search;
    $("moreBtn").onclick = () => search(true);
  }

  async function search(more = false) {
    const qs = new URLSearchParams({ q: $("q").value, groups: f.groups.join(","), types: f.types.join(","), intensities: f.intensities.join(","),
                                     max: $("maxMin").value, offset: more ? items.length : 0, limit: 30 });
    const res = await api("/api/routines?" + qs);
    items = more ? items.concat(res.items) : res.items;
    total = res.total;
    render();
  }

  function render() {
    $("catCount").textContent = `${total} rutinas`;
    $("catalog").innerHTML = items.map((b, i) => blockCard(b, i, {
      done: doneToday.has(b.id), onCheck: `Cat.check(${b.id})`,
      extra: `<span class="addform"><input type="date" id="add-${b.id}" value="${today()}">
              <button class="ghost" onclick="Cat.add(${b.id})" id="addb-${b.id}">＋ Añadir</button></span>` })).join("");
    $("moreBtn").hidden = items.length >= total;
  }

  async function loadDone() {
    const t = today();
    doneToday = new Set(((await api(`/api/plans?from=${t}&to=${t}`))[t] || {}).done || []);
  }

  async function check(id) { await setDone(id, today(), !doneToday.has(id)); await loadDone(); render(); }

  async function add(id) {
    const day = $("add-" + id).value || today();
    const p = (await api(`/api/plans?from=${day}&to=${day}`))[day] || {};
    const ids = (p.blocks || []).map(b => b.id);
    if (!ids.includes(id)) ids.push(id);
    await api("/api/plan", { day, postIds: ids, note: p.note || null, source: p.source || "manual" });
    const btn = $("addb-" + id); btn.textContent = "✓ Añadida"; btn.disabled = true;
  }

  return {
    async show() { if (!ready) { setup(); ready = true; } await loadDone(); search(); },
    check, add,
  };
})();
