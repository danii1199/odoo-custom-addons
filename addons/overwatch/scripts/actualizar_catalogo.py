# Actualiza todo el catálogo de Overwatch desde `odoo shell` (sin el límite de tiempo de una petición web).
# Hace commit tras cada héroe. Desde la raíz del repo:
#   sg docker -c "docker exec -i odoo odoo shell -d <base> --no-http < addons/overwatch/scripts/actualizar_catalogo.py"
from odoo.addons.overwatch.services import seasons
from odoo.addons.overwatch.services.importer import Importer

stats = Importer(env(context=dict(env.context, ow_commit=True)), log=print).run()  # noqa: F821 (env lo pone el shell)
env.cr.commit()  # noqa: F821
print(stats)
print("Pases de batalla:", seasons.importar(env))  # noqa: F821
env.cr.commit()  # noqa: F821
