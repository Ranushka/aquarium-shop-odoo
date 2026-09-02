# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class ProductProduct(models.Model):
    """Expose the linked fish species (if any) on the sellable product so
    the POS frontend can tell, per product tile, whether clicking it should
    go through the guided species/tank selection flow (SEQ 37).

    Not stored: `aquarium.fish.species.product_id` is the authoritative
    link (set from the species form); this is a thin, always-fresh mirror
    of it, cheap enough for POS catalog sizes (a shop's live product count).
    """
    _inherit = "product.product"

    fish_species_id = fields.Many2one(
        "aquarium.fish.species", string="Fish Species",
        compute="_compute_fish_species_id",
        help="Set when a fish species record points to this product as its "
             "sellable product. Read by the POS frontend to trigger the "
             "guided tank-selection flow instead of a plain add-to-order.",
    )

    def _compute_fish_species_id(self):
        species_by_product = {
            species.product_id.id: species.id
            for species in self.env["aquarium.fish.species"].search(
                [("product_id", "in", self.ids)],
            )
        }
        for product in self:
            product.fish_species_id = species_by_product.get(product.id, False)


class PosSession(models.Model):
    """Make sure `fish_species_id` is part of the product data the POS
    frontend loads at session start - without this, `product.fish_species_id`
    would exist on the backend model but never reach the browser, and the
    JS click hook in pos_fish_sale.js would have nothing to check.

    Odoo 17.0 mainline loads POS product fields via
    `_loader_params_product_product()` (a per-model dict of
    {'search_params': {'domain': ..., 'fields': [...]}}) rather than the
    `_load_pos_data_fields()` classmethod used in later Odoo versions - see
    the module README for the version-sensitivity note on this method name.
    """
    _inherit = "pos.session"

    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        result["search_params"]["fields"].append("fish_species_id")
        return result


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

    @api.model
    def _order_line_fields(self, line, session_id=None):
        """Carry the fish-sale fields the frontend attaches to each
        orderline's exported JSON (see `Orderline.export_as_JSON` in
        pos_fish_sale.js) through to the `pos.order.line` create vals.

        The base `_order_line_fields()` only whitelists/maps the stock
        fields it already knows about (product_id, qty, price_unit, ...);
        anything else in the raw line dict is silently dropped unless we
        pull it out here ourselves. This is the "matching field on the
        backend pos.order.line create path" the module README used to flag
        as missing.
        """
        raw_vals = line[2] if len(line) > 2 and isinstance(line[2], dict) else {}
        result = super()._order_line_fields(line, session_id)
        if len(result) > 2 and isinstance(result[2], dict) and raw_vals.get("is_fish_line"):
            result[2]["is_fish_line"] = True
            result[2]["fish_species_id"] = raw_vals.get("fish_species_id") or False
            result[2]["source_tank_id"] = raw_vals.get("source_tank_id") or False
            result[2]["fish_batch_id"] = raw_vals.get("fish_batch_id") or False
        return result

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
