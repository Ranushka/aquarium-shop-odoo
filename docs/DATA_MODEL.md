# Data Model Reference — Aquarium Shop Odoo

Schema/model reference for AQS task 50. Covers how this system maps SRD concepts onto
Odoo models — standard Odoo models used as-is, and the custom fish/tank module.

## Standard Odoo models (no customization)

| SRD concept | Odoo model | Notes |
|---|---|---|
| Accessory product | `product.product` / `product.template` | Standard catalog, barcode field used for scanning |
| Sale / receipt | `pos.order` / `pos.order.line` | Extended — see below |
| Invoice | `account.move` | UAE VAT via `l10n_ae` fiscal positions/taxes |
| Supplier | `res.partner` (vendor) | Standard vendor contact |
| Customer | `res.partner` (customer) | Standard customer contact, purchase history via linked orders |
| Purchase order (accessories) | `purchase.order` / `purchase.order.line` | Standard; fish purchases extend the line, see below |
| Stock movement | `stock.move` / `stock.picking` | Standard Odoo inventory transfers |
| Expense | `hr.expense` | Standard Expenses app |
| User / role | `res.users` / `res.groups` | Role matrix (AQS task 12) implemented as group assignments |
| Audit entry | `auditlog.log` (OCA `auditlog`) | See `docs/OPERATIONS.md` for which models are audited |
| Financial report | OCA `account_financial_report` wizards (`general.ledger.report.wizard`, etc.) | Not a data model per se — report wizards over `account.move.line` |

## Custom fish/tank module (`addons/aquarium_fish_management/`)

This module extends existing Odoo inventory models rather than building a parallel
system, per the SEQ 29 design decision (documented in the module's own README):

| SRD concept | Implementation | Why |
|---|---|---|
| **Fish Species** | New model `aquarium.fish.species` (+ `aquarium.fish.category`) | Not a stock concept natively — genuinely new master data |
| **Fish Batch** | Extends `stock.lot` (Odoo's Lot/Serial Number) | Odoo already tracks per-lot quantity, cost, and movement history; extended with `fish_species_id`, `supplier_id`, `date_received`, `quantity_received`, `cost_per_fish`, `tank_id` |
| **Tank** | Extends `stock.location` | Odoo already supports multi-location stock; extended with `is_tank`, `tank_capacity`, QR code fields |
| **Mortality** | New model `aquarium.fish.mortality` | Linked to batch (`stock.lot`) + tank (`stock.location`); draft/approved/rejected workflow, reason code selection |
| **Tank Transfer** | New model `aquarium.fish.transfer` wrapping `stock.picking`/`stock.move` | Preserves lot identity through an internal transfer |
| **Fish Purchase** | Extends `purchase.order.line` | Auto-creates a `stock.lot` batch + tank assignment on order confirmation |
| **Fish POS Sale** | Extends `pos.order.line` (+ POS frontend JS) | Adds `is_fish_line`, `fish_species_id`, `source_tank_id`, `fish_batch_id` |
| **Stock formula** | `stock.lot.compute_fish_stock_quantity()` (pure function) + computed fields on `stock.lot` | `Received − Sold − Mortality − Transfers Out + Transfers In`; covered by `tests/test_fish_stock_formula.py` and `tests/test_fish_batch_integration.py` |
| **Dashboard** | New model `aquarium.fish.dashboard` | Fish vs. accessory sales split, mortality alerts, best sellers |
| **Tank QR scan page** | Controller `controllers/tank_scan.py`, route `/aquarium/tank/scan/<token>` | Public (no login), mobile-optimized QWeb template |

For field-by-field detail, read the module source directly — `models/stock_lot.py`
(batch + stock formula), `models/stock_location.py` (tank), `models/fish_mortality.py`,
`models/fish_purchase.py`, `models/pos_order.py`, `models/dashboard.py`. Each file has
docstrings tying it back to the SRD section and SEQ number it implements.

## Entity relationships (simplified)

```
aquarium.fish.species ──┬── stock.lot (fish batch) ──┬── stock.location (tank, via tank_id)
                         │                             │
                         │                             ├── stock.move.line (sales, done, dest=customer)
                         │                             │
                         │                             ├── aquarium.fish.mortality (approved)
                         │                             │
                         │                             └── aquarium.fish.transfer → stock.picking
                         │
                         └── pos.order.line (is_fish_line=True, via fish_species_id)

purchase.order.line ──→ creates stock.lot (batch) on order confirmation
```

This is deliberately not a database ER diagram with column-level detail — Odoo's own
Settings → Technical → Database Structure → Models (with Developer Tools enabled) gives
a live, always-accurate field list per model, which is more reliable than a hand-written
copy that will drift as the module evolves.
