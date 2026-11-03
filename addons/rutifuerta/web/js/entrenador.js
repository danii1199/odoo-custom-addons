/* Pestaña «Entrenador» (solo visible con API key). */
const Bot = (() => {
  let history = store("ff-chat") || [];
  let busy = false, ready = false;
  const SUGGESTIONS = [
    "Planifícame la semana que viene, 30 min al día y descanso el domingo",
    "Hoy tengo 20 minutos y poca energía, ¿qué hago?",
    "Rutina de pierna de 40 min con mancuernas para hoy",
    "¿Qué he entrenado estos últimos días?",
  ];

  function md(text) {
    // Formato mínimo: **negrita**, listas con "- " y saltos de línea.
    const lines = esc(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").split("\n");
    let html = "", inList = false;
    for (const l of lines) {
      const m = l.match(/^\s*[-•*]\s+(.*)/);
      if (m) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${m[1]}</li>`; continue; }
      if (inList) { html += "</ul>"; inList = false; }
      html += l.trim() ? l + "<br>" : "<br>";
    }
    return html + (inList ? "</ul>" : "");
  }

  function render(pending) {
    const box = $("chat");
    box.innerHTML = (history.length ? "" : `<div class="msg bot">¡Hola! Soy tu entrenador. Puedo planificarte días o semanas enteras
        con tus rutinas de FuertaFit, teniendo en cuenta lo que ya has hecho. Lo que planifique aparecerá en el <a href="#/calendario">calendario</a>.</div>`)
      + history.map(m => `<div class="msg ${m.role === "user" ? "user" : "bot"}${m.error ? " err" : ""}">${md(m.content)}${
          m.changedDays?.length ? `<div class="actions" style="margin-top:6px">${m.changedDays.map(d =>
            `<a href="#/calendario" onclick="Cal.goTo('${d}')">📅 ${esc(fmtDay(d))}</a>`).join(" ")}</div>` : ""}</div>`).join("")
      + (pending ? `<div class="msg bot typing">Pensando y revisando tu catálogo…</div>` : "");
    box.scrollTop = box.scrollHeight;
  }

  async function send() {
    const text = $("prompt").value.trim();
    if (!text || busy) return;
    busy = true; $("sendBtn").disabled = true; $("prompt").value = "";
    const prev = history.filter(m => !m.error).map(m => ({ role: m.role, content: m.content }));
    history.push({ role: "user", content: text });
    render(true);
    try {
      const res = await api("/api/bot/chat", { history: prev, message: text });
      history.push({ role: "assistant", content: res.reply, changedDays: res.changedDays, error: res.error });
    } catch (e) {
      history.push({ role: "assistant", content: "No he podido contactar con el servidor.", error: true });
    }
    history = history.slice(-40);
    store("ff-chat", history);
    busy = false; $("sendBtn").disabled = false;
    render();
  }

  async function loadSettings() { $("preferences").value = (await api("/api/settings")).preferences; }

  function setup() {
    if (!META.bot) {
      $("botOff").hidden = false;
      $("botOff").innerHTML = `El entrenador con IA está desactivado: falta la API key de Anthropic.
        Pon <code>ANTHROPIC_API_KEY=…</code> en el <code>.env</code>
        y recrea el contenedor de Odoo.`;
    }
    SUGGESTIONS.forEach(s => $("suggestions").appendChild(chip(esc(s), false, () => { $("prompt").value = s; $("prompt").focus(); })));
    $("sendBtn").onclick = send;
    $("prompt").onkeydown = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };
    $("clearChat").onclick = () => { history = []; store("ff-chat", history); render(); };
    $("savePrefs").onclick = async () => {
      await api("/api/settings", { preferences: $("preferences").value.trim() });
      $("prefsMsg").textContent = "Guardado ✓"; setTimeout(() => $("prefsMsg").textContent = "", 1500);
    };
  }

  return {
    show() { if (!ready) { setup(); ready = true; } render(busy); loadSettings(); },
    prefill(text) { $("prompt").value = text; },
  };
})();
