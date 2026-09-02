# Aquarium Fish Management

Odoo 17 Community addon implementing SRD sections 4.6-4.14 (Phase 2, Plane
project AQS, work items SEQ 29-40).

## SEQ 29 - Data model mapping

The module deliberately builds *on top of* Odoo's Inventory (`stock`)
module wherever a native concept already exists, rather than reinventing
inventory tracking. Custom models are used only where there is no
reasonable native equivalent.

| Business concept | Odoo implementation | Where |
|---|---|---|
| Fish Batch | `stock.lot` (Lot/Serial Number), extended | `models/stock_lot.py` |
| Tank | `stock.location`, extended | `models/stock_location.py` |
| Fish Species | new model `aquarium.fish.species` | `models/fish_species.py` |
| Fish Category | new model `aquarium.fish.category` | `models/fish_species.py` |
| Mortality | new model `aquarium.fish.mortality`, linked to batch (lot) + tank (location) | `models/fish_mortality.py` |
| Tank-to-tank transfer | `stock.picking` / `stock.move` (internal transfer), wrapped by `aquarium.fish.transfer` | `models/stock_picking.py` |
| Fish purchase | `purchase.order.line` extension, creates a `stock.lot` batch on order confirmation | `models/fish_purchase.py` |
| Fish sale (POS) | `pos.order.line` extension (`is_fish_line`, `fish_species_id`, `source_tank_id`, `fish_batch_id`) | `models/pos_order.py` |

**Why `stock.lot` for batches**: every fish purchase is a distinct batch
with its own cost/received-date/quantity - exactly what a lot/serial number
already models, and it comes with lot-level traceability (`stock.move.line`
history, `stock.quant` per-location on-hand quantity) for free.

**Why `stock.location` for tanks**: a tank is a physical place stock can be
in. Modeling it as an internal `stock.location` (flag `is_tank=True`) means
Odoo's own stock moves, quants, and reporting already understand tanks
without any extra plumbing - a tank-to-tank fish move is a completely
ordinary internal transfer.

## Module layout

```
aquarium_fish_management/
├── models/
│   ├── fish_species.py       # aquarium.fish.species, aquarium.fish.category (SEQ 30)
│   ├── stock_lot.py          # fish batch fields + SEQ 34 stock formula (SEQ 31, 34)
│   ├── stock_location.py     # tank fields + QR generation (SEQ 32)
│   ├── fish_mortality.py     # aquarium.fish.mortality (SEQ 35)
│   ├── stock_picking.py      # aquarium.fish.transfer, tank-to-tank (SEQ 36)
│   ├── fish_purchase.py      # purchase.order.line extension (SEQ 38)
│   ├── pos_order.py          # pos.order.line extension + backend API (SEQ 37)
│   └── dashboard.py          # aquarium.fish.dashboard (SEQ 39)
├── controllers/
│   └── tank_scan.py          # public QR scan route (SEQ 33)
├── views/                    # backend views, menus, public scan QWeb template
├── report/                   # act_window "reports" (SEQ 40) + QR label PDF report
├── security/                 # ir.model.access.csv (+ placeholder security XML)
├── data/                     # sequences + starter fish categories
├── static/src/{js,xml}/      # minimal POS UI hook (SEQ 37, see below)
└── tests/
    ├── test_fish_stock_formula.py       # SEQ 34 pure-function tests
    └── test_fish_batch_integration.py   # SEQ 34 via real stock.lot/mortality records
```

## SEQ 34 - Stock calculation engine

```
Current Quantity = Received - Sold - Mortality - Transfers Out + Transfers In
```

Implemented as an isolated, unit-testable pure function:
`stock.lot.compute_fish_stock_quantity(received, sold, mortality,
transferred_out, transferred_in)` in `models/stock_lot.py`. The record-level
computed field `stock.lot.current_quantity` gathers each term from its
proper source and calls that function:

- `received` - stored on the batch at purchase time.
- `sold` - summed from **done** `stock.move.line` records for this lot
  whose destination location has usage `customer`. This reuses Odoo's own
  stock-move history rather than a second parallel ledger.
- `mortality` - summed from `aquarium.fish.mortality` records for this lot
  in state `approved` only (draft/rejected records do not affect stock).
- `transferred_out` / `transferred_in` - summed from done stock moves
  between two tank locations (`is_tank=True`) that either start or end at
  the batch's currently assigned tank; this is what makes the per-tank view
  (e.g. the QR scan page) reflect transfers correctly, while the batch-wide
  total is unaffected because a transfer's in/out cancel out overall.

Test coverage lives in `tests/test_fish_stock_formula.py` (pure-function
edge cases: zero, negative-safe non-clamping, `None`-tolerant, transfers
cancelling at batch-total level) and
`tests/test_fish_batch_integration.py` (real `stock.lot` +
`aquarium.fish.mortality` records, verifying draft mortality doesn't affect
stock but approved mortality does, and mortality percentage).

## What's complete

- SEQ 29: data model + this mapping.
- SEQ 30: `aquarium.fish.species` (+ category model) with photo, notes,
  status, availability, default price.
- SEQ 31: fish batch = `stock.lot`, extended with all requested fields.
- SEQ 32: tank = `stock.location`, extended with capacity/notes/QR
  generation (`qrcode` PNG rendered on the fly) and a printable QR-label
  PDF report action.
- SEQ 33: public, unauthenticated `/aquarium/tank/scan/<token>` route +
  QWeb template, styled for tablet/mobile viewports, showing current stock,
  species/batches, recent sales, and recent mortality for that tank.
- SEQ 34: the formula, isolated + tested (see above).
- SEQ 35: `aquarium.fish.mortality` with reason codes, staff member,
  draft/approved/rejected workflow; approved records feed the SEQ 34
  formula.
- SEQ 36: `aquarium.fish.transfer` creates a real internal
  `stock.picking`/`stock.move`, sets the destination move line's `lot_id`
  to the original batch (so lot/batch identity is preserved across the
  transfer), and validates it - so Odoo's own stock move history is the
  audit trail.
- SEQ 38: confirming a purchase order whose line is flagged
  `is_fish_purchase_line` auto-creates the batch (`stock.lot`) and assigns
  it to the chosen tank.
- SEQ 39: `aquarium.fish.dashboard` (transient snapshot model + form view)
  exposing fish-vs-accessory sales split, a 7-day mortality alert count,
  and best-selling species; `get_dashboard_data()` is a plain importable
  method other widgets/dashboards can call too.
- SEQ 40: report actions/views for current fish stock, fish sold
  (pivot), mortality + mortality % (pivot), tank stock, fish movement
  (Odoo's own `stock.move.line` history filtered to fish lots), and fish
  profitability (revenue/cost/profit/margin per batch).

## What's partial / stubbed - be aware before relying on this in production

- **SEQ 37 (POS fish sales) - backend is solid, POS UI is a minimal hook,
  not a finished screen.** Concretely:
  - **Done**: `pos.order.line` fields (`is_fish_line`, `fish_species_id`,
    `source_tank_id`, `fish_batch_id`); `pos.order.get_available_fish_tanks()`
    - a backend RPC-callable method returning which tanks currently have
    stock for a given species, for the cashier to choose from when more
    than one qualifies; a best-effort post-processing step
    (`_link_fish_lines_to_stock_moves`) that, after an order is
    processed, tries to stamp the chosen batch's lot onto the resulting
    stock move line so `quantity_sold` picks it up correctly.
  - **Stubbed / not production-ready**: the actual POS JS/OWL screen. What
    exists (`static/src/js/pos_fish_sale.js`, `static/src/xml/pos_fish_sale.xml`)
    is a `ProductScreen` patch sketch with an `onClickFishProduct()` handler
    and a tank-selection popup call, wired to a placeholder XML template. It
    is **not connected to a real "fish" product grid entry or button** (no
    template inheritance was added that actually renders a trigger for it),
    and — the more important gap — **the chosen species/tank/batch is
    stored on the in-browser JS `Orderline` object as ad-hoc properties but
    is never serialized into the JSON Odoo sends to the backend** (that
    needs an `Orderline.export_as_JSON` / `init_from_JSON` patch, plus a
    matching field on the backend `pos.order.line` create path to consume
    it, which is not implemented). So today, `_link_fish_lines_to_stock_moves`
    has nothing populated to act on end-to-end. Treat the JS file as a
    documented starting point for whoever picks up full POS screen work,
    not as functioning UI. A cashier can still complete an ordinary POS
    sale of a fish-linked product; what's missing is the *guided*
    species/tank selection flow and its round-trip to the backend fields.
  - Stock reduction timing: unaffected by the above - Odoo's own POS flow
    already only creates/validates stock moves once an order is paid, so
    "stock reduces only after the sale is successfully completed" holds
    regardless of the JS gaps.

- **QR code generation** depends on the optional `qrcode` Python package
  being installed in the Odoo image (`pip install qrcode[pil]`). If it is
  missing, `tank_qr_image` simply comes back empty rather than raising -
  add `qrcode` to the Docker image's Python requirements before relying on
  printed QR labels.

- **Security groups**: fish records currently reuse the standard
  `base.group_user` (read) / `stock.group_stock_manager` (full) groups.
  `security/aquarium_security.xml` is a placeholder for a dedicated "Fish
  Manager" group (e.g. to gate mortality approval) if that's wanted later.

- **Purchase-order view XPath** (`views/fish_purchase_views.xml`) targets
  the standard `purchase.order` line tree's `product_id` column by path;
  this could not be verified against a live Odoo 17 instance in this
  environment (no Odoo runtime available here - see Testing below) and may
  need a small path adjustment if Odoo 17's actual `purchase.purchase_order_form`
  structure differs from what's assumed.

## Testing

No live Odoo runtime was available in the environment this module was
built in, so it could not be installed and exercised against a real
database. What *was* done:

- All `.py` files pass `python3 -m py_compile` (syntax-clean).
- Model/field/decorator conventions were written and reviewed by hand
  against Odoo 17 API conventions (`@api.depends`, `@api.model_create_multi`,
  new-style `fields.Many2one`/`fields.Monetary`, etc).
- `tests/` contains real `odoo.tests.common.TransactionCase` tests for the
  SEQ 34 formula (the one piece explicitly called out as needing test
  coverage) - run them the normal Odoo way once this module is installed
  in a real instance, e.g.:

  ```
  odoo-bin -d <db> -i aquarium_fish_management --test-enable \
      --test-tags /aquarium_fish_management --stop-after-init
  ```

Before first real install, double-check in an actual Odoo 17 instance:
the `purchase.purchase_order_form` XPath above, the POS asset bundle name
used in `__manifest__.py` (`point_of_sale._assets_pos` - this is correct
for 17.0 but bundle names have moved between versions before), and that
`qrcode` is installed in the Python environment.
