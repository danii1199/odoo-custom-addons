---
name: probar-cambios
description: Cómo probar cambios del módulo dbd (Dead by Daylight) - modelos, vistas y la web /dbd - en una base de pruebas sin tocar la base dbd. Úsala antes de cualquier prueba que escriba datos.
---

# Probar dbd

Lo general está en la skill raíz `probar-modulo`. Desde la raíz del repo y con `sg docker -c "..."`.

## Base de pruebas

Si el usuario tiene una base de pruebas (nombre en la memoria de Claude), úsala; si no existe o es algo arriesgado, haz una copia:

```bash
docker exec -i odoo odoo db duplicate -n <base-pruebas> dbd_test
# o desde cero:  odoo db init --language es_ES --country ES dbd_test && odoo module install -d dbd_test dbd
docker exec -i odoo odoo module upgrade -d dbd_test dbd
docker restart odoo                                          # recarga Python y plantillas en el servidor
# … pruebas …
docker exec -i odoo odoo db drop dbd_test
```

## Web sin navegador (como visitante anónimo)

```bash
J=<scratchpad>/cj.txt; curl -s -c $J -b $J -o /dev/null "http://localhost:8069/web/login?db=dbd_test"
for u in /dbd /dbd/supervivientes /dbd/asesinos /dbd/perks /dbd/complementos /dbd/ofrendas /dbd/mapas; do
  curl -s -c $J -b $J -o /dev/null -w "$u %{http_code}\n" "http://localhost:8069$u"; done
docker logs --since 2m odoo 2>&1 | grep -A15 ERROR
```
Fichas: `/dbd/supervivientes/<slug>` (p. ej. `dwight-fairfield-1`), `/dbd/asesinos/the-trapper-2`…
En el navegador usa `http://127.0.0.1:8069` para la base de pruebas: así no cambias la sesión que el usuario tiene
abierta en `localhost` (cada host guarda su cookie).

## Modelos: `odoo shell`

`docker exec -i odoo odoo shell -d dbd_test --no-http < <scratchpad>/t.py`; termina con
`env.cr.rollback()` si no quieres guardar. Comprueba las restricciones de `dbd.perk` y `dbd.addon`
(dos dueños, bando incorrecto) con `ValidationError` dentro de `env.cr.savepoint()`.

## JS

`docker run --rm -v $PWD/addons/dbd/static/src/js:/c:ro node:20-alpine node --check /c/dbd.js`

## Importador

`odoo shell -d dbd_test --no-http < addons/dbd/scripts/actualizar_catalogo.py` (hace commit). Una segunda pasada debe
dar 0 nuevos en todo (si no, el emparejamiento por clave/nombre falla). Para ver qué falta sin imagen:
`env[model].search([("image", "=", False)])`. Fuentes y reglas en el `CLAUDE.md` del módulo.
