# Carga la copia local del catálogo (addons/overwatch/datos/) en una base, sin internet. No borra nada.
# Desde la raíz del repo:
#   sg docker -c "docker exec -i odoo odoo shell -d <base> --no-http < addons/overwatch/scripts/cargar_catalogo.py"
from odoo.addons.overwatch.services.copia import cargar

print(cargar(env))  # noqa: F821 (env lo pone el shell)
env.cr.commit()  # noqa: F821
