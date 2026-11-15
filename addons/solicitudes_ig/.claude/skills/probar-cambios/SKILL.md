---
name: probar-cambios
description: Cómo probar cambios del módulo solicitudes_ig (lector de la exportación de Instagram, importación y web /solicitudes-ig) en la base de pruebas.
---

# Probar solicitudes_ig

Desde la raíz del repo, con `sg docker -c "..."`, en la base de pruebas (nombre en la memoria de Claude):

```bash
docker exec -i odoo odoo -d <base> --db-filter='^<base>$' -u solicitudes_ig --test-enable --test-tags /solicitudes_ig --stop-after-init --http-port=8099
docker run --rm -v $PWD/addons/solicitudes_ig/web:/c:ro node:20-alpine node --check /c/app.js
```

`services/lector.py` no depende de Odoo: si Instagram cambia el formato de la exportación, añade un ejemplo a
`tests/test_solicitudes.py`. Nunca pruebes contra Instagram ni automatices clics allí.
