# Menú de inicio (módulo de Odoo `menu_inicio`)

Pantalla de inicio a pantalla completa con la cuadrícula de apps y un buscador de menús, en vez del desplegable de
apps de arriba a la izquierda de Community. Al usuario le gusta cómo lo hace Enterprise, pero se queda en Community:
este módulo es **código propio** (no copiar nada de Enterprise: su licencia no lo permite). Solo depende de `web`.

## Cómo funciona

```
static/src/home_menu_state.js   signals compartidas isOpen y standalone + show/hide/toggle (barra, menú, WebClient)
static/src/home_menu.js/.xml    componente HomeMenu en registry "main_components": cuadrícula de apps
                                (webIconData = data URL; o webIcon "clase,color,fondo"), buscador con ruta
                                "App / Menú / Submenú", flechas + Enter, Esc vuelve a la app actual
static/src/home_menu.scss       overlay fijo bajo la barra (top: --o-navbar-height, z-index 990), degradado
static/src/navbar_patch.js/.xml el botón de apps (web.NavBar.AppsMenu) abre/cierra el menú; con el menú abierto se
                                ocultan nombre y secciones de la app; en móvil «All Apps» del lateral lo abre
static/src/webclient_patch.js   WebClient._loadDefaultApp: en /odoo sin acción se abre el menú (standalone) en vez de
                                la 1.ª app, y da estado a esa entrada del historial (ver «Atrás» abajo)
```
- Se cierra solo cuando se carga otra acción (bus `ACTION_MANAGER:UI-UPDATED`).
- `standalone` (abierto en lugar de una app: recién entrado o vuelto a /odoo con «Atrás»): el botón y Esc no lo
  cierran, porque lo que haya detrás no corresponde a la URL. Abierto con el botón desde una app sí se cierra.
- Con el menú abierto, `.o_action_manager` queda `visibility: hidden` (`:has(.o_menu_inicio)`): no asoma nada.
- **«Atrás» del navegador (bug corregido 2026-10-05)**: la entrada de historial de /odoo nace sin `history.state`;
  el router de Odoo trata un popstate sin estado como «clic en un enlace» y no recarga, así que se quedaba la URL
  de inicio con la app anterior pintada y la barra a medias. `_loadDefaultApp` hace `replaceState({nextState})`
  para que el popstate lance `ROUTE_CHANGE` → `loadRouterState` → `_loadDefaultApp` → menú.
- Todo va en `web.assets_backend` (`static/src/**/*`).

## OWL 3 / Odoo 20 (comprobado)

- Estado: `proxy({...})` en componentes; compartido entre componentes con `signal(v)` de módulo (`s()` lee, `s.set(v)`).
- Refs: `x = signal.ref()` + `t-ref="this.x"`; en plantillas siempre `this.` delante.
- **No** `static props`: OWL 3 lo rechaza y rompe el webclient entero (pantalla en blanco). Si hacen falta props: `useProps`.
- Iconos: `<i class="oi" data-icon="search"/>` (no `oi-search`).
- Patch de getters: añadir un setter vacío al lado (como hace website/navbar.js).

## Probar

En una base de pruebas (`probar-modulo`). Sin la extensión de Chrome conectada, Chromium sin interfaz en Docker:
`node:20-alpine` + `apk add chromium font-noto` + `npm i puppeteer-core@23`, login en `/web/login?db=<bd>_test`
(enviar con Enter: hay varios botones submit; `waitUntil: "domcontentloaded"`, nunca `networkidle`: el bus
mantiene conexiones abiertas), ir a `/odoo` y comprobar `.o_menu_inicio`, recoger `pageerror` y
errores de consola y hacer capturas. Un error de JS en un componente global deja el backend en blanco: mira siempre
la consola.

Prueba de navegación con «Atrás»/«Adelante»: inicio → app → registro → atrás ×2 (debe verse el menú, URL /odoo,
acción oculta) → Esc (no cierra) → adelante (app) → botón (abre encima) → Esc (vuelve a la app). Usa
`history.back()` con `page.evaluate`, no `page.goBack()` (es una SPA: no hay navegación que esperar).
