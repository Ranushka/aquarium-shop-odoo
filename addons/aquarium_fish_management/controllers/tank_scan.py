# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class TankScanController(http.Controller):
    """Public tank QR scan view (SRD 4.8 / SEQ 33).

    Scanning a tank's QR code opens this page, which shows current stock,
    fish species, batch details, sales, mortality, and remaining quantity.
    The QWeb template is tuned for tablet/mobile viewports, since this is
    meant to run on fish-area tablets.
    """

    @http.route(
        "/aquarium/tank/scan/<string:token>",
        type="http", auth="public", sitemap=False,
    )
    def tank_scan(self, token, **kwargs):
        tank = request.env["stock.location"].sudo().search([
            ("tank_qr_token", "=", token),
            ("is_tank", "=", True),
        ], limit=1)
        if not tank:
            return request.not_found()

        quants = request.env["stock.quant"].sudo().search([
            ("location_id", "=", tank.id),
            ("lot_id.is_fish_batch", "=", True),
        ])
        batches = quants.mapped("lot_id")

        batch_rows = []
        for lot in batches:
            batch_rows.append({
                "lot": lot,
                "species": lot.fish_species_id,
                "current_qty_here": lot.current_quantity_at_tank(tank),
            })

        recent_mortality = request.env["aquarium.fish.mortality"].sudo().search([
            ("tank_id", "=", tank.id),
        ], order="date desc", limit=10)

        recent_sales = request.env["pos.order.line"].sudo().search([
            ("source_tank_id", "=", tank.id),
        ], order="id desc", limit=10)

        values = {
            "tank": tank,
            "batch_rows": batch_rows,
            "total_current_stock": sum(row["current_qty_here"] for row in batch_rows),
            "recent_mortality": recent_mortality,
            "recent_sales": recent_sales,
        }
        return request.render(
            "aquarium_fish_management.tank_scan_template", values,
        )
