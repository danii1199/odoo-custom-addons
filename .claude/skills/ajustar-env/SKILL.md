---
name: ajustar-env
description: Cambiar valores del .env de despliegue (contraseñas de Postgres y de los roles, contraseña maestra del gestor de bases de datos, ANTHROPIC_API_KEY) sin mostrarlos, aplicándolos también en Postgres y recreando los contenedores. Úsala cuando el usuario quiera cambiar, regenerar, poner o revisar una contraseña o clave del .env, o tras instalar en un PC nuevo.
---

# Ajustar el .env

Todo con el script `ajustar-env.sh` de la carpeta de despliegue del usuario (fuera del repo; su ruta, en tu memoria;
abajo `$SERVICIOS`), con `sg docker -c "..."` si la sesión no tiene el grupo docker. **Nunca** leas ni muestres el
`.env` ni los valores: el script no los imprime. No escribas la ruta del `.env` en archivos del repo (es público).

| Qué | Orden |
|---|---|
| Ver qué claves tienen valor (sin valores) | `$SERVICIOS/ajustar-env.sh` |
| Valor nuevo al azar | `$SERVICIOS/ajustar-env.sh <CLAVE>` |
| Valor elegido por el usuario | que lo ejecute él: `! $SERVICIOS/ajustar-env.sh <CLAVE> --preguntar` (lo pide oculto) |
| Vaciar una clave opcional | `$SERVICIOS/ajustar-env.sh ANTHROPIC_API_KEY --borrar` |

Las claves están en `.env.example` (junto al `.env`): contraseñas del superusuario de Postgres y de los roles de
Odoo, `ODOO_MASTER_PASSWORD` (gestor `/web/database/manager`) y `ANTHROPIC_API_KEY` (opcional).

## Qué hace y por qué

- Las contraseñas de Postgres solo se leen del `.env` al crear el volumen de Postgres: cambiarlas solo en el
  `.env` rompe la conexión de Odoo. El script hace antes `ALTER ROLE` en Postgres (necesita el contenedor arrancado).
- Después escribe el `.env` (permisos 600) y hace `./servicios.sh recrear postgres odoo`.
- Tras cambiar la contraseña maestra, dile al usuario que la nueva está en `ODOO_MASTER_PASSWORD` del `.env`; si la
  pide expresamente, sácala con `grep` del `.env` (solo entonces y sin guardarla en archivos).
- Si el usuario quiere elegir la contraseña, no se la pidas por el chat: que use `--preguntar` con `!`.
- `ANTHROPIC_API_KEY` es de pago y el usuario no quiere APIs de pago: no la pongas por iniciativa propia; además
  haría falta descomentar el SDK en el `Dockerfile` y `$SERVICIOS/servicios.sh build odoo`.
- Las contraseñas de los usuarios de Odoo (tu login) no están en el `.env`: se cambian en Odoo (Preferencias / Ajustes → Usuarios).
