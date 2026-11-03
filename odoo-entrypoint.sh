#!/bin/bash
# Genera /etc/odoo/odoo.conf a partir de odoo.conf (montado como odoo.base.conf) y añade lo que no va en git:
#  - addons_path: /mnt/extra-addons (= addons/ del repo; cada subcarpeta con __manifest__.py es un módulo),
#    solo si ya hay alguno
#  - admin_passwd: contraseña maestra del gestor de bases de datos (variable de entorno ODOO_MASTER_PASSWORD)
#  - dbfilter: qué bases se pueden abrir desde el navegador (variable de entorno ODOO_DBFILTER, opcional)
# Después sigue con el entrypoint oficial de la imagen.
set -e
: "${ODOO_MASTER_PASSWORD:?Falta la variable de entorno ODOO_MASTER_PASSWORD (protege el gestor de bases de datos)}"

paths=""
if compgen -G "/mnt/extra-addons/*/__manifest__.py" > /dev/null; then
    paths=/mnt/extra-addons
fi

umask 077
{
    cat /etc/odoo/odoo.base.conf
    echo
    if [ -n "$paths" ]; then echo "addons_path = $paths"; fi
    echo "admin_passwd = $ODOO_MASTER_PASSWORD"
    if [ -n "${ODOO_DBFILTER:-}" ]; then echo "dbfilter = $ODOO_DBFILTER"; fi
} > /etc/odoo/odoo.conf
chmod 600 /etc/odoo/odoo.conf

exec /entrypoint.sh "$@"
