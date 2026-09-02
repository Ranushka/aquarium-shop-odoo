# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class PosOrderLine(models.Model):
    """Fish sales via POS (SRD 4.12 / SEQ 37) - backend support.

    Cashiers select the fish species, quantity, and source tank when more
    than one tank has stock. Stock is only reduced once the POS order is
    successfully paid/validated - Odoo's own POS flow already defers stock
    moves to order confirmation, so we simply ensure the lot/tank chosen at
    sale time is carried onto the resulting stock move line.
    """
    _inherit = "pos.order.line"

    is_fish_line = fields.Boolean(string="Is Fish Sale", default=False)
    fish_species_id = fields.Many2one("aquarium.fish.species", string="Fish Species")
    source_tank_id = fields.Many2one(
        "stock.location", string="Source Tank",
        domain=[("is_tank", "=", True)],
    )
    fish_batch_id = fields.Many2one(
        "stock.lot", string="Fish Batch",
        domain=[("is_fish_batch", "=", True)],
    )


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def get_available_fish_tanks(self, fish_species_id):
        """Backend API used by the POS UI: for a given fish species, return
        the tanks that currently have available stock, so the cashier can
        pick a source tank when more than one qualifies.

        Returns a list of dicts: tank id, name, code, and current quantity.
        """
        species = self.env["aquarium.fish.species"].browse(fish_species_id)
        if not species.exists():
            return []
        lots = self.env["stock.lot"].search([
            ("fish_species_id", "=", fish_species_id),
            ("is_fish_batch", "=", True),
        ])
        tanks_data = {}
        for lot in lots:
            for tank in self.env["stock.location"].search([("is_tank", "=", True)]):
                qty = lot.current_quantity_at_tank(tank)
                if qty > 0:
                    entry = tanks_data.setdefault(tank.id, {
                        "tank_id": tank.id,
                        "tank_code": tank.tank_code,
                        "tank_name": tank.tank_display_name or tank.display_name,
                        "quantity": 0.0,
                        "batch_ids": [],
                    })
                    entry["quantity"] += qty
                    entry["batch_ids"].append(lot.id)
        return list(tanks_data.values())

    def _process_order(self, order, draft, existing_order):
        order_id = super()._process_order(order, draft, existing_order)
        pos_order = self.browse(order_id)
        pos_order._link_fish_lines_to_stock_moves()
        return order_id

    def _link_fish_lines_to_stock_moves(self):
        """Best-effort: propagate the cashier-selected batch/tank onto the
        stock move lines Odoo generated for this order's picking, so the
        fish batch (lot) is preserved on the customer-facing stock move and
        SEQ 34's quantity_sold calculation picks it up correctly.
        """
        for order in self:
            if not order.picking_ids:
                continue
            fish_lines = order.lines.filtered("is_fish_line")
            for line in fish_lines:
                if not line.fish_batch_id:
                    continue
                moves = order.picking_ids.move_ids.filtered(
                    lambda m, line=line: m.product_id == line.product_id,
                )
                for move in moves:
                    move_lines = move.move_line_ids.filtered(lambda ml: not ml.lot_id)
                    if move_lines:
                        move_lines[:1].write({"lot_id": line.fish_batch_id.id})
