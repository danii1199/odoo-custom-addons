---
name: odoo-bases-de-datos
description: Gestionar las bases de datos del Odoo común - listar, crear, duplicar, hacer copias de seguridad, restaurar, renombrar o borrar bases (con su filestore), y entrar en Postgres. Úsala cuando el usuario pida una base nueva, una copia, un backup, restaurar, o preparar una base de pruebas.
---

# Bases de datos de Odoo

Dos caminos, ambos gestionan base + filestore (adjuntos en el volumen `odoo-datos`):

- **Web**: `http://localhost:8069/web/database/manager` con la contraseña maestra (`ODOO_MASTER_PASSWORD` en `~/servicios/.env`;
  dísela al usuario solo si la pide y sin copiarla en ningún archivo).
- **CLI** (preferido para ti): `sg docker -c "docker exec -i odoo odoo db <orden> ..."` (desde cualquier carpeta).

| Qué | Orden |
|---|---|
| Listar | `docker exec postgres psql -U admin -Atc "select datname from pg_database where datdba = 'odoo'::regrole"` |
| Crear vacía | `odoo db init <bd> --language es_ES --country ES` (usuario admin/admin por defecto: `--password`) y luego `odoo module install -d <bd> <modulo>` |
| Duplicar | `odoo db duplicate <origen> <destino>` (`-n` neutraliza: sin crons ni correos; ideal para pruebas) |
| Copia de seguridad | `odoo db dump <bd> /tmp/<bd>.zip` y `docker cp odoo:/tmp/<bd>.zip ~/proyectos/copias-seguridad/` |
| Restaurar | `docker cp <archivo>.zip odoo:/tmp/` y `odoo db load <bd-nueva> /tmp/<archivo>.zip` |
| Renombrar | `odoo db rename <vieja> <nueva>` |
| Borrar | `odoo db drop <bd>` |

- Copias en `~/proyectos/copias-seguridad/` (fuera del repo) con fecha en el nombre: `fuertafit-2026-10-05.zip`.
  Borra luego el `.zip` de `/tmp` del contenedor.
- El rol `odoo` tiene `CREATEDB`: es el dueño de todas las bases de Odoo. El superusuario de Postgres es `admin`
  (`docker exec postgres psql -U admin -d <bd>`), útil para consultas de solo lectura.
- Postgres completo (todas las bases): `sg docker -c "docker exec postgres pg_dumpall -U admin" > ~/proyectos/copias-seguridad/todo-<fecha>.sql`.

## Normas

- `fuertafit` tiene **datos reales**. Antes de `drop`, `load` encima, `rename` o `-f` sobre una base que no hayas
  creado tú en esta sesión: pide confirmación y propone hacer antes una copia.
- Bases de pruebas: nombre `<bd>_test` o `<bd>_prueba`; bórralas al terminar.
- No recrees ni restaures datos que el usuario haya borrado.
- Si una base no aparece en el selector de `/web/login`, comprueba que su dueño sea `odoo`.
