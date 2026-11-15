{
    "name": "Solicitudes IG",
    "summary": "Cancelar a mano, por packs, las solicitudes de seguimiento pendientes de Instagram",
    "description": "Importa la lista de solicitudes enviadas de la exportación de datos de Instagram (HTML, JSON o "
                   "texto) y abre los perfiles de 10 en 10 para cancelarlas a mano. No se conecta a Instagram.",
    "version": "20.0.1.0.0",
    "category": "Productivity",
    "author": "danii1199",
    "icon": "/solicitudes-ig/web/icon.png",  # fuera de static/: solo lo sirve el controlador, con permiso
    "license": "LGPL-3",
    "depends": ["base", "web", "website"],
    "data": [
        "security/groups.xml",
        "security/ir.access.csv",
        "data/website_menu.xml",
        "views/solicitud_views.xml",
        "views/menus.xml",
        "views/web_templates.xml",
    ],
    "application": True,
    "installable": True,
}
