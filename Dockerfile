FROM odoo:17.0

USER root

# Custom addons (Phase 2: fish species / batch / tank / mortality module lives here)
COPY ./addons /mnt/extra-addons

# OCA auditlog (SRD/AQS task 14 — Community has no built-in audit trail).
# Sparse-checkout just this module from OCA/server-tools's 17.0 branch to
# keep the image small rather than cloning the whole repo.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && git clone --depth 1 --branch 17.0 --filter=blob:none --sparse \
       https://github.com/OCA/server-tools.git /mnt/oca-addons \
    && cd /mnt/oca-addons && git sparse-checkout set auditlog \
    && rm -rf /mnt/oca-addons/.git \
    && apt-get purge -y git && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

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
