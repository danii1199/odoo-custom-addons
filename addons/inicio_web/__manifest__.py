{
    "name": "Portada del sitio",
    "summary": "Página de inicio del sitio web: panel personal con reloj, saludo y accesos a cada proyecto",
    "description": "Sustituye la portada vacía del sitio web por un panel: saludo según la hora, reloj, frase del día "
                   "y una tarjeta por proyecto instalado (Mi rutina, Dead by Daylight, Overwatch, Gastos) con un dato "
                   "en vivo. Cada tarjeta solo aparece si el módulo está instalado y el usuario tiene acceso.",
    "version": "20.0.1.2.0",
    "category": "Website",
    "author": "danii1199",
    "license": "LGPL-3",
    "depends": ["website", "portal"],
    "data": [
        "views/portada.xml",
        "views/mi_menu.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "inicio_web/static/src/css/portada.css",
            "inicio_web/static/src/js/portada.js",
        ],
    },
    "installable": True,
    "auto_install": False,
}
