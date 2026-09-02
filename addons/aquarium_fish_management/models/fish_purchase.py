# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    """Fish purchase workflow (SRD 4.14 / SEQ 38).

    Distinct from the regular accessory purchase flow: a purchase order
    line flagged as a fish purchase creates a batch record (stock.lot) and
    assigns it to a tank as soon as the order is confirmed, ahead of the
    physical receipt - staff then just need to fine-tune counts on arrival.
    """
    _inherit = "purchase.order.line"

    is_fish_purchase_line = fields.Boolean(string="Is Fish Purchase", default=False)
    fish_species_id = fields.Many2one("aquarium.fish.species", string="Fish Species")
    destination_tank_id = fields.Many2one(
        "stock.location", string="Assign to Tank",
        domain=[("is_tank", "=", True)],
    )
    fish_batch_id = fields.Many2one(
        "stock.lot", string="Created Batch", readonly=True, copy=False,
    )

    @api.onchange("fish_species_id")
    def _onchange_fish_species_id(self):
        for line in self:
            if line.fish_species_id:
                line.is_fish_purchase_line = True
                if line.fish_species_id.product_id:
                    line.product_id = line.fish_species_id.product_id

    def _create_fish_batch(self):
        """Create (or return existing) stock.lot batch for this PO line."""
        self.ensure_one()
        if self.fish_batch_id:
            return self.fish_batch_id
        if not (self.is_fish_purchase_line and self.fish_species_id and self.product_id):
            return self.env["stock.lot"]
        sequence = self.env["ir.sequence"].next_by_code("aquarium.fish.batch") or "/"
        lot = self.env["stock.lot"].create({
            "name": sequence,
            "product_id": self.product_id.id,
            "company_id": self.order_id.company_id.id,
            "is_fish_batch": True,
            "fish_species_id": self.fish_species_id.id,
            "supplier_id": self.order_id.partner_id.id,
            "date_received": fields.Date.context_today(self),
            "quantity_received": self.product_qty,
            "cost_per_fish": self.price_unit,
            "tank_id": self.destination_tank_id.id if self.destination_tank_id else False,
            "purchase_order_id": self.order_id.id,
        })
        self.fish_batch_id = lot.id
        return lot


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def button_confirm(self):
        result = super().button_confirm()
        for order in self:
            for line in order.order_line.filtered("is_fish_purchase_line"):
                line._create_fish_batch()
        return result
