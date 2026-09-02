"""Shared XML-RPC connection helper for the demo-data scripts.

Credentials: the admin password is read from the ODOO_ADMIN_PASSWORD env var
(never hardcoded/committed) — get it from this project's memory entry or
docs/OPERATIONS.md. URL/DB/login aren't secrets so they're fixed here.
"""
import os
import sys
import xmlrpc.client

ODOO_URL = "https://aquarium.ranu.win"
ODOO_DB = "aquarium_shop"
ODOO_LOGIN = "admin@aquarium.shop"

MANIFEST_PATH = os.path.join(os.path.dirname(__file__), ".demo_data_manifest.json")


def connect():
    password = os.environ.get("ODOO_ADMIN_PASSWORD")
    if not password:
        sys.exit(
            "Set ODOO_ADMIN_PASSWORD first, e.g.:\n"
            "  export ODOO_ADMIN_PASSWORD='...'\n"
            "(find it in this project's memory entry / docs/OPERATIONS.md)"
        )
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_LOGIN, password, {})
    if not uid:
        sys.exit("Authentication failed — check ODOO_ADMIN_PASSWORD.")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

    def call(model, method, *args, **kwargs):
        return models.execute_kw(
            ODOO_DB, uid, password, model, method, list(args), kwargs
        )

    return call
