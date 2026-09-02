{
    "name": "Aquarium Shop Roles & Permissions",
    "version": "17.0.1.0.0",
    "category": "Human Resources",
    "summary": "Role/permission matrix (Administrator, Manager, Cashier, Fish Staff) "
                "for the aquarium shop, per AQS work item 'User accounts, roles & "
                "permissions matrix' (SRD 3 & 6)",
    "description": """
Aquarium Shop Roles & Permissions
==================================
Adds four security groups mapping the shop's real job roles onto Odoo's
built-in application groups, plus real field-level access control (not just
view-level hiding) for purchase-cost and profit figures.

This module intentionally defines **no new models** — it is pure security
configuration (res.groups + implied_ids, ir.model.fields.groups, ir.rule,
menu group overrides) layered on top of aquarium_fish_management and Odoo's
own Point of Sale / Inventory / Purchase / Invoicing apps. See README.md for
the full role -> group mapping table and a manual verification checklist.

No real staff user accounts are created by this module — assigning a real
person to one of these groups is a one-click step once the business owner
supplies real names (tracked separately in Plane, out of scope here).
""",
    "author": "Aquarium Shop Odoo Project",
    "website": "https://github.com/Ranushka/aquarium-shop-odoo",
    "license": "LGPL-3",
    "depends": [
        "base",
        "stock",
        "purchase",
        "point_of_sale",
        "product",
        "account",
        "aquarium_fish_management",
    ],
    "data": [
        "security/aquarium_role_groups.xml",
        "security/aquarium_field_security.xml",
        "security/aquarium_menu_restrictions.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
