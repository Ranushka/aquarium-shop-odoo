#!/usr/bin/env python3
"""Add demo/test data to the live Odoo instance for manual testing.

Every record created here is prefixed "[DEMO] " in its name field so it's
obviously not real data, and every created record's model + id is written to
.demo_data_manifest.json (gitignored, local only) so demo_data_remove.py can
delete exactly these records later — nothing else.

Usage:
    export ODOO_ADMIN_PASSWORD='...'
    python3 scripts/demo_data_add.py
"""
import json

from _common import MANIFEST_PATH, connect


def main():
    call = connect()
    manifest = []  # [[model, id], ...] in creation order — removal reverses this,
    # so records get deleted in the opposite order they were created, respecting FKs.

    def create(model, vals):
        rec_id = call(model, "create", vals)
        manifest.append([model, rec_id])
        return rec_id

    # --- Fish categories (reuse existing ones seeded by the module install) ---
    freshwater_cat = call(
        "aquarium.fish.category", "search", [["name", "=", "Freshwater Fish"]]
    )
    freshwater_cat = freshwater_cat[0] if freshwater_cat else None

    # --- Fish species ---
    neon_tetra = create(
        "aquarium.fish.species",
        {
            "common_name": "[DEMO] Neon Tetra",
            "scientific_name": "Paracheirodon innesi",
            "category_id": freshwater_cat,
            "default_selling_price": 8.0,
            "status": "active",
        },
    )
    betta = create(
        "aquarium.fish.species",
        {
            "common_name": "[DEMO] Betta",
            "scientific_name": "Betta splendens",
            "category_id": freshwater_cat,
            "default_selling_price": 25.0,
            "status": "active",
        },
    )

    # --- Tanks ---
    tank_a01 = create(
        "stock.location",
        {
            "name": "[DEMO] Tank A01",
            "usage": "internal",
            "is_tank": True,
            "tank_capacity": 100,
        },
    )
    tank_b01 = create(
        "stock.location",
        {
            "name": "[DEMO] Tank B01",
            "usage": "internal",
            "is_tank": True,
            "tank_capacity": 60,
        },
    )

    # --- Supplier / customer ---
    create(
        "res.partner",
        {
            "name": "[DEMO] Gulf Aquatics Supplier",
            "supplier_rank": 1,
            "phone": "+971500000001",
            "email": "demo-supplier@example.com",
        },
    )
    create(
        "res.partner",
        {
            "name": "[DEMO] Walk-in Test Customer",
            "customer_rank": 1,
            "phone": "+971500000002",
            "email": "demo-customer@example.com",
        },
    )

    # --- Accessory products ---
    for name, price in [
        ("[DEMO] Fish Food 100g", 15.0),
        ("[DEMO] Aquarium Filter Cartridge", 35.0),
        ("[DEMO] Air Pump", 60.0),
    ]:
        create(
            "product.product",
            {"name": name, "list_price": price, "sale_ok": True, "available_in_pos": True},
        )

    # --- A fish batch (stock.lot) for the Neon Tetra, assigned to Tank A01 ---
    # Needs a product to attach the lot to — reuse/create one linked to the species.
    neon_product = create(
        "product.product",
        {
            "name": "[DEMO] Neon Tetra (fish product)",
            "list_price": 8.0,
            "sale_ok": True,
            "available_in_pos": True,
            "tracking": "lot",
        },
    )
    create(
        "stock.lot",
        {
            "name": "[DEMO]-BATCH-001",
            "product_id": neon_product,
            "is_fish_batch": True,
            "fish_species_id": neon_tetra,
            "tank_id": tank_a01,
            "quantity_received": 50,
            "cost_per_fish": 2.5,
        },
    )

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Created {len(manifest)} demo records.")
    print(f"Manifest written to {MANIFEST_PATH}")
    print("Run demo_data_remove.py to clean up.")


if __name__ == "__main__":
    main()
