# Solicitudes IG (módulo de Odoo `solicitudes_ig`)

Petición del usuario (2026-11-14): cancelar sus solicitudes de seguimiento pendientes de Instagram de forma ágil y
**sin automatizar Instagram** (riesgo de bloqueo de la cuenta y va contra sus condiciones). La app solo ordena la lista y
abre los perfiles; el usuario cancela a mano en cada uno. Solo para Dani (grupo propio). Esta carpeta **es el módulo**.

## Estructura

```
services/lector.py   lee la exportación (HTML, JSON o texto) → [(usuario, fecha)] sin Odoo
models/solicitud.py  ig.solicitud (una por cuenta y usuario de Odoo): pendiente → abierta → hecha; «resuelta» = ya
                     no sale en la última exportación completa. importar() reabre lo «hecho» que vuelve a salir.
controllers/main.py  /solicitudes-ig (página del sitio), /solicitudes-ig/web/* (archivos de web/) y
                     /solicitudes-ig/api/{estado,importar,marcar}; todo 404 sin el grupo, como rutifuerta
web/                 app.js, app.css, icon.png (fuera de static/: solo con permiso)
```

- **Packs**: `window.open` de N perfiles en el mismo clic (si hay un `await` antes, el navegador las bloquea). Sin
  `"noopener"` en la llamada para poder contar las bloqueadas (con él devuelve null siempre); se pone `opener = null` después.
  El navegador pide permitir ventanas emergentes la primera vez.
- **«Abrir la siguiente»**: enlace a la siguiente del pack; Ctrl/⌘+clic o rueda la abren detrás (ninguna página puede
  hacerlo con un clic normal) y el enlace avanza tras el clic (`setTimeout`, si no abriría la siguiente). Clic normal: no
  abre nada, solo avisa (el usuario no quiere que le lleve a la pestaña). Con el pack entero abierto, se bloquea.
- **Verificación**: reimportar una exportación nueva con «lista completa» marca «Ya no sale» lo que desapareció (cancelada
  o aceptada) y devuelve a pendiente lo que se marcó como cancelado y sigue saliendo.
- Datos de terceros (nombres de cuentas): solo en la base, nunca en el repo.
- No añadir llamadas a Instagram ni automatizar clics: lo descartó el usuario por el riesgo de bloqueo.
