/* Pestaña «Actualizar»: marcador para traer rutinas nuevas de FuertaFit. */
const Sync = (() => {
  let built = false;
  async function build() {
    // El marcador lleva dentro la dirección de esta web (localhost o la IP de la red, según desde dónde entres).
    const src = await (await fetch("/rutifuerta/web/bookmarklet.js?v=" + Date.now())).text();
    const code = src.replace(/^\/\*[\s\S]*?\*\/\s*/, "").replace("__APP__", location.origin);
    $("bookmarklet").href = "javascript:" + encodeURIComponent(code);
    $("appUrl").textContent = location.origin;
    built = true;
  }
  return {
    async show() {
      if (!built) await build();
      const [meta, s] = [await api("/api/meta"), await api("/api/settings")];
      const when = s.catalogUpdated ? new Date(s.catalogUpdated).toLocaleString("es-ES", { dateStyle: "long", timeStyle: "short" }) : null;
      $("syncInfo").textContent = `${meta.total} rutinas con vídeo · ` +
        (when ? `última actualización: ${when}` : "extraído por primera vez el 28 de septiembre de 2026");
    },
  };
})();
