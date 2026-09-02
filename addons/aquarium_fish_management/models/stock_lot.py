# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockLot(models.Model):
    """Fish Batch = Odoo Lot/Serial Number (SRD 4.7 / SEQ 29 mapping).

    Every fish purchase creates a unique batch, implemented as a stock.lot
    record. The lot's own `name` field is used as the Batch ID.
    """
    _inherit = "stock.lot"

    # --- Fish-batch specific fields -----------------------------------
    is_fish_batch = fields.Boolean(
        string="Is Fish Batch", default=False, index=True,
        help="Set automatically when this lot is linked to a fish species.",
    )
    fish_species_id = fields.Many2one(
        "aquarium.fish.species", string="Fish Species", index=True,
    )
    supplier_id = fields.Many2one("res.partner", string="Supplier")
    date_received = fields.Date(string="Date Received", default=fields.Date.context_today)
    quantity_received = fields.Float(
        string="Quantity Received", default=0.0,
        help="Quantity of fish received into this batch at purchase time.",
    )
    cost_per_fish = fields.Monetary(string="Cost per Fish", currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id,
    )
    total_purchase_cost = fields.Monetary(
        string="Total Purchase Cost", currency_field="currency_id",
        compute="_compute_total_purchase_cost", store=True,
    )
    tank_id = fields.Many2one(
        "stock.location", string="Assigned Tank",
        domain=[("is_tank", "=", True)],
        help="Tank this batch was originally assigned to. Individual quants "
             "may move across tanks via fish transfers; see current_quantity "
             "per tank for the live picture.",
    )
    purchase_order_id = fields.Many2one(
        "purchase.order", string="Purchase Order",
        help="The purchase order that generated this fish batch, if any.",
    )

    # --- SEQ 34: stock calculation engine -------------------------------
    # Current Quantity = Received - Sold - Mortality - Transfers Out + Transfers In
    quantity_sold = fields.Float(
        string="Quantity Sold", compute="_compute_stock_quantities",
    )
    quantity_mortality = fields.Float(
        string="Quantity Mortality", compute="_compute_stock_quantities",
    )
    quantity_transferred_in = fields.Float(
        string="Quantity Transferred In", compute="_compute_stock_quantities",
    )
    quantity_transferred_out = fields.Float(
        string="Quantity Transferred Out", compute="_compute_stock_quantities",
    )
    current_quantity = fields.Float(
        string="Current Quantity", compute="_compute_stock_quantities",
        help="Received - Sold - Mortality - Transfers Out + Transfers In",
    )
    mortality_percentage = fields.Float(
        string="Mortality %", compute="_compute_stock_quantities",
        help="Mortality quantity as a percentage of quantity received.",
    )

    # --- SEQ 40: profitability reporting ---------------------------------
    total_sales_revenue = fields.Monetary(
        string="Sales Revenue", currency_field="currency_id",
        compute="_compute_profitability",
    )
    profit = fields.Monetary(
        string="Profit", currency_field="currency_id",
        compute="_compute_profitability",
    )
    profit_margin = fields.Float(
        string="Profit Margin %", compute="_compute_profitability",
    )

    @api.depends("quantity_received", "cost_per_fish")
    def _compute_total_purchase_cost(self):
        for rec in self:
            rec.total_purchase_cost = (rec.quantity_received or 0.0) * (rec.cost_per_fish or 0.0)

    @api.model
    def compute_fish_stock_quantity(self, received, sold, mortality,
                                     transferred_out, transferred_in):
        """Isolated, unit-testable implementation of the SEQ 34 formula.

        Current Quantity = Received - Sold - Mortality - Transfers Out + Transfers In

        Kept as a pure function (no recordset access) so it can be exercised
        directly by TransactionCase tests without any stock-move fixtures.
        """
        received = received or 0.0
        sold = sold or 0.0
        mortality = mortality or 0.0
        transferred_out = transferred_out or 0.0
        transferred_in = transferred_in or 0.0
        return received - sold - mortality - transferred_out + transferred_in

    def _get_sold_quantity(self):
        """Quantity of this batch sold to customers (POS + regular sales),
        derived from done stock move lines whose destination is a customer
        location. Using stock move history keeps this consistent with
        Odoo's own inventory valuation and avoids double bookkeeping.
        """
        self.ensure_one()
        move_lines = self.env["stock.move.line"].search([
            ("lot_id", "=", self.id),
            ("state", "=", "done"),
            ("location_dest_id.usage", "=", "customer"),
        ])
        # Odoo 17 renamed stock.move.line's "qty_done" field to "quantity".
        return sum(move_lines.mapped("quantity"))

    def _get_transfer_quantities(self):
        """(transferred_out, transferred_in) between tanks (internal
        locations flagged is_tank) for this batch, from done stock moves.
        """
        self.ensure_one()
        move_lines = self.env["stock.move.line"].search([
            ("lot_id", "=", self.id),
            ("state", "=", "done"),
            ("location_id.is_tank", "=", True),
            ("location_dest_id.is_tank", "=", True),
        ])
        transferred_out = 0.0
        transferred_in = 0.0
        if self.tank_id:
            for line in move_lines:
                qty = line.quantity
                if line.location_id == self.tank_id:
                    transferred_out += qty
                if line.location_dest_id == self.tank_id:
                    transferred_in += qty
        return transferred_out, transferred_in

    def _get_mortality_quantity(self):
        self.ensure_one()
        mortalities = self.env["aquarium.fish.mortality"].search([
            ("lot_id", "=", self.id),
            ("state", "=", "approved"),
        ])
        return sum(mortalities.mapped("quantity"))

    @api.depends("quantity_received", "is_fish_batch", "tank_id")
    def _compute_stock_quantities(self):
        for rec in self:
            if not rec.is_fish_batch:
                rec.quantity_sold = 0.0
                rec.quantity_mortality = 0.0
                rec.quantity_transferred_in = 0.0
                rec.quantity_transferred_out = 0.0
                rec.current_quantity = 0.0
                continue
            sold = rec._get_sold_quantity()
            mortality = rec._get_mortality_quantity()
            transferred_out, transferred_in = rec._get_transfer_quantities()
            rec.quantity_sold = sold
            rec.quantity_mortality = mortality
            rec.quantity_transferred_out = transferred_out
            rec.quantity_transferred_in = transferred_in
            rec.current_quantity = rec.compute_fish_stock_quantity(
                rec.quantity_received, sold, mortality, transferred_out, transferred_in,
            )
            rec.mortality_percentage = (
                (mortality / rec.quantity_received * 100.0) if rec.quantity_received else 0.0
            )

    def _get_sales_revenue(self):
        self.ensure_one()
        pos_lines = self.env["pos.order.line"].search([
            ("fish_batch_id", "=", self.id),
        ])
        return sum(pos_lines.mapped("price_subtotal_incl"))

    @api.depends("quantity_sold", "total_purchase_cost")
    def _compute_profitability(self):
        for rec in self:
            revenue = rec._get_sales_revenue() if rec.is_fish_batch else 0.0
            rec.total_sales_revenue = revenue
            rec.profit = revenue - rec.total_purchase_cost
            rec.profit_margin = (rec.profit / revenue * 100.0) if revenue else 0.0

    def current_quantity_at_tank(self, tank):
        """Current quantity of this batch physically in `tank`
        (a stock.location recordset, singleton), applying the SEQ 34 formula
        scoped to that tank via stock.quant (source of truth for physical
        on-hand quantity per lot/location).
        """
        self.ensure_one()
        quants = self.env["stock.quant"].search([
            ("lot_id", "=", self.id),
            ("location_id", "=", tank.id),
        ])
        return sum(quants.mapped("quantity"))

    @api.onchange("fish_species_id")
    def _onchange_fish_species_id(self):
        for rec in self:
            rec.is_fish_batch = bool(rec.fish_species_id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("fish_species_id") and "is_fish_batch" not in vals:
                vals["is_fish_batch"] = True
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("fish_species_id") and "is_fish_batch" not in vals:
            vals["is_fish_batch"] = True
        return super().write(vals)
