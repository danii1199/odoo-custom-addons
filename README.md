# odoo-custom-addons

Módulos propios para **Odoo 20 Community**. Cada carpeta de `addons/` es un módulo independiente.

| Módulo | Qué hace | Depende de |
|---|---|---|
| [`rutifuerta`](addons/rutifuerta) | **Rutifuerta**: genera y planifica rutinas diarias con el catálogo de vídeos de FuertaFit (web `/rutifuerta`) | `website` |
| [`dbd`](addons/dbd) | **Dead by Daylight**: enciclopedia de supervivientes, asesinos, perks, complementos, mapas y ofrendas, con builds y ruleta (web `/dbd`) | `website` |
| [`overwatch`](addons/overwatch) | **Overwatch**: selección de héroes, favoritos, héroe aleatorio, historia, vídeos y galería de cosméticos (web `/overwatch`) | `website` |
| [`apachas`](addons/apachas) | **Apachas**: gastos compartidos al estilo Splitwise: quién pagó, cómo se reparte y quién debe a quién (web `/apachas`) | `mail`, `portal`, `website` |
| [`inicio_web`](addons/inicio_web) | **Portada del sitio**: panel con reloj, saludo y acceso a cada proyecto (web `/`) | `website`, `portal` |
| [`menu_inicio`](addons/menu_inicio) | **Menú de inicio**: cuadrícula de aplicaciones (estilo Enterprise) en vez del desplegable de apps | `web` |
| [`myspoty`](addons/myspoty) | Reproductor de Spotify. *Todavía no es un módulo de Odoo: pendiente de portar* | — |

Cada módulo tiene su propio README con más detalle.

## Contenido del repo

```
addons/              un módulo por carpeta (se monta como extra-addons)
Dockerfile           imagen basada en odoo:20 con el entrypoint propio
odoo-entrypoint.sh   genera odoo.conf al arrancar: añade addons_path y la contraseña maestra (desde variables de entorno)
odoo.conf            configuración base, sin secretos
```

El repo **no** incluye la infraestructura de despliegue (Compose, variables de entorno ni scripts). Las
contraseñas nunca se guardan en git: llegan al contenedor como variables de entorno.

## Uso

Requiere Docker y un PostgreSQL accesible desde el contenedor.

```bash
docker build -t odoo-custom .
docker run -d --name odoo -p 8069:8069 \
  -e HOST=<host-postgres> -e USER=<usuario> -e PASSWORD=<contraseña> \
  -e ODOO_MASTER_PASSWORD=<contraseña-maestra> \
  -v "$PWD/odoo.conf:/etc/odoo/odoo.base.conf:ro" \
  -v "$PWD/addons:/mnt/extra-addons:ro" \
  odoo-custom
```

Después instala los módulos desde *Aplicaciones*, o por consola:

```bash
docker exec -it odoo odoo module install -d <base> <modulo>
```

## Desarrollo

- Cambios en Python o XML de un módulo: `odoo module upgrade -d <base> <modulo>` y reiniciar Odoo.
- Módulo nuevo: crea `addons/<modulo>/` con su `__manifest__.py` y reinicia Odoo.
- Cambios en `Dockerfile` u `odoo-entrypoint.sh`: reconstruye la imagen.

## Licencia

LGPL-3, como indica el manifiesto de cada módulo.
