# -*- coding: utf-8 -*-
"""Integration-level coverage for SEQ 34, exercising the computed fields on
an actual stock.lot record (fish batch) with a linked mortality record,
rather than calling the pure formula function directly.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFishBatchIntegration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env["aquarium.fish.category"].create({
            "name": "Test Freshwater",
        })
        cls.species = cls.env["aquarium.fish.species"].create({
            "common_name": "Test Neon Tetra",
            "scientific_name": "Paracheirodon innesi",
            "category_id": cls.category.id,
            "default_selling_price": 5.0,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Neon Tetra (Test)",
            "type": "product",
            "tracking": "lot",
        })
        cls.tank = cls.env["stock.location"].create({
            "name": "Test Tank A01",
            "usage": "internal",
            "is_tank": True,
            "tank_code": "TA01",
            "tank_capacity": 100,
        })

    def test_current_quantity_no_mortality(self):
        lot = self.env["stock.lot"].create({
            "name": "TEST-BATCH-001",
            "product_id": self.product.id,
            "company_id": self.env.company.id,
            "fish_species_id": self.species.id,
            "quantity_received": 50,
            "cost_per_fish": 2.0,
            "tank_id": self.tank.id,
        })
        self.assertTrue(lot.is_fish_batch, "Setting fish_species_id should flag is_fish_batch.")
        self.assertEqual(lot.total_purchase_cost, 100.0)
        # No sales, no mortality, no transfers recorded yet.
        self.assertEqual(lot.current_quantity, 50)

    def test_current_quantity_reduced_by_approved_mortality(self):
        lot = self.env["stock.lot"].create({
            "name": "TEST-BATCH-002",
            "product_id": self.product.id,
            "company_id": self.env.company.id,
            "fish_species_id": self.species.id,
            "quantity_received": 40,
            "cost_per_fish": 1.5,
            "tank_id": self.tank.id,
        })
        mortality = self.env["aquarium.fish.mortality"].create({
            "date": "2026-01-01",
            "tank_id": self.tank.id,
            "fish_species_id": self.species.id,
            "lot_id": lot.id,
            "quantity": 5,
            "reason": "disease",
        })
        # Draft mortality must NOT affect stock yet.
        self.assertEqual(lot.current_quantity, 40)

        mortality.action_approve()
        # Approved mortality must reduce current_quantity.
        self.assertEqual(lot.current_quantity, 35)
        self.assertAlmostEqual(lot.mortality_percentage, 12.5)

    def test_rejected_mortality_does_not_reduce_stock(self):
        lot = self.env["stock.lot"].create({
            "name": "TEST-BATCH-003",
            "product_id": self.product.id,
            "company_id": self.env.company.id,
            "fish_species_id": self.species.id,
            "quantity_received": 20,
            "cost_per_fish": 1.0,
            "tank_id": self.tank.id,
        })
        mortality = self.env["aquarium.fish.mortality"].create({
            "date": "2026-01-01",
            "tank_id": self.tank.id,
            "fish_species_id": self.species.id,
            "lot_id": lot.id,
            "quantity": 3,
            "reason": "unknown",
        })
        mortality.action_reject()
        self.assertEqual(lot.current_quantity, 20)

    def test_non_fish_lot_reports_zero(self):
        """A regular (non-fish) lot should not blow up the fish formula and
        should simply report zeros for fish-specific quantities.
        """
        plain_product = self.env["product.product"].create({
            "name": "Plain Accessory (Test)",
            "type": "product",
            "tracking": "lot",
        })
        lot = self.env["stock.lot"].create({
            "name": "TEST-PLAIN-001",
            "product_id": plain_product.id,
            "company_id": self.env.company.id,
        })
        self.assertFalse(lot.is_fish_batch)
        self.assertEqual(lot.current_quantity, 0.0)
