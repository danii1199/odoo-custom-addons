---
name: probar-cambios
description: Cómo probar el módulo myspoty sin tocar la cuenta de Spotify ni los datos reales del usuario - base de pruebas, crons desactivados, tests de JS con jsdom. Úsala antes de cualquier prueba de myspoty.
---

# Probar myspoty

Lo general (bases de pruebas, tests de Odoo, shell) está en la skill raíz `probar-modulo`. Desde la raíz del repo y
con `sg docker -c "..."`.

## Base de pruebas

```bash
docker exec -i odoo odoo db init myspoty_test --language es_ES --country ES
docker exec -i odoo odoo module install -d myspoty_test myspoty
# tras cada cambio: odoo module upgrade -d myspoty_test myspoty && docker restart odoo
docker exec -i odoo odoo db drop myspoty_test        # al terminar
```
Si copias una base que ya tenga tokens reales, usa `odoo db duplicate -n` (neutraliza: crons parados). **Nunca**
dejes el cron de sync activo en una base de pruebas con tokens reales: renueva el permiso y gasta rate limit.

## Lo que necesita sesión de Spotify

Lo prueba el usuario (login con su cuenta, escrituras en playlists y me gusta). Tú prueba con `SPOTIFY_CLIENT_ID=prueba`
lo que no la necesita (modelos, reglas de inteligentes con datos inventados, letras, controladores) y simula las
respuestas de Spotify en el shell de Odoo (`odoo shell -d myspoty_test --no-http < t.py`, parcheando `services.spotify.api`).

## JS

- Sintaxis: `docker run --rm -v <scratchpad>:/c:ro node:20-alpine node --check /c/archivo.js`.
- Comportamiento (menús, selección, vistas): jsdom en `node:20-alpine` con `fetch` simulado; carga todos los
  scripts juntos en un único `<script>` (así comparten el ámbito global como en el navegador).
- En Chrome: no dispares `alert`/`confirm`; tras cambiar estáticos, `location.reload()`.
