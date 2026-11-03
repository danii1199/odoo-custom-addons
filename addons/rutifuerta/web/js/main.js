/* Menú (rutas por #) y arranque de la web. Se carga el último. */
const views = ["hoy", "calendario", "semana", "rutinas", "entrenador", "actualizar", "sigilo"];
function route() {
  const v = (location.hash.match(/#\/(\w+)/) || [])[1];
  // Sigilo solo existe si la base tiene la plantilla nueva (sigilo.js); si no, se queda en Hoy en vez de romper la app.
  const view = views.includes(v) && (v !== "entrenador" || META.bot) && (v !== "sigilo" || typeof Sigilo !== "undefined") ? v : "hoy";
  views.forEach(x => { if ($("view-" + x)) $("view-" + x).hidden = x !== view; });
  document.querySelectorAll("#fuerta-app .fa-nav a").forEach(a => a.classList.toggle("on", a.dataset.view === (view === "sigilo" ? "hoy" : view)));
  ({ hoy: Hoy.show, calendario: Cal.show, semana: Week.show, rutinas: Cat.show, entrenador: Bot.show, actualizar: Sync.show, sigilo: () => Sigilo.show() })[view]();
}
window.addEventListener("hashchange", route);

(async () => {
  META = await api("/api/meta");
  $("botLink").hidden = !META.bot;
  $("userName").textContent = META.user;
  DEFAULT_MIN = (await api("/api/settings")).dailyMinutes;
  $("defMin").value = DEFAULT_MIN;
  let t = null;
  $("defMin").oninput = () => {
    const m = +$("defMin").value;
    if (!m || m < 5) return;
    clearTimeout(t);
    t = setTimeout(async () => {
      DEFAULT_MIN = (await api("/api/settings", { dailyMinutes: m })).dailyMinutes;
      Hoy.setDefault(DEFAULT_MIN);
      Cal.refreshDefault();
    }, 400);
  };
  route();
})();
