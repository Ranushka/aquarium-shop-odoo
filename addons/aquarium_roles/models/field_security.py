# -*- coding: utf-8 -*-
"""Real, ORM-enforced field-level access control for purchase-cost / profit
figures (not just view-level `groups="..."` hiding on a <field> tag, which
only affects that one view - anyone with model read access could still
fetch the value via read()/search_read() over XML-RPC/JSON-RPC/the ORM).

Odoo 17's ir.model.fields.write() explicitly refuses to alter a "base"
field's properties (state != 'manual') via a normal write - including from
an XML <record model="ir.model.fields"> data file (raises "Properties of
base fields cannot be altered in this manner!"). The supported way to
restrict an existing base field's `groups` is exactly what this file does:
re-declare the field on an inheriting model with only the changed keyword
argument - Odoo's field-merging across the MRO keeps every other property
(compute, store, currency_field, digits, ...) from the original definition
in aquarium_fish_management/purchase/product and only replaces `groups`.

Every field below previously carried either no group restriction at all
(aquarium_fish_management's stock.lot fields, purchase.order.line.price_unit)
or Odoo core's own `groups="base.group_user"` (product template/product
standard_price - i.e. "any internal user", not restrictive at all given
every Aquarium role is an internal user). Restricting to
group_aquarium_financial_data (implied only by Aquarium Manager and Aquarium
Administrator - see security/aquarium_role_groups.xml) means a Cashier or
Fish Staff user's read() of any of these fields raises AccessError, not an
omitted/empty value - verified live, see the module README.
"""
from odoo import fields, models

FINANCIAL_GROUP = "aquarium_roles.group_aquarium_financial_data"


class StockLot(models.Model):
    _inherit = "stock.lot"

    # aquarium_fish_management (SEQ 40): per-fish purchase cost and derived
    # profitability figures on a fish batch.
    cost_per_fish = fields.Monetary(groups=FINANCIAL_GROUP)
    total_purchase_cost = fields.Monetary(groups=FINANCIAL_GROUP)
    total_sales_revenue = fields.Monetary(groups=FINANCIAL_GROUP)
    profit = fields.Monetary(groups=FINANCIAL_GROUP)
    profit_margin = fields.Float(groups=FINANCIAL_GROUP)


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    # Per-unit purchase cost entered on a PO line - the exact figure
    # fish_purchase.py copies into stock.lot.cost_per_fish on confirm.
    price_unit = fields.Float(groups=FINANCIAL_GROUP)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Standard Odoo "Cost" field. Core ships this with
    # groups="base.group_user" (i.e. visible to any internal user) - every
    # Aquarium role is an internal user, so that default is not restrictive
    # at all here. Replacing it with the financial-data gate group is what
    # actually enforces "Cashier/Fish Staff: no profit reports".
    standard_price = fields.Float(groups=FINANCIAL_GROUP)


class ProductProduct(models.Model):
    _inherit = "product.product"

    standard_price = fields.Float(groups=FINANCIAL_GROUP)
