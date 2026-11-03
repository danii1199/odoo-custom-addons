# Apachas (módulo de Odoo `apachas`)

Grupos de gastos al estilo Splitwise: miembros, gastos con su reparto, pagos entre miembros y deudas simplificadas.
Backend (menú **Apachas**) para Dani y los usuarios del módulo; web móvil **/apachas** para los amigos
(cuentas de portal). Avisos por correo y webhook opcional para n8n. Esta carpeta **es el módulo**. Docker, Postgres y
bases de datos son comunes (`../../CLAUDE.md`).

Decisiones del usuario (2026-11-02): avisos con el correo de Odoo + webhook por si monta n8n; los amigos entran con
cuenta de portal (invitación desde el miembro); permisos por grupos del módulo. Después: **todo en euros** (sin
elegir moneda) y una **imagen** por grupo en vez del emoji. Y que **cualquier miembro gestione el grupo desde la web
como desde el backend** (ajustes, imagen, miembros, editar y borrar cualquier gasto); el webhook, solo el administrador.
Los **pagos solo los edita quien los apuntó** (nadie más, ni el administrador) y cada edición queda en su historial.
**Nadie paga por otro**: en un pago, quien paga es siempre quien lo apunta.
2026-11-03: **Gastos solo lo ve quien tenga permiso** (grupo «Apachas: web»), y se da al invitar o añadir
a alguien con cuenta a un grupo.

## Estructura

```
models/       grupo.py (gastos.grupo + simplificar_deudas, saldos, correos, webhook, cron), miembro.py (gastos.miembro,
              invitar al portal), gasto.py (gastos.gasto + gastos.gasto.linea, repartir()), liquidacion.py (pagos +
              gastos.liquidacion.historial), splitwise.py (CSV de Splitwise: leer_csv/movimientos, exportar/importar
              en gastos.grupo, splitwise_ref en gastos y pagos, asistente gastos.importar.splitwise del backend)
controllers/  main.py: /apachas, /apachas/nuevo-grupo, /apachas/<id>, /apachas/<id>/ajustes (GET/POST),
              /apachas/<id>/archivar, /apachas/<id>/miembros/nuevo, /apachas/<id>/miembros/<mid>/<invitar|correo|archivar|
              activar|quitar>, /apachas/<id>/nuevo, /apachas/<id>/gasto/<gid> (editar), /apachas/<id>/pago/<pid> (editar), /apachas/<id>/saldar,
              /apachas/<id>/borrar/<gasto|pago>/<id> (POST con csrf_token), /apachas/<id>/exportar-splitwise (CSV),
              /apachas/<id>/importar-splitwise (POST con el archivo: revisión) y …/importar-splitwise/confirmar
views/        grupo/gasto/liquidacion_views.xml, splitwise_views.xml (asistente), menus.xml, web_templates.xml (web /apachas)
data/         moneda.xml (llama a `_forzar_euros`: EUR activo y todos los grupos en EUR, en cada actualización),
              mail_templates.xml (cuerpos QWeb de los correos), ir_cron.xml (resumen semanal, lunes 9:00),
              website_menu.xml («Gastos» en el menú del sitio, solo con group_gastos_web; se reescribe en cada copia)
security/     groups.xml: group_gastos_web (la web, portal o internos), group_gastos_user (backend, sus grupos; implica
              web) y group_gastos_manager (todos + webhook; Dani)
migrations/   20.0.1.2.0: da group_gastos_web a quien ya era miembro con cuenta
static/src/   css/apachas.css (bajo .gs-app), js/apachas.js (reparto en vivo, saldar, borrar con 2.º clic)
tests/        test_gastos.py: reparto, deudas, correos, permisos de portal y la web (HttpCase)
```

## Reglas de negocio

- Saldo = pagado − su parte de los gastos + pagos hechos − pagos recibidos (positivo: le deben). Todo en
  céntimos (`grupo.saldos_centimos()`); `deudas()` = mínimo de pagos (voraz).
- Reparto (`gasto.reparto`): `igual`, `partes` (valor = peso), `porcentaje` (suma 100), `importes` (suma el total).
  Lo que sobra al redondear va céntimo a céntimo a las primeras líneas; `repartir()` y el JS hacen lo mismo.
- `_check_reparto` / `_check_pago` validan todo (miembros del grupo, sin repetir, sumas).
- Euros siempre: `currency_id` existe porque lo piden los Monetary, pero es EUR fijo (por defecto, solo lectura,
  oculto). `_fmt()` da «1.234,50 €»; `_factor()` = 100. En los repartos se trabaja en céntimos.
- Imagen del grupo: `image` (hasta 1024 px) e `image_128` (relacionada, guardada) para la web y el backend; sin
  imagen, la web pinta la inicial. Los correos no la llevan (la URL necesita sesión).
- Miembro = contacto (`partner_id`); `name` y `user_id` se guardan para que el portal no necesite leer
  `res.partner`/`res.users`. Archivar un miembro lo saca de los repartos nuevos pero conserva su saldo.

## Permisos (security/ir.access.csv)

- `group_gastos_web` («Apachas: web», sin tipo de usuario: vale para portal e internos): lee y edita sus
  grupos (dominio `member_ids.user_id = user`), lee sus miembros y hace de todo con los gastos y pagos de sus grupos
  (también los que apuntaron otros, como en el backend). Sin él, ni menú ni web (`_acceso()` → 404) ni datos.
  `gastos.miembro._dar_acceso_web()` se lo da al crear un miembro con usuario, al cambiarle el contacto y al
  invitarlo (`action_invitar`). Quitárselo: en el usuario (Ajustes → Usuarios, modo desarrollador → grupos).
- Usuario del módulo: lo mismo en sus grupos (miembro o creador) y crea grupos. Administrador: todo.
- La web no usa sudo salvo: crear un grupo (con su creador como primer miembro) y crear/cambiar miembros y sus
  contactos. Siempre después de `_gestionable()` (= `check_access("write")` sobre el grupo; si no, 404). Al añadir
  un miembro con correo, si ya hay un contacto **con usuario** y ese correo, se usa ese (ve el grupo al momento).
  No se puede archivar ni quitar a uno mismo; «quitar» solo sin gastos ni pagos (si no, archivar). Correos y notas
  del historial también con sudo.
- Editar un gasto (web o backend) deja nota y avisa como uno nuevo (`gasto_editado` en el webhook).
- Pagos: `_check_pagas_tu()` (en create y si cambia `pagador_id`) exige que `pagador_id.user_id` sea el usuario
  (salvo `env.su`): ValidationError. La web fija «paga» al usuario (`/saldar` ignora lo que llegue) y solo muestra
  «Saldar» en las deudas propias; en el backend «Paga» se rellena con tu miembro y es de solo lectura. Un miembro
  sin cuenta no puede apuntar sus pagos (tiene que invitársele). `write()` lanza AccessError si `create_uid` no es el usuario (salvo `env.su`); `puedo_editar` lo refleja en
  la web y en la ficha del backend. Cada cambio de fecha/paga/recibe/importe/nota crea un
  `gastos.liquidacion.historial` (quién, cuándo, «Campo: antes → después»), deja nota en el grupo y avisa
  (`pago_editado`, con `cambios`). Sin cambios reales, no hay historial. Borrar: cualquier miembro.
- QWeb: un `<textarea t-out="x"/>` con `x` = False **no se pinta**: usar `t-out="x or ''"`.

## Splitwise (models/splitwise.py, 2026-11-03)

- CSV de «Exportar como hoja de cálculo» de Splitwise: `Date,Description,Category,Cost,Currency` + una columna por
  persona con su neto (pagado − su parte; la fila suma 0). Pagos: categoría `Payment` (quien paga, en positivo).
  Fila final «Total balance» (se ignora al importar). Cabeceras también en español; separador `,`, `;` o tabulador.
- Importar: un pagador → gasto con importes exactos (o `igual` si sale idéntico a `repartir()`); varios pagadores
  (aquí no existe) → un gasto por acreedor con lo que le deben (saldos idénticos, nota en el gasto). Los pagos se
  crean con sudo aunque no los hiciera quien importa (es historial; «nadie paga por otro» es para los nuevos).
  Solo EUR: otras monedas, filas que no cuadran o fechas raras → errores por línea (el resto se importa).
- `splitwise_ref` (sha1 de fecha, concepto, coste y netos) en gastos y pagos: reimportar se salta lo ya importado.
- Contexto `gastos_importando`: `create()` de gastos y pagos no deja notas ni avisa (ni correo ni webhook); una
  sola nota en el grupo al final. Personas sin miembro: se busca por nombre (sin tildes ni mayúsculas) o se crea
  contacto + miembro (sudo, tras `_gestionable()` en la web / `check_access("write")` en el asistente).
- Exportar: miembros activos o con saldo; categorías a las de Splitwise (`A_SPLITWISE`) y de vuelta por palabras
  (`DE_SPLITWISE`). Exportar e importar en otro grupo da los mismos saldos (test `test_ida_y_vuelta`).

## Avisos

- `grupo._correo()`: un `mail.mail` por miembro con correo (cuerpo QWeb personalizado con su saldo). Salen por el
  servidor de correo saliente de Odoo: **hay que configurarlo** (Ajustes → Técnico → Servidores de correo
  saliente; con Gmail, contraseña de aplicación). Sin él se quedan en la cola.
- Cada gasto/pago avisa a los demás miembros (si `notificar_gastos`); botón «Recordar pagos»; cron semanal a quien
  tenga saldo (si `resumen_semanal`).
- Webhook (`webhook_url`, solo administrador): POST JSON tras el commit (`cr.postcommit`), timeout 5 s, los fallos
  solo se registran. Eventos: `gasto_creado`, `gasto_borrado`, `pago_registrado`, `recordatorio`,
  `resumen_semanal`; siempre con `grupo`, `saldos` y `deudas`.

## Actualizar y probar

```bash
sg docker -c "docker exec -i odoo odoo module upgrade -d <base> gastos && docker restart odoo"
```
Pruebas: skill `probar-cambios`. Solo CSS/JS: reiniciar Odoo (cambia el `?v=`) y recargar.

## Pendiente / ideas

- Gastos recurrentes, fotos de ticket desde la web, Telegram vía n8n.

## Nombre (2026-11-03)

Antes era el módulo `gastos` (web `/gastos`). Se renombró a `apachas` (`/apachas`) por decisión del usuario, para
que el nombre no diga qué es. Los modelos siguen siendo `gastos.*` (no se ven desde fuera). La base real se migró
por SQL (`ir_module_module`, `ir_model_data`, claves de vistas, `website_menu`, cron) y luego `-u`.
