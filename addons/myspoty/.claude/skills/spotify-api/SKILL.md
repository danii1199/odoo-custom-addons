---
name: spotify-api
description: Lo comprobado sobre la Web API de Spotify para myspoty - endpoints que funcionan, los que dan 403/404 a apps nuevas, migración playlists tracks→items, rate limit, PKCE, modo desarrollo y letras de LRCLIB. Úsala antes de proponer o programar cualquier función que llame a Spotify.
---

# Web API de Spotify (comprobado en 2026-09)

## Autenticación

- OAuth **PKCE** sin client secret: solo `SPOTIFY_CLIENT_ID`. El token se renueva con el refresh token.
- Spotify **no acepta `localhost`** como Redirect URI: usar `http://127.0.0.1:<puerto>/...`. Cualquier otra dirección
  (IP de la LAN, dominio) tiene que ser **https** (pendiente: proxy HTTPS o dominio).
- Modo desarrollo: máx. 25 usuarios dados de alta por email en el panel (User Management); si no, `/me` da 403.
- Reproducir en el navegador (Web Playback SDK) exige contexto seguro: desde `http://IP` no suena; la web hace de
  mando a distancia de otros dispositivos (`Player.canPlayHere`).

## Qué no está disponible para apps nuevas (desde nov. 2024)

- Recomendaciones (404), related-artists (403), top-tracks de artista (403), `GET /albums?ids=` (403),
  audio-features y previews. Las playlists creadas por Spotify dan 404. `genres` llega vacío: no mostrarlo.
- Búsqueda: `limit` ≤ 10. Seguir artistas necesitaría el scope `user-follow-*` (no pedido).
- Sustituto casero de "relacionados": colaboradores de tus favoritos (`smart_sources.py`, fuente `collab`).

## Migración de endpoints (comprobado 2026-09-28)

- En playlists el campo `tracks` pasa a `items` (`items.total`). `/playlists/{id}/tracks` da 403 → usar
  `/playlists/{id}/items` (la canción viene en `item`, no en `track`).
- `/me/tracks/contains` da 403 → `/me/library/contains?uris=`.
- Siguen igual: `/me/tracks`, `/me/player/recently-played` (máx. 50), `/me/top/{tracks,artists}`, search.
- Escrituras: probar primero la dirección nueva y, si Spotify la rechaza, la antigua (`spFirst` en JS, `_first` en
  Python). No se han probado contra la cuenta real: las prueba el usuario.

## Rate limit

- `429` con `Retry-After` ≤ 10 s: esperar y reintentar una vez. Si es > 60 s, recordar el bloqueo por tipo de
  petición y no reintentar (`_blocked`). El 2026-09-28 `GET /artists/{id}/albums` quedó bloqueado ~22 h por pruebas.
- No lanzar syncs completas seguidas. Cachés en memoria: búsquedas 1 h, discografías 24 h. `liked` se relee solo
  si cambia el total o la más reciente.

## Letras

Spotify no da letras: **LRCLIB** (`lrclib.net`, sin clave). Caché en tabla: vacía = sin letra (reintentar a los
7 días); si la búsqueda da 503, no guardar nada.
