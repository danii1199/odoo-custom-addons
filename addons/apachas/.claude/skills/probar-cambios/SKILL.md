---
name: probar-cambios
description: Cómo probar cambios del módulo apachas (gastos compartidos) - modelos, permisos de portal, correos, webhook y la web /apachas - en una base desechable. Úsala antes de cualquier prueba que escriba datos.
---

# Probar gastos

Lo general está en la skill raíz `probar-modulo`. Desde la raíz del repo y con `sg docker -c "..."`.

## Tests (base desechable: crean usuarios y mandan correos a la cola)

```bash
docker exec -i odoo odoo db init --language es_ES --country ES gastos_tests
docker exec -i odoo odoo -d gastos_tests --db-filter='^gastos_tests$' -i gastos --test-enable --test-tags /apachas --stop-after-init --http-port=8099 > <scratchpad>/log 2>&1
grep -E "ERROR|FAIL|of [0-9]+ tests" <scratchpad>/log      # sin «| head» directo: deja el proceso vivo
docker exec -i odoo odoo db drop gastos_tests
```

## A mano

- Datos de ejemplo con `odoo shell -d <base_de_pruebas> --no-http` (grupo, miembros, gastos, `env.cr.commit()`).
- Web: en el navegador usa `http://127.0.0.1:8069/web/login?db=<base>` (no cambia la sesión del usuario en
  `localhost`). Un usuario de portal ve solo sus grupos: pruébalo también con uno.
- Correos: `env["mail.mail"].search([], order="id desc", limit=5).mapped("body_html")` (no salen sin SMTP).
- Webhook sin servidor: `patch("odoo.addons.apachas.models.grupo.requests.post", ...)` y `env.cr.postcommit.run()`.
- JS: `docker run --rm -v $PWD/addons/apachas/static/src/js:/c:ro node:20-alpine node --check /c/apachas.js`
