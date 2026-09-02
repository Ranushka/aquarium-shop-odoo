# Demo data scripts

For manually testing the live Odoo instance (POS, fish batches, tanks, etc.)
without using real business data.

```bash
export ODOO_ADMIN_PASSWORD='...'   # see this project's memory entry / docs/OPERATIONS.md
python3 scripts/demo_data_add.py       # creates a small set of [DEMO]-prefixed records
python3 scripts/demo_data_remove.py    # deletes exactly those records, nothing else
```

`demo_data_add.py` creates 2 fish species, 2 tanks, a supplier, a customer, 3
accessory products, a fish product + one fish batch (stock.lot) assigned to a
tank — enough to click through a POS sale, a fish transfer, and a mortality
entry. Everything it creates is named with a `[DEMO]` prefix and its exact
(model, id) is logged to `.demo_data_manifest.json` (gitignored — local
state, not portable across environments).

`demo_data_remove.py` reads that manifest and deletes precisely those
records, in reverse creation order (respects foreign keys — e.g. the fish
batch is deleted before the tank it's assigned to). It does **not** match by
name prefix or any other heuristic, so it can never touch real data even if
someone reuses the "[DEMO]" convention by hand later — only records this
script itself created and logged get removed.

Re-running `demo_data_add.py` without removing first will just add a second
copy of everything (it doesn't check for existing demo data) — run
`demo_data_remove.py` first if you want a clean slate.

## Important: this script does NOT create real stock movements, by design

The fish batch it creates has `quantity_received` set as a plain field on the
`stock.lot` record, but no real `stock.quant`/`stock.move` — so it's fully,
cleanly removable, but it will **not** show up in the POS's tank-availability
check (`get_available_fish_tanks`), which reads actual on-hand quantity via
`stock.quant`, not the lot's own field. If you need to test the POS
multi-tank picker specifically, you need real stock — and that comes with a
real Odoo constraint worth knowing about first:

**Once a product/lot/location has a real `stock.quant` or `stock.move`
against it, Odoo will not let anyone — including admin — hard-delete that
quant, or the lot/product/location referencing it.** This is intentional:
inventory audit trails are append-only by design, same as in any real ERP.
The only way to "remove" that stock is another inventory count bringing the
quantity back to 0 (not a delete), and the lot/product/tank involved can only
be **archived** (hidden from all normal views), not deleted, once they carry
that history.

Practically: if you need to test something that requires real POS stock
availability, do it deliberately and expect to end up with a small number of
permanently-archived (inactive, invisible, zero-quantity) records afterward
— that's not a bug in these scripts, it's Odoo protecting inventory
integrity, and it's exactly what will happen in production too once real
stock starts moving. Don't extend `demo_data_add.py` to create real quants
without updating this note and accepting that trade-off.
