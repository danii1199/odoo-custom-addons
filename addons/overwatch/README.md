# Overwatch (`overwatch`)

La pantalla de selección de héroes de Overwatch en el sitio web de tu Odoo: entrada **Overwatch** en el menú del
sitio (`/overwatch`), visible para todo el mundo (sin sesión, solo para mirar; los favoritos piden el permiso «Overwatch / Usuario»). El backend (app *Overwatch*) es solo para retocar el catálogo.

- **Selección de héroes** como en el juego: los héroes por rol abajo, y el elegido en grande con su fondo, rol,
  vida y habilidades.
- **Favoritos**: «Añadir a favoritos», clic derecho en un héroe o la tecla F. Se guardan en tu cuenta. «★ Favoritos»
  muestra solo los tuyos.
- **Aleatorio**: elige rol (cualquiera, tanque, daño o apoyo) y si sortear solo entre tus favoritos, y pulsa
  *Aleatorio* (o la tecla R). Las casillas se recorren hasta pararse en el elegido.
- **Ficha del héroe**: habilidades con su vídeo, ventajas, datos, **historia** completa con su **vídeo de origen**,
  y la **galería** de aspectos, gestos, poses de victoria, presentaciones y grafitis, con su rareza y cómo se
  consigue, filtros por rareza y buscador.
- **Catálogo**: *Overwatch → Configuración → Actualizar catálogo* trae los héroes nuevos (datos oficiales en español
  vía [OverFast API](https://overfast-api.tekrop.fr)) y sus cosméticos (de la
  [wiki de Overwatch](https://overwatch.fandom.com)). Gratis y sin claves; no borra nada. Úsalo cuando salga un héroe
  o una temporada nueva. Las imágenes de cosméticos se ven directamente desde la wiki; si alguna no carga, puedes
  subir una propia en *Cosméticos*.
- **Copia local**: el módulo trae el catálogo exportado en `datos/`. En *Actualizar catálogo* elige «Copia local» para
  cargarlo en una base sin descargar nada.

Permisos (*Ajustes → Usuarios → Overwatch*): **Usuario** entra en la web y guarda favoritos; **Administrador** edita
y actualiza el catálogo. Sin permiso no se ve nada.
