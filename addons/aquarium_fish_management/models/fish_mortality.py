# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class AquariumFishMortality(models.Model):
    """Fish mortality management (SRD 4.10 / SEQ 35).

    Linked to a batch/lot + a tank (location). Approved records
    automatically reduce available stock by feeding into the SEQ 34 formula
    (stock.lot.current_quantity), since that field's compute reads only
    mortality records in state='approved'.
    """
    _name = "aquarium.fish.mortality"
    _description = "Aquarium Fish Mortality Record"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Reference", default="New", copy=False, readonly=True,
    )
    date = fields.Date(required=True, default=fields.Date.context_today)
    tank_id = fields.Many2one(
        "stock.location", string="Tank", required=True,
        domain=[("is_tank", "=", True)],
    )
    fish_species_id = fields.Many2one(
        "aquarium.fish.species", string="Fish Species", required=True,
    )
    lot_id = fields.Many2one(
        "stock.lot", string="Batch", required=True,
        domain=[("is_fish_batch", "=", True)],
    )
    quantity = fields.Float(string="Quantity", required=True, default=1.0)
    reason = fields.Selection(
        [
            ("disease", "Disease"),
            ("transport_stress", "Transport Stress"),
            ("water_quality", "Water Quality"),
            ("temperature", "Temperature"),
            ("unknown", "Unknown"),
            ("other", "Other"),
        ],
        required=True, default="unknown",
    )
    staff_member_id = fields.Many2one(
        "res.users", string="Staff Member", default=lambda self: self.env.user,
    )
    notes = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="draft", required=True, copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "aquarium.fish.mortality",
                ) or "New"
        return super().create(vals_list)

    @api.constrains("quantity")
    def _check_quantity(self):
        for rec in self:
            if rec.quantity <= 0:
                raise UserError("Mortality quantity must be greater than zero.")

    @api.onchange("lot_id")
    def _onchange_lot_id(self):
        for rec in self:
            if rec.lot_id:
                rec.fish_species_id = rec.lot_id.fish_species_id
                if rec.lot_id.tank_id:
                    rec.tank_id = rec.lot_id.tank_id

    def action_approve(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft mortality records can be approved.")
            rec.state = "approved"
        return True

    def action_reject(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft mortality records can be rejected.")
            rec.state = "rejected"
        return True

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = "draft"
        return True
