#!/bin/bash
set -e

# Render odoo.conf from template with runtime env vars (ODOO_MASTER_PASSWORD),
# since ConfigParser (odoo.conf) doesn't do its own env substitution.
envsubst < /etc/odoo/odoo.conf.template > /etc/odoo/odoo.conf

exec /entrypoint.sh "$@"
