# Odoo 20 Community común. El código de los módulos NO va en la imagen: se monta desde addons/ (extra-addons).
FROM odoo:20

USER root
# Dependencias Python que pidan los módulos (indica cuál lo pide). Tras cambiarlas, reconstruye la imagen
# RUN pip install --no-cache-dir --break-system-packages "anthropic>=1.0"   # fuertafit: entrenador IA (de pago)

COPY odoo-entrypoint.sh /odoo-entrypoint.sh
RUN chmod 755 /odoo-entrypoint.sh && chown odoo:odoo /etc/odoo
USER odoo

ENV TZ=Europe/Madrid PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["/odoo-entrypoint.sh"]
CMD ["odoo"]
