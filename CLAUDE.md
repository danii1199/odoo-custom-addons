# proyectitos (repo `claude-test`)

Un **Odoo 20 Community** común donde el usuario va añadiendo sus propios módulos. Cada proyecto es una carpeta de
`addons/` (los extra-addons) que **es el propio módulo** (`__manifest__.py`, `models/`… directamente dentro), su propia memoria (`addons/<proyecto>/CLAUDE.md`) y sus propias
skills (`addons/<proyecto>/.claude/skills`).
Postgres y Odoo son **comunes**; sus compose viven fuera del repo, en `~/servicios/` (solo en este PC). Todo en español: código, comentarios, interfaz y documentación.

## Estructura

```
Dockerfile             FROM odoo:20 + dependencias Python de los módulos (el código NO va en la imagen)
odoo-entrypoint.sh     genera /etc/odoo/odoo.conf: odoo.conf + addons_path + admin_passwd, y lanza el entrypoint oficial
odoo.conf              configuración de Odoo sin secretos (montada como /etc/odoo/odoo.base.conf)
addons/                extra-addons: cada carpeta es un módulo (nombre técnico = nombre de la carpeta)
  fuertafit/           módulo `fuertafit` (Mi rutina Fuerta, web en el sitio web de Odoo) + scripts/, CLAUDE.md, skills
  dbd/                 módulo `dbd` (enciclopedia de Dead by Daylight, web /dbd), separado de fuertafit
  menu_inicio/         módulo `menu_inicio`: pantalla de inicio con cuadrícula de apps (estilo Enterprise, código propio)
  gastos/              módulo `gastos`: gastos compartidos tipo Splitwise (backend + web /gastos con permiso propio, correo y webhook n8n)
  overwatch/           módulo `overwatch`: selección de héroes al estilo del juego en el sitio web (/overwatch), favoritos, aleatorio, galería; datos/ con el catálogo exportado
  inicio_web/          módulo `inicio_web`: portada del sitio web (reloj, saludo, tarjetas por proyecto) y menú del sitio personalizable por usuario
  myspoty/             futuro módulo `myspoty` (aún sin manifest; app antigua en app/), CLAUDE.md y skills
```

Fuera del repo, **sin git** (decisión del usuario), en `~/servicios/`: la infraestructura Docker de este PC.

```
servicios.sh           centralizador: estado / up / down / restart / recrear / build / pull / logs (todos o los indicados)
.env / .env.example    contraseñas: Postgres, rol `odoo`, contraseña maestra, ANTHROPIC_API_KEY opcional (enlazado en postgres/ y odoo/)
postgres/              compose propio (proyecto `postgres`) + init/ (primera vez: roles `odoo` CREATEDB y `rutinas`, base `rutinas`)
odoo/                  compose propio (proyecto `odoo`): build desde este repo, monta odoo.conf y addons/ (ODOO_REPO para otra ruta)
vaultwarden/           compose propio (proyecto `vaultwarden`, puerto 8080) + vw-data/ (de root: la bóveda cifrada)
instalar.sh            instala TODO en un Mint/Ubuntu vacío (apt, Docker, Claude Code, repo, servicios, .env al azar, copias .zip)
preparar-mudanza.sh    ~/proyectitos/mudanza-<fecha>/: copias + repo y servicios en tar.gz (sin .env ni vw-data) + instalar.sh
ajustar-env.sh         cambia una clave del .env sin mostrarla (+ ALTER ROLE en Postgres y recrear postgres y odoo)
copia-seguridad.sh     copia de una base (por defecto claude-main) en ~/proyectitos/copias-seguridad/<base>-<fecha>.zip
```

- `addons/` se monta **en solo lectura** en `/mnt/extra-addons`. `odoo-entrypoint.sh` mete en `addons_path` cada
  `addons_path` `/mnt/extra-addons` en cuanto hay algún módulo: uno nuevo no necesita tocar el compose, y una
  carpeta sin `__manifest__.py` (como `myspoty` ahora) simplemente se ignora.
- Dentro del módulo pueden ir `scripts/`, `CLAUDE.md`, `.claude/`…: Odoo solo carga lo que importa el manifest.
- Al trabajar en un proyecto, lee su `CLAUDE.md` y usa sus skills (se cargan solas al tocar archivos de esa carpeta).

## Docker (skill `odoo-docker`)

- Siempre `sg docker -c "..."` (la sesión puede no tener aún el grupo `docker`). `docker exec odoo …`,
  `docker restart odoo`, `docker logs odoo` van por nombre de contenedor y valen desde cualquier carpeta; arrancar,
  parar, recrear o reconstruir, con `~/servicios/servicios.sh` (un proyecto Compose por carpeta, independientes).
- Contenedores `postgres`, `odoo` y `vaultwarden`. Odoo **no** depende de Postgres en Compose: lo busca por la red
  externa `proyectitos` (`db_host = postgres`). Volúmenes `postgres-datos` (bases de datos) y `odoo-datos`
  (filestore y sesiones), con nombre fijo: no dependen de ninguna carpeta. Compose avisa de que "were created for
  project proyectitos": es normal, se crearon antes de separar los proyectos (2026-10-30). **No** pongas
  `external: true` ni los borres.
- Odoo en `http://IP-de-este-PC:8069` (toda la red local, decisión del usuario). Postgres solo en `127.0.0.1:5432`.
  Vaultwarden solo por Tailscale: `https://<este-pc>.<red>.ts.net:8443` (`sudo tailscale serve --bg --https=8443 8080`);
  su 8080 escucha solo en `127.0.0.1` (decisión del usuario: nada de HTTP en la red local).
  Desde otros equipos, Odoo por Tailscale con HTTPS (`sudo tailscale serve --bg 8069`, `proxy_mode = True`): sin HTTPS,
  fuera de `localhost`, el backend de Odoo 20 se queda en blanco (contexto no seguro).
- `restart: unless-stopped` (Vaultwarden `always`): Postgres y Odoo arrancan solos al encender el PC (salvo que se paren a mano).
- Si se recrea la carpeta `addons/` (reestructurar, clonar de nuevo…), el contenedor sigue viendo la antigua
  (`/mnt/extra-addons` vacío): `docker restart odoo`.
- Cambiar código Python o XML de un módulo: `restart` + actualizar el módulo en su base de datos (no hace falta `--build`).
  `servicios.sh build odoo` si cambian `Dockerfile` u `odoo-entrypoint.sh` (van dentro de la imagen). Cambiar
  `~/servicios/.env` o un compose: `servicios.sh recrear <servicio>`.

## Bases de datos (skill `odoo-bases-de-datos`)

- Multi-base: `list_db = True`, selector en `/web/login` y gestor en `/web/database/manager`, protegido por la
  contraseña maestra (`ODOO_MASTER_PASSWORD` en `~/servicios/.env`; **no la muestres**). Odoo solo lista las bases cuyo dueño es `odoo`.
- Por consola: `odoo db {init,duplicate,dump,load,rename,drop}` y `odoo module {install,upgrade,uninstall,list}`
  dentro del contenedor (`docker exec -i odoo odoo ...`). Gestionan también el filestore.
- Bases actuales (2026-10-05): `claude-main` (la principal, con fuertafit, menu_inicio y dbd con el catálogo completo: **datos reales**),
  `claude-test` (pruebas del usuario: fuertafit, menu_inicio y dbd con el catálogo completo) y `rutinas` (web
  antigua de fuertafit, solo para migrar). La base `fuertafit` ya no existe. La de la app antigua de myspoty ya no
  importa al usuario.
- En Odoo 20 el servicio `db` de `/jsonrpc` ya no existe: usa el gestor web o el CLI.

## Odoo 20: convenciones de los módulos (ver `addons/fuertafit` como ejemplo)

- Manifest: `version` `20.0.x.y.z`, `author` `danii1199`, `license` `LGPL-3`, `depends` mínimo.
- Permisos en `security/ir.access.csv` (modelo `ir.access`, nuevo en 20): columnas
  `id,name,model_id,group_id/id,operation,domain`; `model_id` es el nombre del modelo (`fuerta.routine`, no
  `model_fuerta_routine`); `operation` tipo `r`/`crud`; el dominio sustituye a las `ir.rule`.
- QWeb: un `t-call` solo pasa los valores del render y sus atributos (`<t t-call="x" rec="c"/>`); un `t-set` dentro
  del cuerpo del `t-call` **no** llega a la plantilla llamada (tampoco `additional_title` a `website.layout`).
- **Acceso por módulo**: cada módulo tiene su grupo en `security/groups.xml` (`ir.module.category` +
  `res.groups.privilege` + `res.groups` que implica `base.group_user`, con `user_ids` = `base.user_admin`, que es Dani).
  `ir.access.csv`, el menú raíz (`groups=`), las rutas web privadas (`has_group`) y el menú del sitio web usan ese
  grupo; así un usuario nuevo no ve nada hasta que se le da acceso en Ajustes → Usuarios. Excepciones (decisión del
  usuario, 2026-11-03): las webs de `dbd` y `overwatch` son **públicas en solo lectura** (builds y favoritos piden
  cuenta/grupo), y `gastos` tiene un grupo web sin tipo de usuario (`group_gastos_web`) que vale para portal.
  Cada usuario puede ocultarse entradas del menú del sitio desde la portada (`inicio_web`). Odoo copia cada
  `website.menu` por sitio web: para cambiarle los grupos, escribe en todas las copias (busca por `manual_url`).
- Un módulo que añade un campo guardado a `res.users`: `odoo module upgrade` falla la primera vez (lee los usuarios
  con el campo nuevo antes de crear la columna); usa `odoo -d <base> -u <módulo> --stop-after-init --http-port=8098`.
- Restricciones SQL con `models.Constraint("UNIQUE (...)", "mensaje")` (no `_sql_constraints`).
- Campos Binary: el valor es un `BinaryValue` (`.decode()`, `.content`), no base64; al escribir, str base64 o BinaryValue.
- Botones de cabecera en listas: `<header><button ... display="always"/></header>`. URLs de backend: `/odoo/action-<xmlid>`.
- JS del backend (OWL 3): `proxy`/`signal` en vez de `useState`/`reactive`, **sin `static props`** (rompe todo el
  webclient), refs con `signal.ref()`, iconos `<i class="oi" data-icon="..."/>`. Detalles en `addons/menu_inicio/CLAUDE.md`.
- Páginas web: `http.route(..., website=True)` + plantilla con `t-call="website.layout"` y zonas `oe_structure`
  editables; CSS propio siempre con prefijo (Bootstrap del sitio usa `.row`, `header`, `nav`, `main`…).
- Vistas `<list>` (no `<tree>`), `invisible="expr"` (no `attrs`). `ir.config_parameter`: `get_str`/`set_str`.
- Tareas periódicas con `ir.cron` en `data/` (`max_cron_threads = 1`). Fechas de "hoy" en `Europe/Madrid` (TZ del contenedor).
- Ante la duda sobre una API de Odoo 20, mira el código real del contenedor:
  `docker exec -i odoo grep -rn ... /usr/lib/python3/dist-packages/odoo` en vez de suponer por versiones anteriores.

## Normas

- **No tocar datos reales** (base `claude-main`) sin pedirlo: prueba en una copia (skill `probar-modulo`).
  Nunca borres, restaures ni sobrescribas una base de datos o volumen sin confirmación explícita.
- No leer ni mostrar `.env`, contraseñas ni tokens; para cambiarlos, skill `ajustar-env`. Para usar un valor: `grep '^X=' ~/servicios/.env | cut -d= -f2-` dentro de un comando.
- Nada de funciones que obliguen a pagar APIs (el usuario no quiere); preferir reglas deterministas.
- Nuevo proyecto o módulo: skill `nuevo-modulo` (carpeta, montaje, CLAUDE.md y skills propias).
- Sin node ni venv en el sistema: lo que haga falta, en contenedores (`node:20-alpine`, la propia imagen de Odoo).
