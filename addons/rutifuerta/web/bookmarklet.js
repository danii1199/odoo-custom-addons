/* Marcador "Actualizar Fuerta": se ejecuta en webapp.fuertafit.com con tu sesión.
   Abre /rutifuerta/sync de tu web (Odoo, con tu sesión), pregunta qué rutinas tienes ya y le pasa solo las nuevas.
   __APP__ se sustituye por la dirección de tu web al crear el marcador. */
(async () => {
  const APP = "__APP__";
  if (location.hostname !== "webapp.fuertafit.com") {
    alert("Abre webapp.fuertafit.com con tu sesión iniciada y pulsa el marcador allí.");
    return;
  }
  const key = Object.keys(sessionStorage).find(k => k.startsWith("oidc.user:"));
  const user = key && JSON.parse(sessionStorage.getItem(key));
  if (!user || !user.access_token) {
    alert("No encuentro tu sesión de FuertaFit en esta pestaña. Inicia sesión y vuelve a pulsar el marcador.");
    return;
  }
  const headers = { Authorization: "Bearer " + user.access_token };
  const API = "https://api.fuertafit.com/api/v2/dona/";
  const ready = new Promise(resolve => {
    const onMsg = e => {
      if (e.origin === APP && e.data && e.data.type === "ready") {
        removeEventListener("message", onMsg);
        resolve(new Set(e.data.known));
      }
    };
    addEventListener("message", onMsg);
  });
  const win = window.open(APP + "/rutifuerta/sync", "ffsync", "width=480,height=380");
  if (!win) { alert("Permite las ventanas emergentes en esta página y vuelve a pulsar el marcador."); return; }
  const send = m => win.postMessage(m, APP);
  const known = await ready;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const clean = s => (s || "").replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/\s+/g, " ").trim();

  const list = [];
  for (let p = 1; p < 300; p++) {
    send({ type: "status", text: `Leyendo el listado de FuertaFit… (página ${p})` });
    const res = await fetch(`${API}posts?IsVisible=true&PageNum=${p}&ResultsPerPage=100`, { headers });
    if (res.status === 401) { send({ type: "error", text: "Tu sesión de FuertaFit ha caducado. Recarga FuertaFit y vuelve a pulsar el marcador." }); return; }
    const page = await res.json();
    if (!page.length) break;
    list.push(...page);
  }
  const todo = list.filter(x => x.postType === "Routine" && x.hasVideo && !known.has(x.id));
  const items = [];
  for (let i = 0; i < todo.length; i++) {
    const b = todo[i];
    send({ type: "progress", done: i, total: todo.length, title: b.title });
    try {
      const res = await fetch(API + "post/" + b.id, { headers });
      if (res.status === 401) { send({ type: "error", text: "Tu sesión de FuertaFit ha caducado a mitad. Recarga FuertaFit y vuelve a pulsar el marcador." }); return; }
      const j = await res.json();
      items.push({
        id: j.id, title: j.title, durationMinutes: b.durationMinutes, format: j.postDuration && j.postDuration.name,
        intensity: j.intensity, location: j.trainingLocation, trainingType: j.trainingType && j.trainingType.name,
        materials: (j.materials || []).map(m => m.material && m.material.name).filter(Boolean),
        trainers: (j.trainers || []).map(t => t.trainer && t.trainer.name).filter(Boolean),
        tags: (j.tags || []).map(t => t.name || (t.tag && t.tag.name) || String(t)),
        summary: clean(j.smallDescription), description: clean(j.largeDescription).slice(0, 800),
        valuation: j.valuation, totalViews: j.totalViews, publishDate: j.publishDate, previewImage: j.previewImage,
      });
    } catch (e) { /* una rutina que falla no para el resto */ }
    await sleep(250);  // sin prisas, para no cargar su servidor
  }
  send({ type: "items", items, seen: list.length });
})();
