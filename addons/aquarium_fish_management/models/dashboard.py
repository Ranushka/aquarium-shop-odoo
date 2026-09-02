# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class AquariumFishDashboard(models.TransientModel):
    """Fish-specific dashboard widgets (SEQ 39), extending the Phase 1
    dashboard (SRD 4.2).

    Implemented as a simple transient "snapshot" model whose single record
    is refreshed on open and rendered with a kanban/form dashboard view -
    this keeps it within Odoo's standard view toolkit rather than requiring
    a bespoke JS dashboard client action.
    """
    _name = "aquarium.fish.dashboard"
    _description = "Aquarium Fish Dashboard"

    fish_sales_total = fields.Monetary(
        string="Fish Sales Total", currency_field="currency_id",
    )
    accessory_sales_total = fields.Monetary(
        string="Accessory Sales Total", currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id,
    )
    mortality_alert_count = fields.Integer(string="Mortality Alerts (7 days)")
    best_selling_species_id = fields.Many2one(
        "aquarium.fish.species", string="Best Selling Species",
    )
    best_selling_species_qty = fields.Float(string="Best Seller Quantity")

    @api.model
    def get_dashboard_data(self):
        """Compute and return dashboard KPIs as a plain dict, for use by a
        client action / kanban widget, or the fish reports menu.
        """
        pos_line_obj = self.env["pos.order.line"]
        fish_lines = pos_line_obj.search([("is_fish_line", "=", True)])
        accessory_lines = pos_line_obj.search([("is_fish_line", "=", False)])

        fish_sales_total = sum(fish_lines.mapped("price_subtotal_incl"))
        accessory_sales_total = sum(accessory_lines.mapped("price_subtotal_incl"))

        week_ago = fields.Date.context_today(self) - timedelta(days=7)
        recent_mortality = self.env["aquarium.fish.mortality"].search([
            ("state", "=", "approved"),
            ("date", ">=", week_ago),
        ])
        mortality_alert_count = len(recent_mortality)

        species_qty = {}
        for line in fish_lines:
            if line.fish_species_id:
                species_qty.setdefault(line.fish_species_id, 0.0)
                species_qty[line.fish_species_id] += line.qty
        best_species = None
        best_qty = 0.0
        for species, qty in species_qty.items():
            if qty > best_qty:
                best_species = species
                best_qty = qty

        return {
            "fish_sales_total": fish_sales_total,
            "accessory_sales_total": accessory_sales_total,
            "mortality_alert_count": mortality_alert_count,
            "best_selling_species_id": best_species.id if best_species else False,
            "best_selling_species_name": best_species.display_name if best_species else "",
            "best_selling_species_qty": best_qty,
        }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        data = self.get_dashboard_data()
        res.update({
            "fish_sales_total": data["fish_sales_total"],
            "accessory_sales_total": data["accessory_sales_total"],
            "mortality_alert_count": data["mortality_alert_count"],
            "best_selling_species_id": data["best_selling_species_id"],
            "best_selling_species_qty": data["best_selling_species_qty"],
        })
        return res

    def action_refresh(self):
        self.ensure_one()
        data = self.get_dashboard_data()
        self.write({
            "fish_sales_total": data["fish_sales_total"],
            "accessory_sales_total": data["accessory_sales_total"],
            "mortality_alert_count": data["mortality_alert_count"],
            "best_selling_species_id": data["best_selling_species_id"],
            "best_selling_species_qty": data["best_selling_species_qty"],
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "aquarium.fish.dashboard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }
