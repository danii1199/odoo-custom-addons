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
models/       hero.py (ow.hero + ow.hero.chapter + ow.hero.ability; ROLES, SUBROLES), cosmetic.py (ow.cosmetic;
              TYPES, RARITIES), pref.py (ow.pref: favoritos, uno por usuario)
services/     importer.py (OverFast API → héroes; llama a wiki.py → cosméticos), wiki.py (parser de las tablas),
              copia.py (exportar/cargar la copia local de datos/)
wizard/       import_wizard.py: «Actualizar catálogo» (Configuración): desde internet o desde la copia local
scripts/      actualizar_catalogo.py (internet, commit por héroe), exportar_catalogo.py, cargar_catalogo.py
datos/        copia del catálogo (no la carga el manifest): catalogo.json + retratos/<clave>.png, exportada de la
              base de pruebas el 2026-11-02 (54 héroes, 5.543 cosméticos, 492 habilidades, 186 capítulos)
data/         website_menu.xml («Overwatch» en el menú del sitio, para todos; vacía group_ids de todas las copias)
controllers/  main.py: /overwatch, /overwatch/heroe/<key>, POST JSON /overwatch/api/favorito
views/        hero_views.xml, cosmetic_views.xml (+ favoritos), import_views.xml, menus.xml,
              web_templates.xml (páginas del sitio: `overwatch.page_layout` llama a website.layout con
              pageName `ow-page` y la zona editable oe_structure_ow_top — no cambiar su id)
static/src/   css/overwatch.css (bajo .ow-app y #wrapwrap.ow-page), js/select.js (selección/favoritos/sorteo), js/hero.js (ficha y galería)
tests/        test_overwatch.py: parser de la wiki, acceso por grupo, páginas y favoritos
```

## Fuentes (gratis, sin claves, User-Agent honesto)

- **OverFast API** (`overfast-api.tekrop.fr`, lee la web oficial), `locale=es-es`: héroes (rol, subrol, datos,
  vida), habilidades con vídeos mp4/webm de la CDN oficial, ventajas menores/mayores, historia por capítulos y
  `story.media.link` (YouTube de la historia de origen). El retrato se **descarga**; fondos, iconos, vídeos e
  imágenes de capítulos se enlazan a la CDN de Blizzard.
- **Wiki de Overwatch** (`overwatch.fandom.com/api.php`, solo la API): plantillas `Template:<Héroe> Skins|Emotes|VP|
  Intros|Sprays`. `{{CTS|n=…}}` = cabecera (rareza `{{rl|c/r/e/l/m|Evento}}` + precio), `{{CPB|h=Prefijo|n=Nombre|
  l=|c=columnas}}` = imagen `File:Prefijo l-o-n.png`, `{{CVB|…}}` = vídeo `.webm`. Varias cabeceras seguidas se
  reparten las columnas de las celdas de debajo; las filas sin cabecera heredan la de su columna. URLs con
  `prop=imageinfo` (50 títulos por petición). Pausa de 0,15 s y reintentos con 5xx/429.
  **Su CDN de imágenes rechaza las descargas desde el servidor: no intentar saltárselo** (nada de User-Agent de
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
