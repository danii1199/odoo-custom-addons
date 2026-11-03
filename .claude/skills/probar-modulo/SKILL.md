---
name: probar-modulo
description: Probar cambios de cualquier módulo de Odoo sin tocar los datos reales - copia de pruebas de la base, tests de Odoo, shell con scripts y comprobación de JS. Úsala antes de cualquier prueba que escriba datos o al validar un cambio.
---

# Probar un módulo sin tocar datos reales

Desde la raíz del repo, con `sg docker -c "..."`. Las skills del proyecto (p. ej. `addons/rutifuerta/.claude/skills/probar-cambios`)
añaden lo específico de cada módulo.

## 1. Base de pruebas

```bash
docker exec -i odoo odoo db duplicate -n <base-real> rutifuerta_test   # copia neutralizada (sin crons ni correos)
docker exec -i odoo odoo module upgrade -d rutifuerta_test <modulo>  # aplica tu código a la copia
# … pruebas …
docker exec -i odoo odoo db drop rutifuerta_test
```
Para un módulo nuevo sin datos: `odoo db init <modulo>_test` + `odoo module install -d <modulo>_test <modulo>`.

## 2. Tests de Odoo (`tests/` del módulo)

```bash
docker exec -i odoo odoo -d <base> --db-filter='^<base>$' -u <modulo> --test-enable --test-tags /<modulo> --stop-after-init --http-port=8099
```
`--db-filter` hace falta porque el `dbfilter` del despliegue solo deja abrir la base real (los HttpCase fallarían).
Revisa `ERROR`/`FAIL` en la salida (`| grep -E "ERROR|FAIL|tests"`). Nunca lances tests contra `rutifuerta`.

## 3. Scripts en el shell de Odoo

`docker exec -i odoo odoo shell -d <bd>_test --no-http < <scratchpad>/t.py`. En el script está `env`;
para guardar, `env.cr.commit()` (sin él se descarta todo al salir: útil para pruebas de solo lectura).

## 4. HTTP y navegador

- El servidor sirve todas las bases: entra en la de pruebas con `/web/login?db=<bd>_test`.
- `curl` con sesión: inicia sesión con `/web/session/authenticate` (JSON) guardando cookies en el scratchpad.
- No dispares `alert`/`confirm` en Chrome (bloquean la extensión).
- JS sin navegador (no hay node en el sistema): copia los `.js` al scratchpad y
  `docker run --rm -v <scratchpad>:/c:ro node:20-alpine node --check /c/archivo.js`.

## 5. Si no queda más remedio que probar en la base real

Pide permiso, anota lo que existe antes, usa fechas o registros fácilmente identificables y deja todo como estaba.
