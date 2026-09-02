{
    "name": "Aquarium Fish Management",
    "version": "17.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Fish species, batch, tank, mortality, transfer, sales and reporting "
                "for an aquarium shop (SRD sections 4.6-4.14)",
    "description": """
Aquarium Fish Management
=========================
Adds fish-specific inventory management on top of Odoo's Stock module:

* Fish species master data
* Fish batches (built on stock.lot / Lot-Serial numbers)
* Tanks (built on stock.location) with QR codes and a public scan view
* A stock-quantity engine: Received - Sold - Mortality - Transfers Out + Transfers In
* Fish mortality tracking
* Tank-to-tank fish transfers (stock.picking/stock.move, lot preserved)
* Point of Sale fish-sale backend support (+ minimal POS UI hook)
* Fish purchase workflow (batch creation + tank assignment)
* Dashboard widgets and reports

See README.md in this module for the full SEQ 29 data-model mapping and a
list of what is fully implemented vs. stubbed.
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
        "web",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/aquarium_security.xml",
        "data/aquarium_data.xml",
        "views/fish_species_views.xml",
        "views/fish_batch_views.xml",
        "views/tank_views.xml",
        "views/fish_mortality_views.xml",
        "views/fish_transfer_views.xml",
        "views/fish_sale_views.xml",
        "views/fish_purchase_views.xml",
        "views/dashboard_views.xml",
        "views/tank_scan_templates.xml",
        "report/fish_reports.xml",
        "report/tank_qr_report.xml",
        "report/fish_report_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "aquarium_fish_management/static/src/js/pos_fish_sale.js",
            "aquarium_fish_management/static/src/xml/pos_fish_sale.xml",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
