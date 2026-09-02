# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AquariumFishCategory(models.Model):
    """Simple category model for fish species (SRD 4.6).

    Kept as its own model (rather than a plain selection) so shop staff can
    add new categories from the UI without a code change.
    """
    _name = "aquarium.fish.category"
    _description = "Aquarium Fish Category"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_uniq", "unique(name)", "A fish category with this name already exists."),
    ]


class AquariumFishSpecies(models.Model):
    """Fish species master data (SRD 4.6).

    Not a native stock concept, so it is a fully custom model. It is linked
    from aquarium.tank.batch (stock.lot) and aquarium.fish.mortality, and is
    used as the product template's fish species when a product represents a
    sellable fish.
    """
    _name = "aquarium.fish.species"
    _description = "Aquarium Fish Species"
    _order = "common_name"

    name = fields.Char(compute="_compute_name", store=True)
    common_name = fields.Char(required=True, index=True)
    scientific_name = fields.Char()
    category_id = fields.Many2one(
        "aquarium.fish.category", string="Category", required=True,
    )
    default_selling_price = fields.Monetary(
        currency_field="currency_id",
        help="Default selling price used to pre-fill new products/batches for this species.",
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id,
    )
    image_1920 = fields.Image(string="Photo", max_width=1920, max_height=1920)
    notes = fields.Text()
    active = fields.Boolean(default=True)
    is_available = fields.Boolean(
        string="Available for Sale", default=True,
        help="Uncheck to temporarily hide this species from POS/sale without archiving it.",
    )
    status = fields.Selection(
        [
            ("active", "Active"),
            ("seasonal", "Seasonal"),
            ("discontinued", "Discontinued"),
        ],
        default="active", required=True,
    )
    product_id = fields.Many2one(
        "product.product", string="Related Product",
        help="The sellable product (POS/Sales) representing this fish species, if any.",
    )
    batch_ids = fields.One2many("stock.lot", "fish_species_id", string="Batches")
    batch_count = fields.Integer(compute="_compute_batch_count")
    mortality_ids = fields.One2many(
        "aquarium.fish.mortality", "fish_species_id", string="Mortality Records",
    )
    total_current_quantity = fields.Float(
        compute="_compute_total_current_quantity",
        string="Total Current Stock",
        help="Sum of current quantity across all batches of this species.",
    )

    @api.depends("common_name", "scientific_name")
    def _compute_name(self):
        for rec in self:
            if rec.scientific_name:
                rec.name = f"{rec.common_name} ({rec.scientific_name})"
            else:
                rec.name = rec.common_name or ""

    @api.depends("batch_ids")
    def _compute_batch_count(self):
        for rec in self:
            rec.batch_count = len(rec.batch_ids)

    @api.depends("batch_ids.current_quantity")
    def _compute_total_current_quantity(self):
        for rec in self:
            rec.total_current_quantity = sum(rec.batch_ids.mapped("current_quantity"))

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, rec.name or rec.common_name or ""))
        return result
