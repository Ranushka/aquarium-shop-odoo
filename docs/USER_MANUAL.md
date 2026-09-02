# User Manual (by role) — Aquarium Shop Odoo

Quick per-role reference for day-to-day use. This assumes the role/permission groups
from AQS task 12 (Cashier / Fish Staff / Manager / Admin) are assigned to real staff
accounts — until then, everyone using the system is the admin account and sees
everything.

## Cashier

Day-to-day billing at the counter.

1. **Open the register**: Point of Sale → Billing Counter → New Session.
2. **Sell an accessory**: tap its tile in the product grid (or scan its barcode) to add
   it to the cart; tap the line to adjust quantity.
3. **Sell a fish**: tap the fish species' tile. If only one tank has stock, it's added
   automatically. If more than one tank has stock, a popup asks which tank to sell from
   — pick it, then confirm quantity.
4. **Apply a discount**: requires manager authorization (per the role matrix) — a
   manager or admin PIN/login is needed to unlock discounting on a line.
5. **Checkout**: pick the customer (or leave as walk-in), choose payment method (cash /
   card / bank transfer / split), confirm. The receipt prints automatically if a printer
   is configured; it always shows the VAT breakdown.
6. **Look up a past sale**: Point of Sale → Orders, filter by date/cashier/payment
   method; reprint from there if the customer needs another copy.
7. **Close the register** at end of shift: Point of Sale → close the session, which
   reconciles cash counted against the system total.

Cashiers cannot see purchase cost, profit figures, or Settings — if a menu you'd expect
is missing, that's the permission matrix working as designed, not a bug.

## Fish / Aquarium Staff

Day-to-day fish care and stock movement.

1. **Receive a new fish batch**: create a Purchase Order for the species (Purchase →
   New, pick the vendor and the fish-species product) and confirm it. Confirming
   auto-creates a batch record and prompts for which tank to assign the stock to.
2. **Record a tank-to-tank transfer**: Aquarium Fish → Transfers → New — pick source
   tank, destination tank, species/batch, quantity. This preserves which original batch
   the fish came from.
3. **Record mortality**: Aquarium Fish → Mortality → New — tank, species, batch,
   quantity, reason code (Disease / Transport Stress / Water Quality / Temperature /
   Unknown / Other), your name, notes. Save as **Draft** first; it does not reduce
   stock until a manager/admin **Approves** it.
4. **Print a tank's QR label**: Aquarium Fish → Tanks → open the tank → Print QR Label.
   Stick it on the tank; scanning it with any phone camera opens a live status page (no
   login needed) showing current stock, species, and recent mortality for that tank —
   handy for a wall-mounted tablet too.
5. **Check current stock per tank/species**: Aquarium Fish → Fish Batches, or the Tanks
   list view — both show live computed stock (Received − Sold − Mortality − Transfers
   Out + Transfers In).

Fish staff cannot see POS, purchases outside fish, expenses, or profit reports.

## Manager

Day-to-day oversight plus everything Cashier and Fish Staff can do.

1. **Dashboard**: Aquarium Fish → Dashboard for fish-specific widgets (sales split,
   mortality alerts, best sellers); Point of Sale / Inventory / Sales apps each have
   their own reporting views for the general Phase 1 numbers (today's sales, payment
   totals, low stock, etc.)
2. **Approve mortality entries**: Aquarium Fish → Mortality — review Draft entries,
   Approve or Reject.
3. **Authorize a cashier's discount**: enter your credentials when a cashier's
   discount attempt prompts for manager approval.
4. **Purchasing (accessories and fish)**: Purchase app — create/confirm purchase
   orders, receive goods.
5. **Expenses**: Expenses app — log rent, utilities, salaries, fish food, repairs,
   etc. against the categories set up for the shop.
6. **Financial reports (limited)**: Invoicing → Reporting → OCA accounting reports has
   the full detail; the permission matrix intends managers to see limited
   profit/expense reporting, not full financials — verify the actual field-level
   restrictions once real manager accounts exist (see AQS task 12).

Managers cannot access Settings/technical configuration.

## Admin / Owner

Full access to everything above plus:

- **Settings** — company profile, VAT/TRN, users, security groups, module
  installation/updates.
- **Full financial reports** — Invoicing → Reporting → OCA accounting reports (General
  Ledger, Trial Balance, Open Items, Aged Partner Balance, VAT Report) and standard
  Odoo Accounting views.
- **Audit log** — Settings → Technical → Audit Logs → Logs (enable Developer Tools
  under Settings → General Settings first if the Technical menu isn't visible).
- **Database management** (backup/restore/duplicate) — the Odoo database-manager
  screen at `/web/database/manager`, needs the master password (see
  `docs/OPERATIONS.md`).
- **Everything infrastructure-level** — see `docs/OPERATIONS.md` for Dokploy/server
  access.

---

This manual describes the system as designed against the SRD's role matrix (AQS task
12). Until real staff accounts with the correct groups exist, verify each restriction
actually holds by testing with a real non-admin account — don't take this document's
word for it in place of that check.
