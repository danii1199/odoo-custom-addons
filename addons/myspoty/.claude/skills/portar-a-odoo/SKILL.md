---
name: portar-a-odoo
description: Portar la app antigua de myspoty (carpeta app/) a un módulo de Odoo 20 `myspoty`, siguiendo el patrón de fuertafit. Úsala cuando el usuario pida empezar o continuar el módulo de myspoty, o al mover una parte concreta (modelos, sync, inteligentes, letras, web).
---

# Portar myspoty a Odoo

Referencia de cómo se hizo con fuertafit: `../fuertafit` (controlador con `_api`, `services/` con
`env`, web en `static/web`, cron) y la skill raíz `nuevo-modulo`. Los datos antiguos **no se migran**.

## Mapa app antigua → módulo

| App antigua (`app/`) | Módulo `myspoty/` |
|---|---|
| `models/db.py` (esquema SQL) | modelos de Odoo, uno por tabla; `fields.Json` donde hoy hay JSON |
| `models/auth.py` users / sessions / device codes | **fuera**: usuarios y sesiones de Odoo |
| `models/auth.py` tokens | `myspoty.token` (uno por `res.users`, campos no legibles en vistas; acceso solo `sudo` en el servicio) |
| `models/library.py`, `liked.py`, `smart.py`, `plays.py`, `spotify_top.py` | `myspoty.track` (común), `myspoty.tag`, `myspoty.track.tag`, `myspoty.rating`, `myspoty.liked`, `myspoty.smart`, `myspoty.play`, `myspoty.top` |
| tabla `lyrics` | `myspoty.lyrics` (común) |
| `context.py` (`as_user`, `uid()`) | `self.env.uid` / `self.env.user` |
| `router.py`, `server.py`, `controllers/*` | `controllers/main.py` con `http.route("/myspoty/api/...", auth="user")` |
| `services/*.py` | `services/*.py` recibiendo `env` (sin HTTP) |
| `scheduler.py` (sync horaria, 20 s entre usuarios) | `data/ir_cron.xml` → método `_cron_sync` que recorre usuarios con token |
| `views/static/` | `static/web/`; cambiar `api()` de `core.js` a `/myspoty/api`, y el login a `/web/login?redirect=/myspoty` |
| `MYSPOTY_NO_SYNC=1` | cron desactivado (o base de pruebas neutralizada) |

## Orden recomendado

1. Esqueleto instalable (manifest, menú que abre `/myspoty`, icono) en `addons/myspoty/myspoty/` + `restart odoo`.
   Instalarlo primero en una base de pruebas (`myspoty_test`, ver `probar-cambios`).
2. Modelos + `ir.access.csv`. 3. `services/spotify.py` (PKCE: el `state`→`verifier` puede ir en la sesión de Odoo
   `request.session` en vez de en memoria) y `/myspoty/login` + `/myspoty/callback`. 4. Biblioteca, etiquetas,
   valoraciones. 5. Sync + cron. 6. Inteligentes. 7. Letras. 8. Web estática.
3. Cada paso: `odoo module upgrade -d myspoty_test myspoty`, revisar logs, probar. Instalar en la base real
   (¿`fuertafit` u otra base nueva?) **solo cuando el usuario diga en cuál**.

## Cuidado

- Mantén los nombres de funciones JS globales (`Player`, `Now`, `Pop`, `Editor`, `TrackList`, `Menu`, `Ask`, `Lib`,
  `Aura`) y el orden de carga de scripts; el navegador sigue llamando a la Web API de Spotify directamente con el
  token de `/myspoty/api/token`.
- Rutas sin `#` de la app antigua (`/playlists`, `/tags`…): en Odoo usa `/myspoty/<ruta>` con una ruta comodín
  que devuelva `index.html`, o pasa a `#`.
- Antes de usar un endpoint de Spotify, consulta la skill `spotify-api` (muchos dan 403/404 a apps nuevas).
