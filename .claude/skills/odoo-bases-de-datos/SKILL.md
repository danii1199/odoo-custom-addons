---
name: odoo-bases-de-datos
description: Gestionar las bases de datos del Odoo común - listar, crear, duplicar, hacer copias de seguridad, restaurar, renombrar o borrar bases (con su filestore), y entrar en Postgres. Úsala cuando el usuario pida una base nueva, una copia, un backup, restaurar, o preparar una base de pruebas.
---

# Bases de datos de Odoo

Solo por consola (gestiona base + filestore, los adjuntos del volumen `odoo-datos`):
`sg docker -c "docker exec -i odoo odoo db <orden> ..."` (desde cualquier carpeta).

- El gestor web (`/web/database/manager`) está **desactivado** (`list_db = False`) porque Odoo está publicado en
  internet: con la contraseña maestra se podría descargar o borrar una base. No lo reactives sin que lo pida.
- El navegador solo abre la base que fija `dbfilter` (variable `ODOO_DBFILTER` del compose de despliegue). Para el
  resto, consola; para tests en otra base: `--db-filter='^<base>$'` en la orden (ver skill `probar-modulo`).

| Qué | Orden |
|---|---|
| Listar | `docker exec postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -Atc "select datname from pg_database where datdba = '\''odoo'\''::regrole"'` |
| Crear vacía | `odoo db init <bd> --language es_ES --country ES` (usuario admin/admin por defecto: `--password`) y luego `odoo module install -d <bd> <modulo>` |
| Duplicar | `odoo db duplicate <origen> <destino>` (`-n` neutraliza: sin crons ni correos; ideal para pruebas) |
| Copia de seguridad | `odoo db dump <bd> /tmp/<bd>.zip` y `docker cp odoo:/tmp/<bd>.zip <carpeta-de-copias>/` |
| Restaurar | `docker cp <archivo>.zip odoo:/tmp/` y `odoo db load <bd-nueva> /tmp/<archivo>.zip` |
| Renombrar | `odoo db rename <vieja> <nueva>` |
| Borrar | `odoo db drop <bd>` |

- Copias en la carpeta de copias del usuario (fuera del repo; ruta en tu memoria) con fecha en el nombre: `rutifuerta-2026-10-05.zip`.
  Borra luego el `.zip` de `/tmp` del contenedor.
- El rol `odoo` tiene `CREATEDB`: es el dueño de todas las bases de Odoo. El superusuario de Postgres es el de
  `$POSTGRES_USER` (`docker exec postgres sh -c 'psql -U "$POSTGRES_USER" -d <bd>'`), útil para consultas de solo lectura.
- Postgres completo (todas las bases): `sg docker -c "docker exec postgres sh -c 'pg_dumpall -U \"\$POSTGRES_USER\"'" > <carpeta-de-copias>/todo-<fecha>.sql`.

## Normas

- La **base real** (nombre en tu memoria) tiene **datos reales**. Antes de `drop`, `load` encima, `rename` o `-f` sobre una base que no hayas
  creado tú en esta sesión: pide confirmación y propone hacer antes una copia.
- Bases de pruebas: nombre `<bd>_test` o `<bd>_prueba`; bórralas al terminar.
- No recrees ni restaures datos que el usuario haya borrado.
- Si una base no aparece en el selector de `/web/login`, comprueba que su dueño sea `odoo`.
