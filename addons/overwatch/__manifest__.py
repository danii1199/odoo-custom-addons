{
    "name": "Overwatch",
    "summary": "Selección de héroes de Overwatch: favoritos, héroe aleatorio, historia, vídeos y galería de cosméticos",
    "description": "Pantalla de selección de héroes al estilo del juego (/overwatch) con favoritos por usuario y "
                   "sorteo general o por rol; ficha de cada héroe con habilidades, historia y su vídeo de origen; "
                   "galería de aspectos, gestos, poses de victoria, presentaciones y grafitis; todos los pases de batalla. Catálogo importado "
                   "de OverFast API (datos oficiales) y de la wiki de Overwatch (cosméticos).",
    "version": "20.0.1.6.0",
    "category": "Website",
    "author": "danii1199",
    "license": "LGPL-3",
    "depends": ["base", "web", "website"],
    "data": [
        "security/groups.xml",
        "security/ir.access.csv",
        "data/website_menu.xml",
        "data/ir_cron.xml",
        "views/hero_views.xml",
        "views/cosmetic_views.xml",
        "views/season_views.xml",
        "views/import_views.xml",
        "views/menus.xml",
        "views/web_templates.xml",
    ],
    "application": True,
    "installable": True,
}
