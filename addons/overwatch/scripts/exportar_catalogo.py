# Exporta el catálogo de una base a /tmp/ow-catalogo dentro del contenedor (addons/ está montado en solo lectura).
# Desde la raíz del repo:
#   sg docker -c "docker exec -i odoo odoo shell -d <base> --no-http < addons/overwatch/scripts/exportar_catalogo.py"
#   rm -rf addons/overwatch/datos && sg docker -c "docker cp odoo:/tmp/ow-catalogo addons/overwatch/datos"
from odoo.addons.overwatch.services.copia import exportar

print("Exportados (héroes, cosméticos):", exportar(env, "/tmp/ow-catalogo"))  # noqa: F821 (env lo pone el shell)
