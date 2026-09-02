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
├── static/src/{js,xml}/      # POS UI wiring (SEQ 37, see below - not live-tested)
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

- **SEQ 37 (POS fish sales) - now wired end-to-end per the Odoo 17.0
  mainline API as best understood from reading Odoo's own
  `point_of_sale` source and long-standing conventions; NOT verified in a
  live browser session (no Odoo runtime was available in this
  environment). Read the "Confidence" subsection below before relying on
  this in production; a human needs to click through a real POS session
  before this goes live.**

  **What's wired now:**
  - `product.product.fish_species_id` (`models/pos_order.py`,
    `ProductProduct`) - a thin computed mirror of
    `aquarium.fish.species.product_id`, so the POS frontend can tell, per
    product tile, whether a product is a fish species.
  - `pos.session._loader_params_product_product()` override
    (`models/pos_order.py`, `PosSession`) adds `fish_species_id` to the
    list of product fields the POS frontend loads at session start - without
    this the field would exist on the backend but never reach the browser.
  - `static/src/js/pos_fish_sale.js` patches
    `ProductScreen.prototype.addProductToOrder(product)`: if the clicked
    product carries a `fish_species_id`, it calls
    `pos.order.get_available_fish_tanks()`, then blocks the sale with an
    `AlertDialog` on zero tanks, auto-selects on exactly one tank, or opens
    a `SelectionPopup` (the "popup" service) on two or more, before adding
    the line.
  - The chosen species/tank/batch is stamped onto the newly created
    `Orderline` via a `setFishSaleData()` method added by the patch, and is
    now serialized into the order JSON via patched
    `Orderline.export_as_JSON()` / `init_from_JSON()` (Odoo 17's POS data
    layer is still the pre-18 plain-class `models.js`, not a reactive OWL
    data model, so this is the standard place to add custom fields to the
    payload).
  - On the backend, `PosOrder._order_line_fields()` is now overridden
    (`models/pos_order.py`) to pull `is_fish_line` /
    `fish_species_id` / `source_tank_id` / `fish_batch_id` out of the raw
    line JSON and into the `pos.order.line` create vals - the base method
    only whitelists the stock fields it already knows about and silently
    drops anything else, which is why this override was needed; without it
    the fields existed on the model but nothing ever populated them from a
    real sale. `_link_fish_lines_to_stock_moves()` (unchanged) now has real
    data to act on.
  - Stock reduction timing: unaffected by any of the above - Odoo's own POS
    flow already only creates/validates stock moves once an order is paid,
    so "stock reduces only after the sale is successfully completed" holds
    regardless.

  **Confidence / what could not be verified (no live Odoo runtime here):**
  - JS syntax was checked with `node --check` and the XML template was
    checked with a plain XML parser; **neither was run inside an actual
    Odoo 17 POS session in a browser.** No click-through, no console
    inspection, no network-payload inspection was possible.
  - The riskiest assumption is the exact click-handler method name on
    `ProductScreen` - this module targets `addProductToOrder(product)`,
    believed correct for Odoo 17.0 mainline, but point-releases have used
    `_clickProduct` at other points in the point_of_sale addon's history.
    A `console.error` fires at module load time if
    `ProductScreen.prototype.addProductToOrder` doesn't exist on the
    running build, so this will be immediately visible in the browser
    console if wrong - if it does fire, rename the patched method to match
    whatever this Odoo build actually calls on a product-tile click.
  - The second assumption is that the `popup` service (`SelectionPopup`)
    is still registered in this exact 17.0 point-release; some later
    point-releases trimmed it in favour of `dialog` only. If it's missing,
    the code falls back to auto-selecting the first tank and logs a
    `console.error` explaining the gap, rather than failing the sale
    silently or throwing - but that fallback means the *guided* tank
    choice would silently not happen for multi-tank species until someone
    ports `_selectFishTank()` to the `dialog` service's `makeAwaitable()`
    pattern.
  - `PosOrder._order_line_fields()` and
    `PosSession._loader_params_product_product()` are believed to be the
    correct 17.0 method names/signatures for, respectively, mapping a raw
    order-line JSON dict into `pos.order.line` create vals and declaring
    which `product.product` fields the POS frontend loads - based on
    reading Odoo's own `point_of_sale/models/pos_order.py` and
    `pos_session.py` conventions, not confirmed against a running 17.0
    instance.
  - `Orderline`/`export_as_JSON`/`init_from_JSON` living in
    `@point_of_sale/app/store/models` with a plain-class (non-reactive)
    shape is believed stable across the 17.0 series (the reactive OWL data
    model rewrite is an 18.0 change), but this could not be confirmed
    against this exact point-release either.

  **What a human should manually test first, in order:**
  1. Install/upgrade the module against a real Odoo 17 instance and open a
     POS session; confirm no JS console errors on load (in particular,
     neither of the two `console.error` messages above should appear).
  2. Create a fish species with `product_id` set to a POS-sellable
     product, give it stock in exactly one tank, and click that product's
     tile in the POS grid - it should add the line immediately with no
     popup.
  3. Give the same species stock in two or more tanks and click its tile
     again - the tank-picker popup should appear; pick a tank and confirm
     the line is added.
  4. Click a fish-species tile for a species with zero tank stock - the
     "No Stock" alert should appear and no line should be added.
  5. Complete a sale containing a fish line, then check the resulting
     `pos.order.line` record's `is_fish_line` / `fish_species_id` /
     `source_tank_id` / `fish_batch_id` fields in the backend - these
     should reflect exactly what was chosen at the POS, and
     `stock.lot.current_quantity` for that batch should drop accordingly
     once the order/picking is validated.
  6. Reopen/reprint an order containing a fish line (exercises
     `init_from_JSON`) and confirm the fish fields survive the round trip.

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
for 17.0 but bundle names have moved between versions before), that
`qrcode` is installed in the Python environment, and - per the SEQ 37
"Confidence" section above - the `ProductScreen.prototype.addProductToOrder`
method name, the `popup` service's availability, and the
`PosOrder._order_line_fields()` / `PosSession._loader_params_product_product()`
method names/signatures the new POS wiring in
`static/src/js/pos_fish_sale.js` and `models/pos_order.py` depends on.
