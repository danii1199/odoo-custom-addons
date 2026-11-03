---
name: actualizar-catalogo
description: Vuelve a extraer o actualizar el catálogo de rutinas de FuertaFit (modelo `fuerta.routine` de Odoo, común a todos los usuarios) usando la sesión del usuario en Chrome. Úsala cuando pida "actualizar rutinas", "recoger datos de nuevo", "hay rutinas nuevas en FuertaFit" o cuando el catálogo falte o esté corrupto.
---

# Actualizar el catálogo de FuertaFit

Hay dos caminos. Prefiere el primero; usa el segundo si el usuario te lo pide a ti o si hay que rehacerlo entero.

## A. El usuario lo hace solo (sin Claude)

Pestaña **Actualizar** de la web (`/fuerta#actualizar`): arrastrar el marcador «⟳ Actualizar Fuerta» a favoritos, abrir
webapp.fuertafit.com con sesión y pulsarlo. Solo trae rutinas nuevas. Código: `static/web/bookmarklet.js` y
`static/web/sync.html` (servido en `/fuerta/sync`). Si falla, revisa esos dos archivos y `POST /fuerta/api/catalog/import`
(`controllers/main.py` → `fuerta.routine.import_items` en `models/routine.py`, limpieza en `services/catalog.clean_item`).

## B. Hacerlo tú con Claude in Chrome

Reglas: **nunca pidas ni teclees la contraseña**; el usuario inicia sesión él mismo. Solo metadatos, nunca vídeos.

1. Carga la skill del navegador y las herramientas `mcp__claude-in-chrome__*` en una sola ToolSearch
   (incluye `javascript_tool`, `read_network_requests`, `list_connected_browsers`, `select_browser`).
2. Hay dos Chrome conectados. El del usuario en este PC es **Linux ("Browser 1")**; el de Windows es otro equipo.
   Si `tabs_context_mcp` falla con "No group with id", lista los navegadores y pregunta cuál usar (AskUserQuestion).
3. Navega a `https://webapp.fuertafit.com/#/training` en una pestaña del grupo. La sesión se guarda **por pestaña**
   (sessionStorage), así que normalmente redirige al login: pide al usuario que inicie sesión **en esa pestaña**.
4. Token: `JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k => k.startsWith("oidc.user:")))).access_token`.
   Guárdalo en `window.__ffh = {Authorization: "Bearer " + token}`; **no lo imprimas nunca**. Dura ~1-2 h.
5. API (JSON, `api.fuertafit.com/api/v2/dona/`):
   - Listado: `posts?IsVisible=true&PageNum=N&ResultsPerPage=100` hasta página vacía (~2.600 publicaciones).
     Interesan `postType === "Routine" && hasVideo` (~1.590). Trae `durationMinutes`.
   - Detalle: `post/{id}` (singular; `posts/{id}` da 404). La salida puede venir bloqueada por el filtro de datos
     sensibles si incluye URLs firmadas: extrae solo los campos que necesitas.
6. Lanza la extracción **en segundo plano dentro de la página** (`window.__ffjob = {...}`, bucle async con 300 ms de
   pausa entre peticiones, parar en 401) y consulta el progreso con llamadas cortas. Así gasta pocos tokens.
   En pestaña de fondo va a ~60/min. Para un refresco, pide solo los ids que no estén en `GET /fuerta/api/catalog/ids` (requiere sesión de Odoo).
7. Campos por rutina (los que conserva `services/catalog.clean_item`): `id, title, url, durationMinutes, format (postDuration.name),
   intensity, location (trainingLocation), trainingType (.name), materials ([].material.name), trainers
   ([].trainer.name), tags, summary (smallDescription sin HTML), description (largeDescription sin HTML, 800 chars),
   valuation, totalViews, publishDate, previewImage`.
8. Para llevar los datos al disco, elige una:
   - **Refresco:** `fetch` no llega a localhost desde la página de FuertaFit. Usa `window.open` de `/fuerta/sync` +
     `postMessage` (hace falta un clic real: crea un botón temporal y púlsalo con `computer`), o
   - **Completo:** mismo mecanismo que el refresco (ventana `/fuerta/sync` + `postMessage`): con el catálogo vacío,
     `GET /fuerta/api/catalog/ids` devuelve [] y se envían todas. No hace falta descargar archivos.
   El navegador debe tener sesión de Odoo en la base correcta (la real, o `fuertafit_test` para probar).
9. Comprueba el resultado en la pestaña de la web: `fetch("/fuerta/api/meta")` (total y grupos), o en Odoo,
   menú Mi rutina Fuerta → Catálogo. Luego deja la pestaña como estaba.
