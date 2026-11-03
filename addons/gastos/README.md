# Gastos compartidos (`gastos`)

Como Splitwise, pero en tu Odoo: grupos o eventos (un viaje, el piso, una cena…), quién ha pagado qué, cómo se
reparte y quién debe a quién.

- **Todo en euros.** Cada grupo puede llevar su **imagen** (la foto del viaje, del piso…), que se ve en la web.
- **Backend** (menú *Gastos compartidos*): crea un grupo, añade miembros (cualquier contacto) y apunta gastos y
  pagos. Pestaña *Quién debe a quién* con el mínimo de pagos para quedar en paz. Botón **Invitar** en cada miembro:
  le llega un correo para crear su contraseña (cuenta de portal, gratis) y desde entonces ve sus grupos en la web.
  **Gastos solo lo ve quien tiene el permiso «Gastos compartidos: web»**, que se da solo al invitar o añadir a
  alguien con cuenta a un grupo (el resto de usuarios no ven ni el menú).
- **Web móvil** `/gastos`: tus grupos con tu saldo, añadir y editar gastos (a partes iguales, por partes, por
  porcentaje o importes exactos, con el cálculo en vivo), saldar deudas y ver los movimientos. **Cualquier miembro
  gestiona el grupo como desde el backend**: crear grupos, ⚙ Ajustes (nombre, descripción, imagen, avisos), añadir,
  invitar, archivar o quitar miembros y archivar el grupo. Cada uno solo ve sus grupos.
- **Pagos**: cada uno apunta los pagos que hace él (nadie puede apuntar un pago en nombre de otro).
- **Pagos editables con historial**: un pago solo lo puede editar quien lo apuntó, y cada cambio queda registrado
  (quién, cuándo y qué cambió) bajo el pago, en la web y en el backend.
- **Avisos por correo**: a los demás miembros con cada gasto o pago, botón *Recordar pagos* y resumen semanal (los
  lunes) a quien tenga algo pendiente. Se activan o desactivan por grupo, en la pestaña *Avisos*.
- **Splitwise**: exporta un grupo en el CSV de Splitwise o importa el que exportas desde Splitwise (en el grupo,
  «Exportar como hoja de cálculo»). En la web, en ⚙ *Ajustes → Splitwise*; en el backend, botones *Exportar a
  Splitwise* e *Importar de Splitwise* del grupo. Antes de importar ves cuántos gastos y pagos entran y emparejas cada
  persona de Splitwise con un miembro (o se crea). Los saldos quedan iguales que en Splitwise; volver a importar el
  mismo archivo no repite nada y no se manda un correo por cada movimiento importado. Solo euros.
- **n8n (opcional)**: en *Avisos → Webhook* pon la URL de un nodo Webhook de n8n y recibirá cada evento en JSON
  (gasto, pago, recordatorio, resumen, con saldos y deudas). Desde n8n puedes reenviarlo a Telegram, WhatsApp…

**Para que salgan los correos** hay que configurar el correo saliente: *Ajustes → Técnico → Servidores de correo
saliente* (con Gmail: smtp.gmail.com, puerto 587, TLS y una contraseña de aplicación).

Permisos (*Ajustes → Usuarios → Gastos compartidos*): **Usuario** ve los grupos donde está; **Administrador** ve
todos y configura el webhook.
