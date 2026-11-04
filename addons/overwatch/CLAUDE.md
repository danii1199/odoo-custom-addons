# Overwatch (módulo de Odoo `overwatch`)

Pantalla de selección de héroes al estilo del juego (`/overwatch`) con favoritos por usuario y héroe aleatorio
(general o por rol, entre favoritos o todos); ficha de cada héroe con habilidades (con su vídeo), historia y vídeo
de origen (YouTube); galería de aspectos, gestos, poses de victoria, presentaciones y grafitis como la del juego.
Todo en el **sitio web** de Odoo (entrada «Overwatch» en su menú, como `dbd`); el backend es solo para editar.
Esta carpeta **es el módulo**. Docker, Postgres y bases son comunes (`../../CLAUDE.md`).

Decisiones del usuario (2026-11-02): acceso solo con el grupo del módulo (web y backend); cosméticos importados de
la wiki con la imagen **enlazada** (la carga el navegador; si deja de cargar, se sube una a mano en el backend).
Después (mismo día): la experiencia en el **frontend** (sitio web, con su item de menú), el backend para retocar.

## Estructura

```
models/       hero.py (ow.hero + ow.hero.chapter + ow.hero.ability con `stats`; ROLES, SUBROLES), cosmetic.py
              (ow.cosmetic; TYPES, RARITIES), pref.py (ow.pref: favoritos, uno por usuario), season.py (ow.season +
              ow.season.reward: míticos + ow.season.item: todas las recompensas por nivel), change.py (ow.change: Novedades; ow.update.mixin: botón
              «Buscar actualizaciones» en héroes, pases y novedades)
services/     importer.py (OverFast API → héroes; llama a wiki.py → cosméticos y a detalles.py → números de las
              habilidades; apunta las novedades), wiki.py (parser de las tablas), detalles.py ({{Ability_details}}
              de la página del héroe), seasons.py (temporadas de «Season/2022-2026» y «Season/<año>»), eventos.py (eventos de las
              temporadas recientes y sus fechas), pases.py (tablas de niveles
              de cada pase e imágenes por nombre de archivo),
              copia.py (exportar/cargar la copia local de datos/, también pases y números)
wizard/       import_wizard.py: «Actualizar catálogo» (Configuración): desde internet o desde la copia local
scripts/      actualizar_catalogo.py (internet, commit por héroe), exportar_catalogo.py, cargar_catalogo.py
datos/        copia del catálogo (no la carga el manifest): catalogo.json + retratos/<clave>.png, exportada de la
              base de pruebas el 2026-11-02 (54 héroes, 5.543 cosméticos, 492 habilidades, 186 capítulos)
data/         website_menu.xml («Overwatch» en el menú del sitio, para todos; vacía group_ids de todas las copias),
              ir_cron.xml (búsqueda diaria de actualizaciones, 5:00; noupdate: la migración 20.0.1.6.0 la pasó de
              semanal a diaria)
controllers/  main.py: /overwatch, /overwatch/heroe/<key>, /overwatch/pases, /overwatch/pases/<key>, /overwatch/eventos,
              /overwatch/novedades,
              POST JSON /overwatch/api/favorito
views/        hero_views.xml, cosmetic_views.xml (+ favoritos), import_views.xml, menus.xml,
              web_templates.xml (páginas del sitio: `overwatch.page_layout` llama a website.layout con
              pageName `ow-page` y la zona editable oe_structure_ow_top — no cambiar su id)
static/src/   css/overwatch.css (bajo .ow-app y #wrapwrap.ow-page), js/select.js (selección/favoritos/sorteo), js/hero.js
              (ficha y galería; datos de cada habilidad), js/seasons.js (vídeos de los míticos al verse)
tests/        test_overwatch.py: parser de la wiki, acceso por grupo, páginas y favoritos
```

## Fuentes (gratis, sin claves, User-Agent honesto)

- **OverFast API** (`overfast-api.tekrop.fr`, lee la web oficial), `locale=es-es`: héroes (rol, subrol, datos,
  vida), habilidades con vídeos mp4/webm de la CDN oficial, ventajas menores/mayores, historia por capítulos y
  `story.media.link` (YouTube de la historia de origen). El retrato se **descarga**; fondos, iconos, vídeos e
  imágenes de capítulos se enlazan a la CDN de Blizzard.
- **Wiki de Overwatch en Weird Gloop** (`overwatch.weirdgloop.org/api.php`, solo la API; **desde 2026-11-04**, antes
  `overwatch.fandom.com`): la comunidad se mudó y la de Fandom quedó sin actualizar (sin las tablas de los pases desde
  la Temporada 4 de 2026, sin D.Mon ni Doctrine, sin imágenes de lo reciente). Mismo formato de plantillas. Licencia
  CC BY-SA: las páginas de pases lo citan. Al pasar a Weird Gloop: cosméticos 5.545 → 5.929, sin imagen 272 → 70
  (lo que queda no existe en ninguna de las dos: «TBA», «???» o erratas de la wiki), D.Mon 24 y Doctrine 21.
  Plantillas: plantillas `Template:<Héroe> Skins|Emotes|VP|
  Intros|Sprays`. `{{CTS|n=…}}` = cabecera (rareza `{{rl|c/r/e/l/m|Evento}}` + precio), `{{CPB|h=Prefijo|n=Nombre|
  l=|c=columnas}}` = imagen `File:Prefijo l-o-n.png`, `{{CVB|…}}` = vídeo `.webm`. Varias cabeceras seguidas se
  reparten las columnas de las celdas de debajo; las filas sin cabecera heredan la de su columna. URLs con
  `prop=imageinfo` (50 títulos por petición). Pausa de 0,15 s y reintentos con 5xx/429.
  **La CDN de Fandom rechazaba las descargas desde el servidor: no intentar saltárselo en ninguna** (nada de User-Agent de
  navegador ni similares). Por eso se guarda la URL y la carga el navegador.
- `wiki_name` del héroe si el nombre en inglés no coincide con la wiki (`WIKI_NAMES` en importer.py).
- Resultado (2026-11-02, base de pruebas): 54 héroes, 5.543 cosméticos, 275 sin archivo en la wiki (salen con la
  inicial); Doctrine aún no tiene tablas en la wiki. Una segunda pasada da 0 nuevos. Los nombres se limpian de
  plantillas (`{{Locked}}`), negritas y marcas invisibles (`\u200e`, `\u3164`).
- El importador nunca borra; rehace habilidades y capítulos de cada héroe (vienen completos); cada héroe va en un
  savepoint (si falla, no queda a medias) y los errores salen en el resumen.

## Web

- **Pública** (decisión del usuario, 2026-11-03): rutas `website=True`, `auth="public"`; visitantes, portal e internos
  sin el grupo leen el catálogo (`ir.access` de lectura para `base.group_public`/`group_portal`/`group_user`) y ven
  todo en solo lectura. Favoritos solo con `group_ow_user` (`can_fav` en el JSON y en la plantilla: sin él no salen
  los botones, ni «Solo favoritos», ni el filtro «★ Favoritos»; la API devuelve 403). Cabecera y pie del sitio oscurecidos solo aquí (`#wrapwrap.ow-page`); la selección ocupa el alto que
  queda bajo la cabecera (`--ow-alto` desde select.js). Menú del sitio sin grupos (Odoo copia cada `website.menu`
  por sitio: para cambiar los grupos, escribe en todas las copias). Datos en `<script id="ow-data">`
  (JSON con `</` escapado). Estáticos con `?v=` = fecha del archivo más nuevo (se calcula al arrancar Odoo:
  reiniciar tras cambiar CSS/JS).
- Selección: plantilla por roles en una cuadrícula de 2 filas (`--cols` desde JS), casillas con esquinas cortadas
  (dos capas con `clip-path`), fondo del héroe con velo. Favoritos: botón, clic derecho o tecla F. Aleatorio: R.
- Ficha: pestañas con `#resumen`, `#historia`, `#aspectos`, `#gestos`, `#poses`, `#presentaciones`, `#grafitis`
  (responde a `hashchange`). La galería carga imágenes/vídeos al verse (IntersectionObserver); si uno falla, la
  inicial. YouTube con `youtube-nocookie.com`, el iframe se crea al abrir la pestaña.
- La vista grande de la galería y el vídeo de habilidades son `position: sticky` (acompañan al bajar). Por eso
  `.ow-app` usa `overflow-x: clip`, **no** `hidden` (hidden crea una zona de scroll propia y anula el sticky).

## Pases de batalla y novedades (2026-11-04, pedido del usuario)

- **Pases** (`/overwatch/pases`, enlazada desde la selección; backend «Pases de batalla»): una `ow.season` por
  temporada desde Overwatch 2 (antes no había pases): 20 de «Season/2022-2026» y las del arco anual («Season/2026»:
  Reign of Talon; `seasons.descargar` sigue con 2027… hasta la primera página que no exista). `key` = `ow2-s12` /
  `2026-s5`. Fechas de «(4 October 2022 - 6 December 2022)» y variantes; sin día → fecha vacía y `dates_text`.
  **Actual** = la última que ya ha empezado (`current()`); sin fecha de inicio = próxima. Míticos del bloque
  «New Battle Pass» (`{{rl|m|…}}`; aspecto, de mitad de temporada o arma), enlazados al aspecto del catálogo por
  héroe + nombre sin tildes (las armas no están en la galería: salen con la inicial). Imagen = la primera
  `[[File:…]]` del apartado (la hoja de ruta), enlazada como los cosméticos.
- **Números de las habilidades** (`ow.hero.ability.stats`, JSON `[[etiqueta, valor]]`): de los `{{Ability_details}}`
  de la página del héroe en la wiki, emparejados con OverFast **en inglés** (sin `locale`, mismo orden que en
  español). Solo los campos de `detalles.CAMPOS`, con unidades y frases comunes traducidas (el resto queda en
  inglés). Se saltan `removed` y «(old)». Si la wiki falla, se quedan los de antes. Web: enfriamiento, carga de la
  definitiva, munición y cargas bajo cada habilidad; todos al elegirla. Primera pasada: 396/492 con datos.
- **Novedades** (`ow.change`): el importador compara antes de escribir: vida, armadura, escudos, habilidades nuevas o
  retiradas, descripción y cada dato (no cuando llegan por primera vez); `seasons.guardar` apunta pases nuevos y
  míticos nuevos en un pase que ya existía (la wiki publica el de mitad de temporada más tarde). La primera carga
  no llena Novedades. `batch` = fecha de la búsqueda.
- **Botón «Buscar actualizaciones»** (solo administrador; cabecera de Héroes, Pases y Novedades): héroes +
  números + pases, **sin cosméticos** (~40 s; los cosméticos con «Actualizar catálogo», que también hace todo lo
  anterior). Termina con un aviso y abre las novedades de esa búsqueda.

- **Todas las recompensas** (`ow.season.item`, `/overwatch/pases/<key>`, con filtro por tipo): tablas de niveles de
  «List of previous Battle Passes/2022-2026», «List of previous Battle Passes/<año>» y «Battle Pass» (el actual de
  la wiki, que se reconoce por el nombre de la temporada). Filas `|nivel`, `|gratis`, `|prémium`; tras «Prestige
  Tiers», una sola celda (`colspan`). `{{rl|rareza|Nombre|tipo|Héroe}}` (tipos en `pases.TIPOS`) o texto
  («{{Credits}} 250» → «250 créditos»). 2026-11-04: 2.285 recompensas de 23 pases; **la wiki aún no tenía las tablas de
  las temporadas 4 y 5 de 2026** (la web lo dice; se cargan solas cuando salgan y quedan en Novedades como
  «recompensas publicadas», salvo en la primera carga).
- **Imágenes**: cosmético de la galería si es de un héroe (sin tildes y quitando el nombre del héroe, que la wiki
  añade en algunos grafitis); si no, nombres de archivo de la wiki por tipo (`pases.ARCHIVOS`: `PI <n>.png`,
  `NameCard <n>.png`, `WeaponCharm <n>.png`, `<héroe> Weapon Skin <n>.png`…, con `ALIAS` como «S76») pedidos de 50
  en 50 con `urls_archivos`. Las temporadas sin hoja de ruta usan la imagen de su mítico. Frases, títulos y
  créditos no tienen imagen (símbolo). Resultado: 93 % de lo que puede tenerla, 42/45 míticos.
- **Novedades en la web** (`/overwatch/novedades`, pública como el resto: `ir.access` de lectura para visitantes,
  portal e internos), agrupadas por búsqueda, con enlace al héroe o al pase.
- **Pases por caminos** (desde la Temporada 4 de 2026): la wiki pone una tabla por camino («… Battle Pass (1)»,
  «(2)»…, «(Mythic)»): `ow.season.item.section` = «Camino inicial», «Camino 1…5», «Camino de prismas», «Prestigio»;
  el nivel cuenta dentro de su camino. Los míticos de 2026 en «Season/2026» van bajo «New {{Raritylink|m|text=Mythic}}
  Skins» con `{{Raritylink|m|text=Nombre}}` (además de `{{rl|m|…}}`).
- **Pulsar una recompensa**: si está en la galería de un héroe, es un enlace a `/overwatch/heroe/<clave>#<tipo>/<id>`
  (hero.js abre esa pestaña con el cosmético elegido y a la vista); si no, pero tiene imagen, se abre en grande
  (`<dialog class="ow-lightbox">`, seasons.js). Los míticos de las tarjetas, igual.
- **Contexto `ow_fuente_nueva`**: no apunta como novedad los cambios en los números de las habilidades (se usó al pasar
  a Weird Gloop: cambia la redacción, no el juego).
- **Búsqueda diaria** (2026-11-04, antes semanal; `cron_check_updates` → `ow.change._cron_check_updates`, como
  superusuario): lo del botón + cosméticos + eventos, commit por héroe; ~3 min. Se cambia o desactiva en Ajustes →
  Técnico → Acciones planificadas.
- **Eventos** (`ow.event`, `/overwatch/eventos`, arriba en `/overwatch/pases`; backend «Eventos»): los enlaza el
  apartado de cada temporada (puntos «Events/Collaborations/…Event» y líneas sueltas «[[Overwatch x …]]»,
  `eventos.enlaces_eventos`). Solo temporadas de los últimos `RECIENTES` días (pocas peticiones al día). Las fechas,
  del texto de la página de cada evento (no hay ficha fija): rangos «February 10 to March 31, 2026», «*2026: October 6
  to November 3», «October 6–November 2»…, el que cae en su temporada. Sin ninguno: las de la temporada y `approx`,
  y entonces el estado es **«Sin fechas confirmadas»**, nunca «Activo» (Graveyard Games salía activo hasta el 8 de
  diciembre y había acabado el 2 de noviembre). Un evento nuevo = novedad `event_new` (la primera carga no).
  Blizzard solo da las fechas en el texto de sus artículos: no se usa.
- **Overwatch Countdown** (2026-11-04, 20.0.1.7.0; `services/countdown.py`): el recuadro «Event Countdown» de la
  portada de la wiki no sale de sus páginas sino de `MediaWiki:Countdown.js`, que lee `owcountdown.com/api/events`
  (pública, sin clave; `www.` y de respaldo `preview.`). Da lo que está en curso o por empezar con **hora exacta**
  (UTC), descripción y fuente (notas del parche), sin imágenes ni historial. Se salta la etiqueta «Season» (la
  temporada ya es el pase). `guardar_countdown` (después de la wiki) actualiza por `countdown_id`, o se une al evento
  de la wiki con el mismo nombre (`_nombre`) en esa temporada; si no, `owc:<id>`. Con `countdown_id` la wiki solo
  pone imagen y página, no las fechas. Estado al segundo con `start_at`/`end_at` (el `_search_state` va por días: el
  controlador reparte con `_eventos`). Web: cuenta atrás en vivo (`data-countdown`, seasons.js), fechas en hora de
  Madrid. Los «sin fechas confirmadas» ya no salen en la franja de /overwatch/pases, solo en /overwatch/eventos.
- **Tier Hack** (2026-11-04, 20.0.1.8.0; `services/hack.py`, `ow.season.hack`): desde la Temporada 4 de 2026 se
  puede cambiar un aspecto legendario del pase por otro de una lista. La wiki solo la da para el pase actual
  (apartado «=== Tier Hack ===» de «Battle Pass», «Current Skin Pool is:») y reescribe la página cada temporada:
  las de temporadas terminadas salen de la revisión de la víspera de su fin (`rvstart`), aceptada solo si su primera
  cabecera «==Season N: Nombre==» es esa temporada. Una terminada con lista ya no se pide (a diario, solo la actual);
  sin datos no se borra nada; si cambia, novedad «Tier Hack cambiado/publicado». Emparejado con la galería por
  `_nombre` (solo letras y números: «Class President 76» = «Class President: 76»); si no, imagen por archivo de la
  wiki. Web: sección «Tier Hack» arriba en `/overwatch/pases/<key>`; backend: pestaña en el pase.
- **Carteles ampliables** (`img.ow-zoomable`: hoja de ruta de cada pase, imagen de cada evento): `<dialog class="ow-zoom">`
  con rueda, doble clic y botones para el zoom (1×–8×, alrededor del puntero) y arrastre para moverse (seasons.js).

## Actualizar (desde la raíz del repo)

```bash
sg docker -c "docker exec -i odoo odoo module upgrade -d <base> overwatch && docker restart odoo"
sg docker -c "docker exec -i odoo odoo shell -d <base> --no-http < addons/overwatch/scripts/actualizar_catalogo.py"
```
(la importación completa tarda ~2-3 min). Sin internet, desde la copia de `datos/`:
`... odoo shell -d <base> --no-http < addons/overwatch/scripts/cargar_catalogo.py`. Para renovar la copia:
`exportar_catalogo.py` (escribe en /tmp/ow-catalogo del contenedor) y
`rm -rf addons/overwatch/datos && sg docker -c "docker cp odoo:/tmp/ow-catalogo addons/overwatch/datos"`.

## Pendiente / ideas

- Tarjetas de nombre, amuletos e iconos de jugador (no están en esas plantillas), sorteo de skin aleatoria,
  traducir los nombres de los cosméticos (la wiki está en inglés).
