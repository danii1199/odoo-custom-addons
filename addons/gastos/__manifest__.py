{
    "name": "Gastos compartidos",
    "summary": "Grupos de gastos al estilo Splitwise: quién pagó, cómo se reparte y quién debe a quién",
    "description": "Grupos o eventos con sus miembros, gastos con reparto a partes iguales, por importes, por "
                   "partes o por porcentaje, pagos entre miembros y deudas simplificadas. Web móvil en /gastos "
                   "para los miembros (cuenta de portal), avisos por correo, resumen semanal, webhook (n8n) y exportar/importar el CSV de Splitwise.",
    "version": "20.0.1.3.0",
    "category": "Productivity",
    "author": "danii1199",
    "license": "LGPL-3",
    "depends": ["base", "mail", "portal", "website"],
    "data": [
        "security/groups.xml",
        "security/ir.access.csv",
        "data/moneda.xml",
        "data/mail_templates.xml",
        "data/ir_cron.xml",
        "data/website_menu.xml",
        "views/grupo_views.xml",
        "views/gasto_views.xml",
        "views/liquidacion_views.xml",
        "views/splitwise_views.xml",
        "views/menus.xml",
        "views/web_templates.xml",
    ],
    "application": True,
    "installable": True,
}
