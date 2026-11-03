---
name: probar-cambios
description: Cómo probar cambios de Mi rutina Fuerta (generador, calendario, plan semanal, importación del catálogo, web) sin estropear los datos reales del usuario. Úsala antes de cualquier prueba que escriba en el calendario, historial, ajustes o catálogo.
---

# Probar fuertafit sin tocar los datos del usuario

Lo general (bases de pruebas, tests, shell) está en la skill raíz `probar-modulo`. Aquí lo propio de este módulo.
Datos reales: la base real (nombre en `CLAUDE.local.md` de la raíz). El usuario **no quiere que se restauren ni recreen** datos que haya borrado.

## 1. Copia de pruebas (desde la raíz, con `sg docker -c "..."`)

```bash
docker exec -i odoo odoo db duplicate -n <base-real> fuertafit_test
docker exec -i odoo odoo module upgrade -d fuertafit_test fuertafit
# … pruebas …
docker exec -i odoo odoo db drop fuertafit_test
```
`-n` neutraliza la copia: el cron de plan automático no corre en ella.

## 2. Lógica de Python: `odoo shell`

```bash
docker exec -i odoo odoo shell -d fuertafit_test --no-http < <scratchpad>/t.py
```
En `t.py`: `from odoo.addons.fuertafit.services import generator, planner, calendar, catalog`.
Para actuar como un usuario: `uenv = env(user=env.ref("base.user_admin").id)`. Si el catálogo está vacío, mete
rutinas de prueba con `env["fuerta.routine"].import_items([...])` (mismos campos que trae el marcador).
Sin `env.cr.commit()` nada se guarda.

## 3. En la web

- Entra en la copia: `http://localhost:8069/web/login?db=fuertafit_test` y luego `/fuerta`.
- Si no hay más remedio que probar en `fuertafit` (con permiso): fechas de un mes futuro sin planificar
  (mira antes `GET /fuerta/api/plans?from=...&to=...` y **anota lo que existe**) y al terminar borra solo lo tuyo con
  `POST /fuerta/api/plan/remove {"day": ...}` y `POST /fuerta/api/day/clear {"start": ..., "end": ...}`.
  Si cambias ajustes (`/fuerta/api/settings`), vuelve a poner el valor previo.
- `POST /fuerta/api/catalog/import` escribe en el catálogo común: pruébalo solo en `fuertafit_test`.

## 4. Navegador (Claude in Chrome)

- Cambiar solo el `#` no recarga: usa `location.reload()` tras cambiar estáticos.
- No dispares `alert`/`confirm` (bloquean la extensión). `window.open` desde `javascript_tool` se bloquea como
  emergente: crea un botón temporal y pulsa con `computer` (clic real).
- "Cannot access a chrome-extension:// URL of different extension": otra extensión tapa la pestaña; sigue con `curl`.
- Módulos JS expuestos para probar desde `javascript_tool`: `Hoy`, `Cal` (`select`, `move`, `skip`, `generate`),
  `Week`, `Cat`, `Sync`.
- Sin navegador: `node --check` de `addons/fuertafit/static/web/js/*.js` con `node:20-alpine` en Docker;
  concaténalos en orden de carga para detectar nombres declarados dos veces entre archivos.

## 5. Refactors: comparar la API antes y después

Dos copias idénticas (`fuertafit_a`, `fuertafit_b`), versión vieja y nueva del módulo, misma semilla
(`random.seed(12345)` al inicio del script de shell) y el mismo recorrido de la API; compara respuestas y tablas.
