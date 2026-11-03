# Dead by Daylight (módulo de Odoo `dbd`)

Enciclopedia del videojuego Dead by Daylight: supervivientes, asesinos, perks, complementos, reinos/mapas y ofrendas.
Se edita en el backend (menú **Dead by Daylight**, solo con el grupo del módulo) y se publica en el sitio web en `/dbd`
con un diseño inspirado en el juego. Esta carpeta (`addons/dbd`) **es el módulo**. Docker, Postgres y bases de datos
son comunes (`../../CLAUDE.md`, skills `odoo-docker`, `odoo-bases-de-datos`, `probar-modulo`).

Decisión del usuario (2026-10-05): portal **separado de rutifuerta** (su propia base de datos y sitio web, portada
`/dbd`). El catálogo completo está en la base real (importado el 2026-10-05; hay copia previa) y en la base de pruebas.

## Estructura

```
models/       common.py (RARITIES, DIFFICULTIES, ROLES y dbd.character.mixin), survivor.py, killer.py,
              perk.py (dbd.perk + dbd.perk.tag), addon.py, realm.py (dbd.realm + dbd.map), offering.py
views/        character_views.xml (supervivientes y asesinos), perk_views.xml, item_views.xml (complementos y
              ofrendas), map_views.xml, menus.xml, web_templates.xml (las páginas de /dbd)
services/     importer.py: importa/actualiza todo el catálogo (datos de dbd.tricky.lol + imágenes de wiki.gg)
wizard/       import_wizard.py: botón «Actualizar catálogo» (Configuración) que llama al importador
scripts/      actualizar_catalogo.py: lo mismo desde `odoo shell` (sin límite de tiempo; para la primera carga)
controllers/  main.py: rutas públicas /dbd, /dbd/supervivientes[/<slug>], /dbd/asesinos[/<slug>], /dbd/perks,
              /dbd/complementos, /dbd/ofrendas, /dbd/mapas, /dbd/build, /dbd/aleatoria; API /dbd/api/catalogo
              (pública) y /dbd/api/builds[/guardar|/borrar] (sesión + grupo, POST solo JSON)
tests/        test_builds.py: validación, API, login obligatorio, públicas/privadas, sorteo (HttpCase; admin/admin
              y un usuario de portal → solo en una base desechable)
data/         datos_iniciales.xml (ejemplos: personajes de 2016, sus perks, 3 reinos…; noupdate),
              website_menu.xml («Dead by Daylight» en el menú del sitio)
security/     groups.xml: dbd.group_dbd_user (ve el backend) y dbd.group_dbd_manager (edita e importa; Dani);
              ir.access.csv: lectura para public/portal (la web) y group_dbd_user, todo para group_dbd_manager
static/src/   css/dbd.css (bajo .dbd-app y #wrapwrap.dbd-page; .dbd-picker y .dbd-tip van en el body),
              js/dbd.js (filtros), js/loadout.js (DbdLoadout: catálogo, casillas, selector, tooltip, URL),
              js/build.js (editor), js/random.js (ruleta)
```

## Modelo de datos

- `dbd.survivor` / `dbd.killer` heredan `dbd.character.mixin` (nombre, retrato, capítulo, fecha, licenciado,
  dificultad, historia). El asesino añade nombre real, poder, velocidad, radio de terror, altura y `addon_ids`.
- `dbd.perk`: `role` (survivor/killer) se calcula del dueño (`survivor_id` o `killer_id`); sin dueño = perk general
  (`is_general`). Restricción: nunca dos dueños ni dueño del otro bando. Etiquetas `dbd.perk.tag`.
- `dbd.addon`: de asesino (`killer_id`) o de objeto de superviviente (`item_type`), con `rarity`.
- `dbd.offering`: `role` survivor/killer/both, `category`, `rarity`, `realm_id` en las de reino.
- `dbd.item`: objetos de superviviente (`/api/items` con `type: item`), con rareza y `event`.
- `dbd.build`: build del usuario (`user_id`, dominio «solo las propias» en ir.access; el administrador lee todas):
  bando, personaje, 4 perks del bando, objeto (superviviente) + 2 complementos de su tipo, o 2 complementos del
  asesino (su poder va con el asesino), ofrenda del bando o «ambos». `_check_build` lo valida todo;
  `save_from_web`/`to_web` son el formato del editor web.
- `dbd.realm` agrupa `dbd.map`. `rarity_order` (almacenado) ordena por rareza real, no alfabética.
- `dbd_key` (de `dbd.external.mixin`, única por modelo): clave en la fuente externa. El importador actualiza por
  ella; si no existe, empareja por nombre (sin mayúsculas ni comillas tipográficas) con registros sin clave.
- Imágenes: un campo `image` por modelo (y `power_image` en el asesino); la web las sirve en `/web/image/<modelo>/<id>/image` y, si no hay,
  pinta la inicial. Nombres del juego en inglés; textos en español.

## Web

- Páginas `website=True`, `auth="public"`: los visitantes sin sesión leen gracias a `ir.access` (no hay `sudo`).
- Plantillas: `dbd.layout` (llama a `website.layout` con `pageName="'dbd-page'"`, barra de pestañas propia,
  zona editable `oe_structure_dbd_top` — no cambiar su id), `dbd.picture`, `dbd.perk_card`, `dbd.item_card`.
- **Odoo 20**: un `t-call` solo recibe los valores del render y sus **atributos** (`<t t-call="dbd.picture" rec="c"/>`);
  un `t-set` dentro del cuerpo del `t-call` no llega a la plantilla llamada.
- Filtros: `.dbd-filterable` > `.dbd-chips[data-filter=X]` (botones con `data-value`, valores separados por espacios)
  filtran los `.dbd-item` por su `data-X`; `.dbd-search` busca en `data-search`.
- CSS: colores de rareza en variables `--r-<clave>` (mismas claves que `RARITIES`). Cabecera y pie del sitio se
  oscurecen solo en estas páginas (`#wrapwrap.dbd-page`). Estáticos con `?v=` (fecha del archivo más nuevo).

## Actualizar (desde la raíz del repo)

```bash
sg docker -c "docker exec -i odoo odoo module upgrade -d <base> dbd && docker restart odoo"
sg docker -c "docker exec -i odoo odoo shell -d <base> --no-http < addons/dbd/scripts/actualizar_catalogo.py"
```
Solo CSS/JS: recargar el navegador (el `?v=` cambia al reiniciar Odoo).

## Importar el catálogo (services/importer.py)

- **Datos**: API pública de `dbd.tricky.lol` (`/api/characters`, `perks`, `addons`, `items`, `offerings`, `maps`,
  `dlc`). Solo la API: sus páginas web tienen protección anti-bots (403) y no se intenta saltarla.
  Personajes: rol, dificultad, altura, `bio`, `story` → historia; asesino: velocidad y radio de terror desde
  `tunables` (cm → m), poder desde `items[character.item]`; capítulo y fecha desde `dlc`. Perks: el dueño es
  `characters[str(perk.character)]`; marcadores `{Tunable.X.Clave}` → valores por nivel, `{Keyword.X}`, `{Input.X}`.
  Complementos de asesino: su `parents[0]` es el `item` del asesino. Rarezas: `veryrare` → muy rara, `visceral` →
  ultra rara. Variantes de mapa con el mismo nombre → «Coal Tower II».
- **Imágenes**: wiki oficial `deadbydaylight.wiki.gg` (API de MediaWiki, User-Agent honesto). Por orden: archivo con
  el nombre del juego (`IconPerks_adrenaline.png`, mapas sin el número de variante), archivo con el nombre en
  camelCase (`IconAddon_high-EndSapphireLens.png`) e imagen principal de la página del elemento.
  **No usar la wiki de Fandom**: su CDN bloquea lo que no es un navegador. Los repos de GitHub con iconos o son
  fan-art (N7Maxxi) o están desfasados.
- Nunca borra. Solo descarga las imágenes que faltan (salvo «volver a descargar todas»). Primera carga
  (~1.600 imágenes, ~1 min): mejor con el script de `scripts/` que con el botón.
- Resultado (2026-10-05): 54 supervivientes, 44 asesinos, 321 perks, 942 complementos, 125 ofrendas, 21 reinos,
  58 mapas; 20 imágenes sin encontrar (complementos con el mismo nombre en varios asesinos, 5 poderes y 2 ofrendas
  de evento): la web pinta la inicial.
- Los ejemplos de `data/datos_iniciales.xml` se emparejan por nombre; en la base de pruebas se **archivaron** (no
  borraron) 4 que estaban duplicados o ya no existen en el juego; en la real se emparejaron todos.

## Builds (2026-10-05)

- Menú **Builds**: «Mis builds» (backend), «Crear build» (/dbd/build), «Build aleatoria» (/dbd/aleatoria) y
  «Builds publicadas» (/dbd/builds). En la web, también pestañas del portal. JS de la lista y el visor: builds.js.
- **Crear build exige sesión** (el controlador manda a `/web/login?redirect=…`). La ruleta y la lista no. Pueden
  tener builds los usuarios con `group_dbd_user` y los de **portal**. Abrir una propia: `/dbd/build?id=N`.
- **Sin registro libre** (decisión del usuario, 2026-11-03: Odoo está abierto a internet): ya no hay «Crear cuenta»;
  las cuentas de portal se crean por invitación. En Odoo 20 cada `website` tiene `auth_signup_uninvited`, que
  **manda** sobre el parámetro general `auth_signup.invitation_scope`; el módulo ya no lo toca (se quitó
  `data/signup.xml`, que lo ponía en `b2c` al instalar). No lo vuelvas a abrir sin que lo pida.
- **Públicas/privadas**: `is_public`; las públicas salen en `/dbd/builds` y se ven en `/dbd/builds/ver?id=N` sin
  sesión (ir.access: lectura con dominio `is_public` para público, portal y usuarios). `author_name` se guarda en
  la build porque quien la ve no puede leer `res.users`. Enlaces compartidos: al visor (`?id=` si es pública, o la
  build en la URL `?r=s|k&c=&p=a.b.c.d&i=&a=x.y&o=&n=`). «Copiar y editar» → editor como build nueva y privada.
- **Personajes del sorteo**: `dbd.random.pref` (uno por usuario) guarda los **excluidos**, así los personajes
  nuevos entran solos. Sin sesión, la selección dura lo que la página.
- Ruleta: casilla a casilla, se frena hasta pararse; «Siguiente casilla»; clic = volver a girar esa (y sus
  complementos si cambia el objeto o el asesino). Precarga las imágenes para no girar en blanco.
- Reglas comunes a editor y ruleta: `DbdLoadout.options()` (qué vale en cada casilla) y `sanitize()`.
- Sin `alert/confirm`: borrar pide un segundo clic. Descripciones en el tooltip (`[data-tip-kind][data-tip-id]`).

## Pendiente / ideas

- «Favoritas» o votos en las builds públicas, filtros de la ruleta por etiquetas de perk.

## Normas

- Si añades un campo, añádelo en el backend **y** en la web. Código y textos en español.
- Pruebas: skill `probar-cambios` (base de pruebas); tests: `odoo db init dbd_tests` y
  `odoo -d dbd_tests --db-filter='^dbd_tests$' -i dbd --test-enable --test-tags /dbd --stop-after-init --http-port=8099 > log` (sin `| head`:
  cortar la salida deja el proceso vivo ocupando el puerto), luego `odoo db drop dbd_tests`.
