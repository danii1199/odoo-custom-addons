# Rutifuerta (módulo de Odoo `rutifuerta`)

Genera y planifica rutinas diarias a partir del catálogo de vídeos de FuertaFit (suscripción del usuario).
**Solo enlaza a los vídeos** (`https://webapp.fuertafit.com/#/post/{id}`); nunca se descargan vídeos ni URLs de streaming.
Esta carpeta (`addons/rutifuerta`) **es el módulo**: nombre técnico `rutifuerta`. Docker, Postgres y bases de datos son
comunes y están en la raíz (`../../CLAUDE.md`, skills `odoo-docker`, `odoo-bases-de-datos`, `probar-modulo`).

Historia: web independiente (`app/`, base `rutinas`) → módulo `fuerta_rutinas` (2026-10) → módulo `rutifuerta` con la
web dentro del sitio web de Odoo y todo editable también desde el backend (2026-10-05). La base antigua `rutinas`
sigue existiendo solo para `scripts/migrar_rutinas.py`.

## Estructura

```
__manifest__.py  depende de base, web y website
models/          routine.py (fuerta.routine: catálogo COMÚN, `data` JSON + campos calculados almacenados),
                 history.py, plan.py (+ acciones del backend: hecha, generar semana), day_status.py (skipped/moved/away),
                 settings.py (fuerta.settings: JSON `values` + campos editables con compute/inverse; fuerta.group),
                 week_plan.py (fuerta.week.plan: «Mis semanas», semanas tipo guardadas por usuario)
wizard/          away.py (marcar ausencia de varios días), routine_import.py (importar JSON de rutinas)
services/        lógica sin HTTP que recibe `env`: catalog.py (grupos con GROUP_RULES, búsqueda, caché por base),
                 generator.py, planner.py (semana/día), calendar.py (mover, saltar, ausencias), coach.py (IA, latente),
                 dates.py (`today()` en Europe/Madrid, WEEKDAYS)
controllers/     main.py: /rutifuerta (página del sitio web), /rutifuerta/sync (ventana del marcador) y /rutifuerta/api/* (JSON)
views/           web_templates.xml (la página /rutifuerta), vistas del backend, asistentes, menus.xml
data/            ir_cron.xml (plan automático), groups.xml (7 grupos), website_menu.xml («Mi rutina» en el menú web)
security/        groups.xml (grupo de acceso), ir.access.csv: catálogo y grupos lectura; plan/historial/estados/ajustes
                 solo los propios; todo exige el grupo
web/             css/app.css (todo bajo .fuerta-app), js/<pestaña>.js, sync.html, bookmarklet.js
scripts/         migrar_rutinas.py (rutinas → Odoo; solo lee la base antigua; se lanza con `odoo shell`)
```

## La web dentro del sitio web de Odoo

- `/rutifuerta` (`website=True`, `auth="user"`) renderiza `rutifuerta.app_page`, que hace `t-call="website.layout"`:
  cabecera, menú y pie del sitio. Encima y debajo de la app hay `oe_structure` (`oe_structure_fuerta_top/bottom`)
  que el usuario edita con el editor del sitio web; Odoo guarda esos cambios como vista personalizada (no tocar
  esos ids o se pierden las ediciones). La app (`#fuerta-app`) la pinta el JS; no es editable.
- CSS: todo prefijado con `.fuerta-app` para no romper Bootstrap del sitio. Clases que chocaban con Bootstrap
  renombradas: `.fa-row` (no `.row`), `.fa-head`, `.fa-nav`, `.fa-main` (el sitio ya tiene `header`, `nav`, `main`).
- JS: scripts clásicos con ámbito global (`Hoy`, `Cal`, `Week`, `Cat`, `Bot`, `Sync`, `Sigilo`), cargados al final de la
  plantilla con `?v=` (fecha del estático más nuevo). `common.js` primero, `main.js` (rutas `#/vista`) al final.
  Selectores siempre dentro de `#fuerta-app`. El `anchor_slide` del sitio no interfiere con `#/vista`.
- Botón «⚙ Gestionar en Odoo» → `/odoo/action-rutifuerta.action_plan` (backend).

## Backend = todo lo que hace la web

Menú **Rutifuerta**: Planificado (calendario/lista editable, botones «Generar esta semana / la que viene»,
«Hecha»/«Deshacer» por línea), Historial, Días especiales (+ «Marcar ausencia» con rango), Mis ajustes (server action
que abre/crea el registro del usuario: minutos, calentamiento, material, semana tipo con etiquetas, plan automático),
Mis semanas (semanas tipo guardadas, agrupadas por días de entreno, botón «Usar esta semana»), Catálogo → Rutinas (lectura) e Importar rutinas (mismo JSON que el marcador). Lo que se cree en un lado se ve en el otro:
los dos usan los mismos modelos y métodos (`save_plan`, `mark_done`, `planner.plan_week`, `calendar.set_away`…).
Si añades algo a la web, añade su equivalente en el backend (y al revés).

## Acceso (2026-10-05: «el de entrenamiento solo lo ve Dani»)

- Grupo `rutifuerta.group_fuerta_user` («Rutifuerta / Usuario», `security/groups.xml`), con Dani
  (`base.user_admin`). Lo exigen `ir.access.csv`, el menú raíz, el menú web «Mi rutina» (todas sus copias por sitio)
  y el controlador (`_allowed()`: 403 en `/rutifuerta`, `/rutifuerta/sync` y `/rutifuerta/api/*`). El cron se salta a quien no lo
  tenga. Para dar acceso a otro usuario: Ajustes → Usuarios → «Rutifuerta: Usuario».

## Detalles

- Multiusuario (entre quienes tienen el grupo): catálogo común; lo demás por usuario (`user_id`, dominio en ir.access).
- `services/catalog.get(env)` cachea el catálogo clasificado por base y lo recarga si cambia la tabla.
- `_api(handler)`: JSON, `HttpError` → status; POST solo `Content-Type: application/json` (protección CSRF).
- Ajustes: `values` (JSON) es la fuente de verdad (lo usa la web); los campos del formulario se calculan de él y lo
  escriben con `_inverse_fields`. `auto_plan` tiene compute propio porque se guarda (el cron busca por él).
  Los nombres de `fuerta.group` deben coincidir con `GROUP_RULES` de `services/catalog.py`.
- Odoo 20: un campo Binary devuelve `BinaryValue` (`.decode()` da el contenido ya sin base64).
- Mis semanas (`fuerta.week.plan`, 2026-10-05): semanas tipo por días de entreno (`days_count`, calculado) y
  minutos (`minutes`). Las **recomendadas** (`recommended`, sin `user_id`, comunes y de solo lectura por ir.access)
  vienen de `data/week_recommended.xml` (3/4/5 días × 30/45/50/60 min, pautas ACSM/NSCA; generado con un script,
  descripción en cada una).
  **2026-10-19: reorientadas a perder grasa** (fuerza + cardio, cardio tras torso, máx. 3 bloques de cardio/semana) y
  **sin Cuerpo-Mente** (el usuario no lo quiere: solo calentamiento, con el ajuste `warmup`; `cooldown` en false).
  Simuladas con `generator.generate` y los ajustes reales: todas cuadran al minuto. Se editaron a mano, no hay script. Las del usuario son suyas; duplicar una recomendada da una propia. Usar una = copiar su
  `week` y sus `minutes` a los ajustes (`week` y `dailyMinutes`). Ya no se crean semanas de ejemplo por usuario.
- Duraciones: `durationMinutes` es la **nominal** de FuertaFit («2x10MIN»), no la del vídeo; el usuario prefiere
  seguir con ella aunque algún día salga más largo (los vídeos a veces incluyen más que el entrenamiento). No corregir
  duraciones a mano sin que lo pida (2026-10-19 se probó con «Entrenamiento 30 de enero», id 1691, y lo dejó en 20).
- `semana.js`: `save()` sustituye `s`; los chips leen siempre `s.week[i]` al hacer clic (antes editaban el objeto viejo).
- **Plan sigilo** (2026-10-21, `web/js/sigilo.js`, vista `#/sigilo` enlazada desde Hoy): rutina **propia**, no de
  FuertaFit, para los días sin tiempo: 30:00 justos (calentamiento, 3 asaltos de sombra, fuerza 40/20 × 2 vueltas,
  final a tope, bajar pulsaciones), **en silencio** (el usuario tiene vecinos: cero saltos e impactos; nada de escaladores ni zancadas con paso, los pies no caen al suelo). Temporizador mudo: color, parpadeo
  y vibración opcional; versión con mancuernas (`alt`). Todo en el JS (`PLAN`), sin modelo ni backend: es contenido
  fijo, no datos del usuario, y no se apunta en el historial (este va por rutinas de FuertaFit). Si cambias pasos,
  que el total siga en 1800 s.
- `services/coach.py`: entrenador con Claude API, **latente** (solo con `ANTHROPIC_API_KEY` y el SDK). El usuario no
  quiere pagar API: no lo actives ni lo sugieras.

## Ejecutar y actualizar (desde la raíz del repo)

```bash
sg docker -c "docker exec -i odoo odoo module upgrade -d <bd> rutifuerta && docker restart odoo"
```
Solo estáticos: recargar el navegador. Web: `/rutifuerta` en el sitio de Odoo.

## Normas

- **No tocar los datos reales** (la base real) sin pedirlo: skill `probar-cambios` (base `rutifuerta_test`).
- No restaurar ni recrear datos que el usuario haya borrado. Nada que requiera API de pago.
- Código y textos en español, mismo estilo que el existente. Catálogo desde FuertaFit: skill `actualizar-catalogo`.

## Nombre (2026-11-03)

Antes era el módulo `fuertafit` (web `/fuerta`). Se renombró a `rutifuerta` (`/rutifuerta`) por decisión del
usuario. Los modelos siguen siendo `fuerta.*`. El marcador del navegador lleva la URL dentro: tras el cambio hay
que volver a instalarlo desde la pestaña «Actualizar».

## Invisible sin permiso (2026-11-03, decisión del usuario)

Para quien no tenga `group_fuerta_user` (o no tenga sesión), Rutifuerta **no existe**: todas sus rutas son
`auth="public"` + `website=True` y lanzan `NotFound` (`_forbidden()`), así la 404 es la misma página del sitio que
una URL inventada (sin `website=True` Odoo da otra más corta, y `auth="user"` mandaría al login: las dos lo delatan).
Los archivos están en `web/` (no en `static/`, que Odoo sirve a cualquiera) y los sirve `/rutifuerta/web/<ruta>`
con permiso; el icono también (`web_icon` y `icon` del manifest). Tests: `tests/test_acceso.py`. No añadas nada en
`static/` ni rutas sin `_allowed()`.
