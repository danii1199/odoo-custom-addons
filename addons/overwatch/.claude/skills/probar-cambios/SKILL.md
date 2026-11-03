---
name: probar-cambios
description: Cómo probar cambios del módulo overwatch - importador (OverFast + wiki), parser de cosméticos, la selección /overwatch y la galería - en una base de pruebas. Úsala antes de cualquier prueba que escriba datos.
---

# Probar overwatch

Lo general está en la skill raíz `probar-modulo`. Desde la raíz del repo y con `sg docker -c "..."`.

## Tests

```bash
docker exec -i odoo odoo db init --language es_ES --country ES ow_tests
docker exec -i odoo odoo -d ow_tests -i overwatch --test-enable --test-tags /overwatch --stop-after-init --http-port=8099 > <scratchpad>/log 2>&1
grep -E "ERROR|FAIL|of [0-9]+ tests" <scratchpad>/log
docker exec -i odoo odoo db drop ow_tests
```
Los tests usan claves `test-*`, así que valen también en una base con el catálogo importado.

## Parser de la wiki sin Odoo

`services/wiki.py` no depende de Odoo: `python3 -I script.py` con `sys.path.insert(0, "addons/overwatch/services")`,
`wiki.cosmeticos_heroe(wiki.nueva_sesion(), "Ana")` y `wiki.urls_archivos(...)`. Si cambia el formato de las tablas,
añade el caso a `TABLA` en tests/test_overwatch.py.

## Importador

`odoo shell -d <base> --no-http < addons/overwatch/scripts/actualizar_catalogo.py` (commit por héroe, ~2-3 min).
Una segunda pasada debe dar 0 héroes y 0 cosméticos nuevos. Sin imagen:
`env["ow.cosmetic"].search_count([("media_url", "=", False), ("image", "=", False)])`.
No uses User-Agents de navegador ni otros trucos con la CDN de la wiki: solo su API.

## Web

En el navegador, `http://127.0.0.1:8069/web/login?db=<base>` (no toca la sesión de `localhost`). Tras cambiar
CSS/JS, `docker restart odoo` (el `?v=` se calcula al arrancar). JS:
`docker run --rm -v $PWD/addons/overwatch/static/src/js:/c:ro node:20-alpine sh -c 'node --check /c/select.js && node --check /c/hero.js'`
