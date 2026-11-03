---
name: odoo-docker
description: Arrancar, parar, reiniciar, reconstruir o revisar el Odoo 20 común, Postgres y los demás servicios Docker del usuario, y aplicar cambios de código de un módulo (actualizarlo). Úsala tras cambiar código de cualquier addon, para ver logs, abrir un shell de Odoo o cuando Odoo no responda en localhost:8069.
---

# Odoo y Postgres en Docker

Los compose **no están en el repo**: viven en la carpeta de despliegue del usuario (sin git; su ruta, en tu memoria;
abajo `$SERVICIOS`), un proyecto Compose por servicio, independientes entre sí; Odoo encuentra a Postgres por una
red Docker externa. `$SERVICIOS/servicios.sh` los maneja todos. No escribas esa ruta ni detalles de red en el repo. Siempre envuelto en `sg docker -c "..."` (sin el grupo
`docker` activo da "permission denied"). Los `docker exec`/`docker restart` van por nombre de contenedor: valen desde
cualquier carpeta.

| Qué | Comando |
|---|---|
| Estado de todos | `sg docker -c "$SERVICIOS/servicios.sh"` |
| Arrancar / parar (todos o los indicados) | `sg docker -c "$SERVICIOS/servicios.sh up [odoo…]"` · `down [odoo…]` |
| Logs | `sg docker -c "docker logs odoo --tail 50"` |
| Reiniciar Odoo (cambios Python/XML, `odoo.conf`) | `sg docker -c "docker restart odoo"` |
| Actualizar un módulo | `sg docker -c "docker exec -i odoo odoo module upgrade -d <bd> <modulo>"` y luego `restart odoo` |
| Instalar un módulo | `sg docker -c "docker exec -i odoo odoo module install -d <bd> <modulo>"` y luego `restart odoo` |
| Cambió `Dockerfile` u `odoo-entrypoint.sh` | `sg docker -c "$SERVICIOS/servicios.sh build odoo"` |
| Cambió el `.env` o un compose (`restart` no lo relee) | `sg docker -c "$SERVICIOS/servicios.sh recrear odoo"` |
| Cualquier orden de Compose en un proyecto | `sg docker -c "$SERVICIOS/servicios.sh odoo config"` (ps, pull, exec…) |
| Shell de Odoo (Python con `env`) | `sg docker -c "docker exec -i odoo odoo shell -d <bd> --no-http" < script.py` |
| Comprobar | `curl -s -o /dev/null -w '%{http_code}\n' localhost:8069/web/login` (200) |

Alternativa equivalente a `module upgrade`: `odoo -d <bd> -u <modulo> --stop-after-init` (no levanta HTTP, así que
no choca con el servidor en marcha). Tras actualizar, reinicia para que el servidor cargue el código nuevo.

## Detalles que ya dieron problemas

- Odoo 20 escucha por defecto en `127.0.0.1`: `odoo.conf` lleva `http_interface = 0.0.0.0`; sin eso, curl da 000.
- `/etc/odoo/odoo.conf` lo genera `odoo-entrypoint.sh` en cada arranque (con `admin_passwd`, permisos 600). Edita
  `odoo.conf` del repo, nunca el del contenedor. `addons_path` = `/mnt/extra-addons` (= `addons/`) en cuanto hay algún módulo.
- `odoo-entrypoint.sh` va **dentro de la imagen**: tras editarlo, `servicios.sh build odoo` (un `restart` sigue usando el viejo).
- Los addons se montan en solo lectura: no hace falta `--build` para cambios de código, pero sí actualizar el módulo
  si cambian modelos, vistas, datos o permisos.
- Estáticos (`static/`): Odoo los cachea en el navegador; recarga forzada o versiona las URL (ver `rutifuerta`).
- `servicios.sh down` está bien; **`down -v` o `docker volume rm` borran todas las bases de datos**: nunca sin
  confirmación explícita del usuario.
- Antes de recrear un contenedor, si necesitas sus logs, míralos: se pierden.
- No uses `pkill -f` con patrones amplios: puede matar tu propia shell.
- **"A css error occurred, using an old style"** (franja roja abajo; error SCSS de `rgba($color…)` en Bootstrap):
  a la base le faltan módulos estándar auto-instalables, sobre todo `html_editor`. Le pasó a `rutifuerta` el
  2026-10-05. Arreglo: `odoo module install -d <bd> html_editor`, borrar la caché de CSS
  (`env["ir.attachment"].search([("url", "=like", "/web/assets/%")]).unlink()` + `env.cr.commit()` en `odoo shell`) y
  `restart odoo`. Para ver el error real: `curl` del `.css` enlazado en `/web/login` y buscar `css_error_message`.
