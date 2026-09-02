FROM odoo:17.0

USER root

# Custom addons (Phase 2: fish species / batch / tank / mortality module lives here)
COPY ./addons /mnt/extra-addons

# Base Odoo config template; rendered at container start (entrypoint.sh) with
# ODOO_MASTER_PASSWORD. DB connection itself comes from HOST/PORT/USER/PASSWORD
# env vars, read natively by the official image's own entrypoint.
COPY ./odoo.conf.template /etc/odoo/odoo.conf.template
COPY ./entrypoint.sh /entrypoint-wrapper.sh
RUN chown -R odoo:odoo /etc/odoo \
    && chmod +x /entrypoint-wrapper.sh \
    && apt-get update \
    && apt-get install -y --no-install-recommends gettext-base \
    && rm -rf /var/lib/apt/lists/*

USER odoo

EXPOSE 8069
ENTRYPOINT ["/entrypoint-wrapper.sh"]
CMD ["odoo"]
