---
name: nuevo-modulo
description: Crear un proyecto o módulo nuevo de Odoo 20 en el repo (carpeta, manifest, montaje en Docker, instalación) con su propia memoria CLAUDE.md y sus skills. Úsala cuando el usuario quiera añadir un addon, un proyecto nuevo o portar una app existente a Odoo.
---

# Nuevo proyecto / módulo

## Estructura (igual que `addons/fuertafit/`): la carpeta ES el módulo

```
addons/<modulo>/          nombre técnico = nombre de la carpeta (snake_case)
  __manifest__.py, __init__.py, models/, views/, security/, controllers/, static/…
  CLAUDE.md                memoria del proyecto: qué es, arquitectura, decisiones, normas propias
  README.md                para el usuario: qué hace y cómo se usa
  .claude/skills/<skill>/SKILL.md   skills propias (probar-cambios y las de su dominio)
  scripts/                 opcional: migraciones, utilidades (sin __manifest__.py: Odoo lo ignora)
```

## Pasos

1. Esqueleto del módulo: `__init__.py`, `__manifest__.py`, `models/`, `views/` (+ `menus.xml`), `security/ir.access.csv`,
   `static/description/icon.png`. Puedes partir de `odoo scaffold <modulo> /tmp/x` dentro del contenedor y copiar,
   pero adapta a las convenciones de `CLAUDE.md` (Odoo 20: `ir.access`, `models.Constraint`, `<list>`).
2. Acceso: `security/groups.xml` con su categoría, privilegio y grupo «Usuario» (y «Administrador» si hace falta),
   `user_ids` = `base.user_admin` (Dani). Cárgalo antes de `ir.access.csv` y úsalo en permisos, menú raíz y web
   (ver `addons/fuertafit/security/groups.xml`). Nada visible para `base.group_user` en general.
3. Manifest: `"version": "20.0.1.0.0"`, `"author": "danii1199"`, `"license": "LGPL-3"`, `"depends": ["base", ...]`.
4. No hay que tocar el compose: `addons/` entero está montado. Tras crear el módulo,
   `sg docker -c "docker restart odoo"` para que Odoo lo vea (`odoo module list` o Aplicaciones → Actualizar lista).
5. Dependencias Python: línea `RUN pip install ...` en el `Dockerfile` indicando el módulo, y `up -d --build`.
   Secretos/variables: en `.env` + `.env.example` + `environment:` del servicio `odoo` (solo lo que necesite).
6. Instala en una base de pruebas primero (skill `probar-modulo`), y en la real solo cuando el usuario lo diga:
   `docker exec -i odoo odoo module install -d <bd> <modulo>` + `restart odoo`.
7. Escribe `addons/<modulo>/CLAUDE.md` y sus skills (mínimo `probar-cambios`), y añade el proyecto a la estructura del
   `CLAUDE.md` raíz y al `README.md`.

## Portar una app existente (como se hizo con fuertafit)

- Tablas → modelos (`fields.Json` para datos sin esquema fijo); un `user_id` por registro en lo que sea de cada usuario
  y dominio `[('user_id', '=', user.id)]` en `ir.access.csv`.
- Lógica sin HTTP → `services/` que reciben `env`. Rutas `/api/*` → `controllers/main.py` con `http.route(auth="user")`;
  para POST JSON sin token CSRF, exige `Content-Type: application/json`.
- Web estática propia → `static/web/` servida por el controlador; hilos/schedulers → `ir.cron`.
- Script de migración de datos en `addons/<modulo>/scripts/` que **solo lee** la base antigua y se ejecuta con `odoo shell`.
