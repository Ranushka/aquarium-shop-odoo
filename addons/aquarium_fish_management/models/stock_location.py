# -*- coding: utf-8 -*-
import base64
from io import BytesIO

from odoo import api, fields, models

try:
    import qrcode
except ImportError:  # pragma: no cover - optional dependency
    qrcode = None


class StockLocation(models.Model):
    """Tank = Odoo Stock Location (SRD 4.8 / SEQ 29 mapping).

    A tank is a stock.location flagged with is_tank=True, carrying capacity,
    a display code, and a generated QR code that links to the public scan
    view (SEQ 33).
    """
    _inherit = "stock.location"

    is_tank = fields.Boolean(
        string="Is Tank", default=False, index=True,
        help="Flag this stock location as a physical aquarium tank.",
    )
    tank_code = fields.Char(
        string="Tank ID",
        help="Short unique tank code, e.g. A01, A02, B01.",
    )
    tank_display_name = fields.Char(string="Tank Name")
    tank_capacity = fields.Integer(
        string="Capacity", help="Maximum number of fish this tank can hold.",
    )
    tank_notes = fields.Text(string="Tank Notes")
    tank_qr_token = fields.Char(
        string="QR Token", copy=False, readonly=True,
        help="Opaque token used in the public scan URL, generated once per tank.",
    )
    tank_qr_image = fields.Binary(
        string="QR Code", compute="_compute_tank_qr_image", store=False,
        attachment=False,
    )
    tank_scan_url = fields.Char(
        string="Scan URL", compute="_compute_tank_scan_url",
    )

    # --- current stock / batches, visible per tank (SEQ 32) -------------
    current_fish_stock = fields.Float(
        string="Current Fish Stock", compute="_compute_tank_stock_info",
    )
    batch_ids = fields.Many2many(
        "stock.lot", string="Assigned Batches", compute="_compute_tank_stock_info",
    )
    batch_count = fields.Integer(compute="_compute_tank_stock_info")

    _sql_constraints = [
        ("tank_code_uniq", "unique(tank_code)", "Tank ID must be unique."),
    ]

    @api.depends("is_tank")
    def _compute_tank_stock_info(self):
        for rec in self:
            if not rec.is_tank:
                rec.current_fish_stock = 0.0
                rec.batch_ids = [(5, 0, 0)]
                rec.batch_count = 0
                continue
            quants = self.env["stock.quant"].search([
                ("location_id", "=", rec.id),
                ("lot_id", "!=", False),
                ("lot_id.is_fish_batch", "=", True),
            ])
            rec.current_fish_stock = sum(quants.mapped("quantity"))
            lots = quants.mapped("lot_id")
            rec.batch_ids = [(6, 0, lots.ids)]
            rec.batch_count = len(lots)

    def _get_or_create_qr_token(self):
        self.ensure_one()
        if not self.tank_qr_token:
            token = f"tank-{self.id}-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"
            self.tank_qr_token = token
        return self.tank_qr_token

    @api.depends("tank_qr_token", "is_tank")
    def _compute_tank_scan_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", default="",
        )
        for rec in self:
            if not rec.is_tank:
                rec.tank_scan_url = False
                continue
            token = rec.tank_qr_token or rec._get_or_create_qr_token()
            rec.tank_scan_url = f"{base_url}/aquarium/tank/scan/{token}"

    @api.depends("tank_scan_url", "is_tank")
    def _compute_tank_qr_image(self):
        for rec in self:
            if not rec.is_tank or not rec.tank_scan_url or qrcode is None:
                rec.tank_qr_image = False
                continue
            img = qrcode.make(rec.tank_scan_url)
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            rec.tank_qr_image = base64.b64encode(buffer.getvalue())

    def action_generate_qr(self):
        """Explicit action (button) to (re)generate the QR token/code."""
        for rec in self:
            rec._get_or_create_qr_token()
        return True
