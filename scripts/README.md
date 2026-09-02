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
