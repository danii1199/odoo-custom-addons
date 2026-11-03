# myspoty (módulo de Odoo `myspoty`, pendiente de portar)

Reproductor propio de Spotify (Web API + Web Playback SDK) con datos propios encima: etiquetas, valoraciones, notas,
playlists inteligentes, estadísticas y letras. El usuario tiene Premium. Interfaz y código en español.

Es un proyecto del Odoo 20 común del repo (como `../fuertafit`): Docker, Postgres y bases de datos en la raíz
(`../../CLAUDE.md`, skills `odoo-docker`, `odoo-bases-de-datos`, `probar-modulo`, `nuevo-modulo`).

## Estado (2026-10-05)

- El módulo aún **no existe**. Esta carpeta (`addons/myspoty`) será el módulo (nombre técnico `myspoty`):
  `__manifest__.py`, `models/`… irán directamente aquí. Hasta entonces Odoo la ignora.
- `app/` es la **app antigua** independiente (`http.server`, solo librería estándar + psycopg). Es la referencia
  funcional para portar; no se ejecuta ya. Al portar, `app/` se borra.
- Los datos de la app antigua (base `myspoty`) **no le importan al usuario**: no hay que migrarlos. Empezar limpio.
- Cómo portarla: skill `portar-a-odoo`. Lo que se sabe de la API de Spotify: skill `spotify-api`.

## Diseño previsto en Odoo (mismo patrón que fuertafit)

```
addons/myspoty/
  models/       usuario = res.users de Odoo; su permiso de Spotify (tokens) en un modelo propio por usuario;
                canciones y letras comunes; etiquetas, valoraciones, notas, inteligentes, escuchas y tops por usuario
  services/     spotify.py (OAuth PKCE, renovar token, api()), smart_sources.py, smart_playlists.py, sync.py, lyrics.py
  controllers/  main.py: /myspoty (web), /myspoty/callback (OAuth) y /myspoty/api/* (JSON, auth="user")
  data/         ir_cron.xml: sync horaria de escuchas y tops (antes scheduler.py)
  security/     ir.access.csv: datos de cada usuario filtrados por user_id
  static/web/   la web actual (index.html, css/, js/) con las URL cambiadas a /myspoty/...
```

- Sesiones: las da Odoo (login de Odoo) → desaparecen `users`/`sessions`/cookie `myspoty_sid` y el código de 6
  letras para otros dispositivos. Cada usuario de Odoo conecta **su** Spotify (PKCE) una vez.
- Redirect URI de Spotify: Spotify no acepta `localhost`; con Odoo en el puerto 8069 será
  `http://127.0.0.1:8069/myspoty/callback` (hay que añadirla en el panel de Spotify). Fuera de este PC hace falta https.
- `SPOTIFY_CLIENT_ID` (sin secreto, PKCE) irá en el `.env` raíz + `environment:` del servicio `odoo`, o en un
  `ir.config_parameter` editable desde Ajustes.

## Normas

- No leer ni mostrar `.env` ni tokens de Spotify. No pedir al usuario credenciales de Spotify: inicia sesión él.
- No lanzar syncs completas seguidas contra la cuenta real (rate limit de Spotify; ver `spotify-api`).
  En pruebas, nunca una base con tokens reales y el cron de sync activo (duplica con `-n`: neutraliza los crons).
- Las escrituras en la cuenta de Spotify del usuario (playlists, me gusta) solo las prueba el usuario.
- Pruebas: skill `probar-cambios`.
