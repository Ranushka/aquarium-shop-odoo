FROM odoo:17.0

USER root

# Custom addons (Phase 2: fish species / batch / tank / mortality module lives here)
COPY ./addons /mnt/extra-addons

# OCA modules Community edition is missing (sparse-checkout just what's
# needed from each repo's 17.0 branch, not the whole repo):
#  - auditlog (server-tools): AQS task 14, no built-in audit trail
#  - date_range + report_xlsx (server-ux / reporting-engine): dependencies
#    of account_financial_report below
#  - account_financial_report (account-financial-reporting): AQS task 48,
#    P&L / Balance Sheet / General Ledger / Trial Balance — Enterprise-only
#    in stock Odoo (account_reports), this is Community's equivalent
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && mkdir -p /mnt/oca-addons \
    && git clone --depth 1 --branch 17.0 --filter=blob:none --sparse \
       https://github.com/OCA/server-tools.git /tmp/server-tools \
    && (cd /tmp/server-tools && git sparse-checkout set auditlog) \
    && cp -r /tmp/server-tools/auditlog /mnt/oca-addons/ \
    && git clone --depth 1 --branch 17.0 --filter=blob:none --sparse \
       https://github.com/OCA/server-ux.git /tmp/server-ux \
    && (cd /tmp/server-ux && git sparse-checkout set date_range) \
    && cp -r /tmp/server-ux/date_range /mnt/oca-addons/ \
    && git clone --depth 1 --branch 17.0 --filter=blob:none --sparse \
       https://github.com/OCA/reporting-engine.git /tmp/reporting-engine \
    && (cd /tmp/reporting-engine && git sparse-checkout set report_xlsx) \
    && cp -r /tmp/reporting-engine/report_xlsx /mnt/oca-addons/ \
    && git clone --depth 1 --branch 17.0 --filter=blob:none --sparse \
       https://github.com/OCA/account-financial-reporting.git /tmp/afr \
    && (cd /tmp/afr && git sparse-checkout set account_financial_report) \
    && cp -r /tmp/afr/account_financial_report /mnt/oca-addons/ \
    && rm -rf /tmp/server-tools /tmp/server-ux /tmp/reporting-engine /tmp/afr \
    && apt-get purge -y git && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --break-system-packages --no-cache-dir xlsxwriter xlrd

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
