# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    """Light extension so fish transfers are easy to filter/report on."""
    _inherit = "stock.picking"

    is_fish_transfer = fields.Boolean(
        string="Is Fish Transfer", default=False, index=True,
    )


class AquariumFishTransfer(models.Model):
    """Fish transfer management, tank-to-tank (SRD 4.11 / SEQ 36).

    A thin front-end over Odoo's own stock.picking / stock.move (internal
    transfer type) so that the resulting movement history, and the
    lot/batch traceability, are exactly Odoo's standard mechanism -
    auditable via the regular stock move history views.
    """
    _name = "aquarium.fish.transfer"
    _description = "Aquarium Fish Transfer (Tank to Tank)"
    _order = "id desc"

    name = fields.Char(default="New", copy=False, readonly=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    lot_id = fields.Many2one(
        "stock.lot", string="Batch", required=True,
        domain=[("is_fish_batch", "=", True)],
    )
    fish_species_id = fields.Many2one(
        related="lot_id.fish_species_id", string="Fish Species", store=True,
    )
    source_tank_id = fields.Many2one(
        "stock.location", string="Source Tank", required=True,
        domain=[("is_tank", "=", True)],
    )
    destination_tank_id = fields.Many2one(
        "stock.location", string="Destination Tank", required=True,
        domain=[("is_tank", "=", True)],
    )
    quantity = fields.Float(required=True, default=1.0)
    notes = fields.Text()
    picking_id = fields.Many2one("stock.picking", string="Stock Transfer", readonly=True, copy=False)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="draft", required=True, copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "aquarium.fish.transfer",
                ) or "New"
        return super().create(vals_list)

    @api.constrains("source_tank_id", "destination_tank_id")
    def _check_tanks_differ(self):
        for rec in self:
            if rec.source_tank_id == rec.destination_tank_id:
                raise UserError("Source and destination tanks must be different.")

    def _get_picking_type(self):
        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "internal"),
            ("warehouse_id.company_id", "=", self.env.company.id),
        ], limit=1)
        if not picking_type:
            raise UserError(
                "No internal transfer operation type configured for this company.",
            )
        return picking_type

    def action_confirm_transfer(self):
        """Create and validate the underlying stock.picking, preserving the
        original fish batch (lot) across the move.
        """
        for rec in self:
            if rec.state != "draft":
                continue
            if not rec.lot_id.product_id:
                raise UserError(
                    "The selected batch has no linked product; cannot create a stock move.",
                )
            picking_type = rec._get_picking_type()
            picking = self.env["stock.picking"].create({
                "picking_type_id": picking_type.id,
                "location_id": rec.source_tank_id.id,
                "location_dest_id": rec.destination_tank_id.id,
                "is_fish_transfer": True,
                "origin": rec.name,
            })
            move = self.env["stock.move"].create({
                "name": f"Fish transfer {rec.name}",
                "product_id": rec.lot_id.product_id.id,
                "product_uom_qty": rec.quantity,
                "product_uom": rec.lot_id.product_id.uom_id.id,
                "location_id": rec.source_tank_id.id,
                "location_dest_id": rec.destination_tank_id.id,
                "picking_id": picking.id,
            })
            picking.action_confirm()
            picking.action_assign()
            # Odoo 17 renamed stock.move.line's "qty_done" field to
            # "quantity", and added a "picked" boolean that button_validate
            # uses to know a line was actually processed.
            move.move_line_ids.write({
                "lot_id": rec.lot_id.id,
                "quantity": rec.quantity,
                "picked": True,
            })
            if not move.move_line_ids:
                self.env["stock.move.line"].create({
                    "move_id": move.id,
                    "product_id": rec.lot_id.product_id.id,
                    "lot_id": rec.lot_id.id,
                    "location_id": rec.source_tank_id.id,
                    "location_dest_id": rec.destination_tank_id.id,
                    "quantity": rec.quantity,
                    "picked": True,
                    "product_uom_id": rec.lot_id.product_id.uom_id.id,
                })
            picking.button_validate()
            rec.picking_id = picking.id
            # Keep the batch's "assigned tank" pointing at its most recent
            # tank so single-tank views (and default new mortality/sale
            # forms) default sensibly; full historical location is still
            # available via stock.move / stock.quant.
            rec.lot_id.tank_id = rec.destination_tank_id.id
            rec.state = "done"
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "draft":
                rec.state = "cancelled"
            elif rec.picking_id and rec.picking_id.state != "done":
                rec.picking_id.action_cancel()
                rec.state = "cancelled"
        return True
