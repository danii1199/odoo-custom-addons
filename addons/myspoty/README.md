# myspoty

> **Estado (2026-10):** se va a portar a un módulo de Odoo (`addons/myspoty/myspoty`) dentro del Odoo común del repo.
> Lo que sigue describe la app antigua de `app/`, que sirve de referencia; ya no se ejecuta ni se conservan sus datos.

Reproductor propio de Spotify con diseño "aura": tus playlists, Tus me gusta, búsqueda con `Ctrl+K`,
etiquetas de colores, valoraciones y notas por canción, playlists inteligentes que se sincronizan con tu
Spotify y estadísticas propias. Necesita **Spotify Premium** para reproducir.

## Puesta en marcha

1. En https://developer.spotify.com/dashboard crea una app con la Redirect URI
   `http://127.0.0.1:8001/callback` y marca *Web API* y *Web Playback SDK*.
2. Pega el **Client ID** en `.env` detrás de `SPOTIFY_CLIENT_ID=` (no hace falta el client secret).
3. `~/servicios/servicios.sh build odoo` (si luego cambias `.env`: `~/servicios/servicios.sh recrear odoo`; `restart` no lo relee)
4. Abre **http://127.0.0.1:8001** (con `127.0.0.1`, no `localhost`) y entra con Spotify.

## Uso

| Tecla | Acción |
|---|---|
| `Ctrl+K` | Buscar / ir a una sección (`Enter` reproduce, `Mayús+Enter` a la cola) |
| `Espacio` | Play / pausa |
| `←` `→` | ±10 s · con `Mayús`: canción anterior / siguiente |
| `T` | Etiquetar y valorar lo que suena |
| `L` | Me gusta |
| `F` | Pantalla completa: portada y controles + letra sincronizada (LRCLIB) |

- En las listas: doble clic (o clic en el número/portada) reproduce; al pasar el ratón salen ♥, etiquetas y "añadir a".
- Clic en el anillo del botón de play = saltar a esa parte de la canción.
- **Estadísticas reales de Spotify**, actualizadas solas **cada hora** (y al iniciar sesión, o con «Actualizar ahora»):
  - Tus tops oficiales (último mes, 6 meses y año): 50 artistas y 50 canciones calculados por Spotify con todo lo que escuchas.
  - En segundo plano, myspoty guarda cada hora tus últimas 50 escuchas (lo que Spotify permite) sin duplicar;
    de ahí salen las marcas «12×» de las listas. No se muestra como sección porque solo cuenta desde que usas myspoty.
  - Spotify ya no da géneros a las apps nuevas, así que no se muestran.

## Estructura (MVC)

- `app/models/`: datos propios en Postgres (base de datos `myspoty`, ver `../postgres`): sesión, canciones, etiquetas, valoraciones,
  playlists inteligentes e historial.
- `app/services/`: cliente de Spotify (OAuth PKCE, renovación del token, Web API) y playlists inteligentes.
- `app/controllers/`: `/login`, `/callback` y `/api/*`.
- `app/views/static/`: la web (HTML, `css/`, `js/` por módulo). Rutas sin `#` (`/playlists`, `/tags`…).

## Varios usuarios

- Cada persona entra con **su** Spotify y tiene sus propias etiquetas, inteligentes, tops e historial.
- Spotify (modo desarrollo) permite **25 usuarios**: añade el email de cada uno en tu app del panel → *User Management*.
- Para que otros inicien sesión hace falta una dirección **https** registrada como Redirect URI (Tailscale o dominio) y
  ponerla en `SPOTIFY_REDIRECT_URIS` (separadas por comas) en `.env`.
- Tus otros dispositivos: tu foto → **Conectar otro dispositivo** → código de 6 letras para escribir en la pantalla de entrada.

## Seguridad

- Abierto a la red de casa en `http://IP-de-este-PC:8001`; cada usuario necesita su sesión (login o código). Desde otros PC no suena en el navegador (Spotify exige HTTPS): hace de mando a distancia de tus dispositivos.
  El login con Spotify solo funciona desde este PC por `http://127.0.0.1:8001`.
- Tu contraseña nunca pasa por myspoty: inicias sesión en la página de Spotify.
- `.env` está fuera de git; los datos viven en el volumen Docker `postgres-datos`, fuera del repo.

## Conexión con otros proyectos

El contenedor está en la red Docker `proyectos`: otro contenedor de esa red puede llamarlo en `http://myspoty:8001`.
