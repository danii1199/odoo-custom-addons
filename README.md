# odoo-custom-addons

Odoo 20 Community con mis módulos propios. Postgres y Odoo comunes en Docker; cada proyecto es una carpeta de
`addons/` (los extra-addons): cada carpeta de `addons/` es un módulo.

Aquí solo está el código de Odoo (`addons/`, `Dockerfile`, `odoo.conf`). Los compose, el `.env` y los scripts de
instalación y copias viven fuera del repo, en `~/servicios/` de mi PC, y viajan con la carpeta de mudanza.

| Proyecto | Módulo | Estado |
|---|---|---|
| [`addons/fuertafit`](addons/fuertafit) | `fuertafit` · Mi rutina Fuerta (web en el sitio web de Odoo, `/fuerta`) | ver su README |
| [`addons/dbd`](addons/dbd) | `dbd` · enciclopedia de Dead by Daylight (web `/dbd`, catálogo importado de fuentes públicas) | ver su README |
| [`addons/menu_inicio`](addons/menu_inicio) | `menu_inicio` · pantalla de inicio con iconos de apps (estilo Enterprise) | instálalo en cada base |
| [`addons/gastos`](addons/gastos) | `gastos` · gastos compartidos tipo Splitwise (web `/gastos`, avisos por correo, webhook n8n) | ver su README |
| [`addons/overwatch`](addons/overwatch) | `overwatch` · selección de héroes de Overwatch, favoritos, aleatorio, historia y galería (`/overwatch`) | ver su README |
| [`addons/inicio_web`](addons/inicio_web) | `inicio_web` · portada del sitio web: reloj, saludo y una tarjeta por proyecto (`/`) | ver su CLAUDE.md |
| [`addons/myspoty`](addons/myspoty) | `myspoty` · reproductor de Spotify | pendiente de portar a Odoo |

## Instalar (en este PC o en otro)

`~/servicios/instalar.sh` lo hace **todo** en un Linux Mint / Ubuntu recién instalado: git, Docker y Compose, Claude
Code, el repo en `~/proyectos/odoo-custom-addons`, `~/servicios`, `.env` con contraseñas al azar, Odoo y Postgres, y restaura
las copias. Se puede repetir sin miedo: no sobrescribe `.env`, el repo ni una base que ya exista.

### Llevarlo a otro PC

1. En este PC: `~/servicios/preparar-mudanza.sh` (o `… claude-main claude-test` para varias bases).
   Crea `~/proyectos/mudanza-<fecha>/` con la copia de las bases (base + adjuntos), el repo tal cual (historial de
   git y cambios sin subir), `~/servicios` (sin `.env` ni los datos de Vaultwarden), tus ajustes de Claude y el instalador. Cópiala a un USB: son **datos reales**,
   no la subas a ningún sitio público.
2. En el PC nuevo: `bash /ruta/al/usb/mudanza-<fecha>/instalar.sh` (pide la contraseña de sudo).
3. Odoo en http://localhost:8069 con tu usuario de siempre. Claude: terminal nueva, `cd ~/proyectos/odoo-custom-addons && claude`
   (la primera vez, iniciar sesión). La contraseña maestra del gestor de bases es nueva: `ODOO_MASTER_PASSWORD` en `~/servicios/.env`.

Sin carpeta de mudanza, `instalar.sh` clona el repo de GitHub, pero necesita `~/servicios` (no está en git). Una copia
suelta se restaura con `~/servicios/instalar.sh ~/proyectos/copias-seguridad/<base>-<fecha>.zip [nombre-base]`.

## Contraseñas (.env)

`~/servicios/ajustar-env.sh` muestra qué claves tienen valor; `… ODOO_MASTER_PASSWORD --preguntar` la cambia
(sin `--preguntar`, al azar). Las de Postgres se cambian también dentro de Postgres; no edites el `.env` a mano.

## Bases de datos

- Gestor: http://localhost:8069/web/database/manager (crear, duplicar, copia de seguridad, restaurar, borrar), con la
  contraseña maestra `ODOO_MASTER_PASSWORD` de `~/servicios/.env`.
- Por consola: `docker exec -it odoo odoo db --help` y `docker exec -it odoo odoo module --help`.
- Los datos viven en los volúmenes Docker `postgres-datos` y `odoo-datos`, **fuera del repo**.
  ⚠️ `docker compose down -v` o `docker volume rm` los borran.
- Copia de una base: `~/servicios/copia-seguridad.sh [base]` (por defecto `claude-main`).
- Copia de todo Postgres: `docker exec postgres pg_dumpall -U admin > ~/proyectos/copias-seguridad/todo.sql`

## Cambios de código

- Python/XML de un módulo: `docker exec -it odoo odoo module upgrade -d <base> <modulo>` y `docker restart odoo`.
- `Dockerfile` u `odoo-entrypoint.sh`: `~/servicios/servicios.sh build odoo`. `.env`: `~/servicios/servicios.sh recrear odoo`.
- Módulo nuevo: crea `addons/<modulo>/` con su `__manifest__.py` y `docker restart odoo`.

Detalle para Claude en `CLAUDE.md` y en `.claude/skills/`; cada proyecto tiene además los suyos.
