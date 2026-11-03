# odoo-custom-addons

Un **Odoo 20 Community** común donde el usuario va añadiendo sus propios módulos. Cada proyecto es una carpeta de
`addons/` (los extra-addons) que **es el propio módulo** (`__manifest__.py`, `models/`… directamente dentro), su propia memoria (`addons/<proyecto>/CLAUDE.md`) y sus propias
skills (`addons/<proyecto>/.claude/skills`).
Postgres y Odoo son **comunes**; su despliegue (Compose, `.env`, scripts) vive fuera del repo, en la carpeta de
servicios del usuario (ruta en la memoria de Claude). El repo es **público**. Todo en español: código, comentarios, interfaz y documentación.

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

- `addons/` se monta **en solo lectura** en `/mnt/extra-addons`. `odoo-entrypoint.sh` mete en `addons_path` cada
  `addons_path` `/mnt/extra-addons` en cuanto hay algún módulo: uno nuevo no necesita tocar el compose, y una
  carpeta sin `__manifest__.py` (como `myspoty` ahora) simplemente se ignora.
- Dentro del módulo pueden ir `scripts/`, `CLAUDE.md`, `.claude/`…: Odoo solo carga lo que importa el manifest.
- Al trabajar en un proyecto, lee su `CLAUDE.md` y usa sus skills (se cargan solas al tocar archivos de esa carpeta).

## Docker (skill `odoo-docker`)

- Siempre `sg docker -c "..."` (la sesión puede no tener aún el grupo `docker`). `docker exec odoo …`,
  `docker restart odoo`, `docker logs odoo` van por nombre de contenedor y valen desde cualquier carpeta; arrancar,
  parar, recrear o reconstruir, con `servicios.sh` de la carpeta de servicios (skill `odoo-docker`).
- Contenedores `postgres` y `odoo`; los datos viven en volúmenes Docker, fuera del repo. **No** los borres.
- Odoo 20 necesita HTTPS fuera de `localhost` (si no, el backend se queda en blanco): por eso `proxy_mode = True`.
- Si se recrea la carpeta `addons/` (reestructurar, clonar de nuevo…), el contenedor sigue viendo la antigua
  (`/mnt/extra-addons` vacío): `docker restart odoo`.
- Cambiar código Python o XML de un módulo: `restart` + actualizar el módulo en su base de datos (no hace falta `--build`).
  Si cambian `Dockerfile` u `odoo-entrypoint.sh` (van dentro de la imagen), hay que reconstruirla.

## Bases de datos (skill `odoo-bases-de-datos`)

- Multi-base: `list_db = True`, selector en `/web/login` y gestor en `/web/database/manager`, protegido por la
  contraseña maestra (**no la muestres**). Odoo solo lista las bases cuyo dueño es `odoo`.
- Por consola: `odoo db {init,duplicate,dump,load,rename,drop}` y `odoo module {install,upgrade,uninstall,list}`
  dentro del contenedor (`docker exec -i odoo odoo ...`). Gestionan también el filestore.
- Hay una **base real** (datos del usuario) y una **base de pruebas**; sus nombres, en la memoria de Claude
  (si no los sabes, pregunta antes de tocar nada).
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

- **No tocar datos reales** (la base real) sin pedirlo: prueba en una copia (skill `probar-modulo`).
  Nunca borres, restaures ni sobrescribas una base de datos o volumen sin confirmación explícita.
- No leer ni mostrar `.env`, contraseñas ni tokens; para cambiarlos, skill `ajustar-env`.
- Nada de funciones que obliguen a pagar APIs (el usuario no quiere); preferir reglas deterministas.
- El repo es **público**: no escribas en archivos versionados rutas de la infraestructura, del `.env`, puertos,
  red, nombres de bases ni contraseñas.
- Nuevo proyecto o módulo: skill `nuevo-modulo` (carpeta, montaje, CLAUDE.md y skills propias).
- Sin node ni venv en el sistema: lo que haga falta, en contenedores (`node:20-alpine`, la propia imagen de Odoo).
