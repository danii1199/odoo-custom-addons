# Portada del sitio (módulo de Odoo `inicio_web`)

Página de inicio del sitio web (`/`): panel personal con reloj, saludo según la hora, fecha, frase del día y una
tarjeta por proyecto. Petición del usuario (2026-11-02): algo original para no tener la portada en blanco; es de uso
privado y la ve poca gente.

- `views/portada.xml`: hereda `website.homepage` y añade el panel dentro del `t-call` a `website.layout` (no depende del `#wrap`: si se borra con el editor, no se rompe; el CSS lo pone primero), y el `#wrap` sigue siendo editable
  con el editor del sitio (lo que se ponga sale debajo). Odoo copia la herencia también a la copia del sitio
  (`website_id = 1`) si la portada ya se había editado.
- `models/website.py`: `website.inicio_datos()` (pública porque QWeb no deja llamar a métodos con `_`). No depende
  de los otros módulos: cada tarjeta mira si existe su modelo (`"ow.hero" in env`) y si el usuario tiene el grupo.
  Consultas con sudo, siempre filtradas al usuario actual o sobre catálogos públicos.
  - Mi rutina: días entrenados esta semana (`fuerta.history.done_on`), L–D marcados.
  - Dead by Daylight (también sin sesión): recuentos del catálogo y enlace a la build aleatoria.
  - Overwatch (pública): héroes y, con su grupo, favoritos; «héroe del día» al azar entre los favoritos (fijo durante el día) con su fondo.
  - Gastos (grupo `apachas.group_gastos_web`): saldo total en sus grupos activos.
  - Backend: solo usuarios internos.
- **Personalizar menú** (2026-11-03, petición del usuario: «entro y solo quiero ver gastos»): en la portada, un
  `<details>` con una casilla por entrada de primer nivel del menú del sitio que el usuario puede ver (sin la
  portada); POST `/inicio/menu` guarda las URLs desmarcadas en `res.users.ini_menu_oculto` (separadas por espacios,
  con sudo y solo las URLs posibles). `website.menu._compute_visible` las esconde para ese usuario y la portada
  quita sus tarjetas. Solo esconde: los permisos no cambian.
  También desde el **perfil**: «Personalizar menú» en el desplegable del usuario (`views/mi_menu.xml` hereda
  `portal.user_dropdown`, así que lo tienen internos y portal) abre `/mi-menu` (casillas con el estilo del tema;
  `volver=mi-menu` hace que el POST vuelva ahí con «Guardado»). Depende de `portal` por esa herencia.
- Sin sesión: aviso de rincón privado + botón «Entrar» y solo la tarjeta de DbD.
- `controllers/main.py`: `/mi-menu` (GET) y `/inicio/menu` (POST). `tests/test_portada.py`: portada pública, ocultar una entrada y un usuario de portal desde /mi-menu.
- `static/src/`: CSS bajo `.ini-app` y JS (reloj, saludo y foco que sigue al ratón), en `web.assets_frontend`.
- Frases propias en `FRASES` (models/website.py); se elige una por día.

Actualizar: como añade un campo a `res.users`, `odoo module upgrade` falla («column res_users.ini_menu_oculto does
not exist») la primera vez; usa `odoo -d <base> -u inicio_web --stop-after-init --http-port=8098`. Después vale:
`sg docker -c "docker exec -i odoo odoo module upgrade -d <base> inicio_web && docker restart odoo"`.

## Esquema de color (2026-11-04)

`portada.js` va en `web.assets_frontend`, así que se carga en **todo** el sitio. Al principio pone
`document.documentElement.style.colorScheme` a `dark` o `light` según el fondo del `body` (el tema es oscuro). Sin
esto, los controles nativos (calendario de `input[type=date]`, listas de `select`) salían en claro sobre fondo oscuro, y
Samsung Internet con modo oscuro volvía a oscurecer la página por su cuenta.
