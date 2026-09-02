# -*- coding: utf-8 -*-
"""SEQ 34 - fish stock calculation engine.

Current Quantity = Received - Sold - Mortality - Transfers Out + Transfers In

These tests target the isolated pure-function implementation directly
(stock.lot.compute_fish_stock_quantity), so they run fast and pin down the
formula's arithmetic without needing any stock-move/purchase fixtures.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFishStockFormula(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Lot = self.env["stock.lot"]

    def test_basic_formula(self):
        """Plain received/sold/mortality, no transfers."""
        qty = self.Lot.compute_fish_stock_quantity(
            received=100, sold=20, mortality=5,
            transferred_out=0, transferred_in=0,
        )
        self.assertEqual(qty, 75)

    def test_formula_with_transfers(self):
        """Transfers in/out both applied correctly."""
        qty = self.Lot.compute_fish_stock_quantity(
            received=50, sold=10, mortality=2,
            transferred_out=15, transferred_in=5,
        )
        # 50 - 10 - 2 - 15 + 5 = 28
        self.assertEqual(qty, 28)

    def test_formula_all_zero(self):
        qty = self.Lot.compute_fish_stock_quantity(
            received=0, sold=0, mortality=0,
            transferred_out=0, transferred_in=0,
        )
        self.assertEqual(qty, 0)

    def test_formula_handles_none_gracefully(self):
        """None values (e.g. unset float fields) should behave like zero."""
        qty = self.Lot.compute_fish_stock_quantity(
            received=40, sold=None, mortality=None,
            transferred_out=None, transferred_in=None,
        )
        self.assertEqual(qty, 40)

    def test_formula_can_go_negative(self):
        """The pure function does not clamp to zero - overselling or
        over-reporting mortality should surface as a visibly wrong
        (negative) number rather than being silently hidden, so staff can
        catch data-entry mistakes.
        """
        qty = self.Lot.compute_fish_stock_quantity(
            received=10, sold=15, mortality=0,
            transferred_out=0, transferred_in=0,
        )
        self.assertEqual(qty, -5)

    def test_transfers_cancel_out_at_batch_total_level(self):
        """When a batch's transfers in and out are equal (e.g. summed
        across all tanks for the whole batch), the net effect on current
        quantity is zero - transfers only redistribute stock, they never
        change the total headcount for a batch.
        """
        qty_no_transfer = self.Lot.compute_fish_stock_quantity(
            received=30, sold=5, mortality=1,
            transferred_out=0, transferred_in=0,
        )
        qty_with_equal_transfers = self.Lot.compute_fish_stock_quantity(
            received=30, sold=5, mortality=1,
            transferred_out=12, transferred_in=12,
        )
        self.assertEqual(qty_no_transfer, qty_with_equal_transfers)
