{
    "name": "Rutifuerta",
    "summary": "Genera y planifica rutinas diarias con el catálogo de vídeos de FuertaFit",
    "description": "Solo enlaza a los vídeos de FuertaFit; nunca los descarga. "
                   "Cada usuario tiene su calendario, historial y ajustes; el catálogo es común.",
    "version": "20.0.1.4.0",
    "category": "Productivity",
    "author": "danii1199",
    "icon": "/rutifuerta/web/icon.png",  # fuera de static/: solo lo sirve el controlador, con permiso
    "license": "LGPL-3",
    "depends": ["base", "web", "website"],
    "data": [
        "security/groups.xml",
        "security/ir.access.csv",
        "data/ir_cron.xml",
        "data/groups.xml",
        "data/week_recommended.xml",
        "data/website_menu.xml",
        "views/wizard_views.xml",
        "views/routine_views.xml",
        "views/user_data_views.xml",
        "views/settings_views.xml",
        "views/week_plan_views.xml",
        "views/menus.xml",
        "views/web_templates.xml",
    ],
    "application": True,
    "installable": True,
}
