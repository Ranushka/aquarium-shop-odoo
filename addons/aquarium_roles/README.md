# Aquarium Shop Roles &amp; Permissions

Implements the AQS project's role/permission matrix ("User accounts, roles &amp;
permissions matrix", SEQ 12 / SRD 3 &amp; 6) as real, testable Odoo security
configuration. This module adds **no new models** - it is pure security
config (four `res.groups`, `implied_ids` onto Odoo's own built-in application
groups, `ir.model.fields.groups` for real field-level access control, one
`ir.rule` gap-fix, and two menu overrides) layered on top of
`aquarium_fish_management` and Odoo's Point of Sale / Inventory / Purchase /
Invoicing apps.

No real staff user accounts are created here - assigning a real person to one
of the four groups below is a one-click step (Settings -> Users -> pick the
group) once the business owner supplies real names. That's tracked as a
separate, still-blocked AQS task.

## Role -> group mapping

| Role | Group (this module) | Implies (Odoo/aquarium_fish_management groups) |
|---|---|---|
| Cashier | `group_aquarium_cashier` | `point_of_sale.group_pos_user` |
| Fish/Aquarium Staff | `group_aquarium_fish_staff` | `stock.group_stock_user`, `stock.group_production_lot`, `stock.group_stock_multi_locations` |
| Manager | `group_aquarium_manager` | Cashier + Fish Staff + `stock.group_stock_manager` + `purchase.group_purchase_user` + `account.group_account_invoice` + `group_aquarium_financial_data` |
| Administrator/Owner | `group_aquarium_admin` | Manager + `base.group_system` + `account.group_account_manager` + `purchase.group_purchase_manager` + `point_of_sale.group_pos_manager` |

`group_aquarium_financial_data` is a fifth, internal-only "gate" group (not a
job role, never assigned directly) implied only by Manager and Admin. It is
the `groups` value on every field-level restriction below.

All Odoo group XML ids above were confirmed **live** against this instance
via `ir.model.data`/`res.groups` XML-RPC lookups on 2026-09-02, not guessed
from memory of stock Odoo. See `security/aquarium_role_groups.xml` for the
full reasoning behind each `implied_ids` choice (in particular, why Cashier
does *not* get `stock.group_stock_user` - that group grants write access to
stock operations, which would make "inventory view-only" false).

### What each role can/can't do, and how

- **Cashier** - POS billing (full, via `point_of_sale.group_pos_user`).
  Inventory is intentionally **not** wired through `stock.group_stock_user`
  (which is read/write) - the "view-only" requirement is satisfied by simply
  not granting a group that would allow writes; no purchase group, so no
  Purchase app access at all. No fish management - see the "known gap"
  section below, this needed an explicit `ir.rule`, not just an omitted
  group. No profit/cost fields (field-level restricted, see below). No
  Settings.
- **Fish Staff** - Fish management full (via `aquarium_fish_management`'s own
  access rules, most granted to `base.group_user`/`stock.group_stock_manager`
  - unaffected by this module). Inventory "limited" via
  `stock.group_stock_user` (not `stock.group_stock_manager` - can't
  reconfigure warehouses). No POS group, no purchase group -> no POS/Purchase
  app access. No profit/cost fields. No Settings.
- **Manager** - Full POS, full inventory (`stock.group_stock_manager`), full
  purchasing, full fish management (inherits Fish Staff). "Limited" expenses:
  `account.group_account_invoice` (Billing - create/post invoices) but not
  `account.group_account_manager` (Billing Administrator - that's what
  unlocks the OCA P&amp;L/Balance Sheet/Trial Balance reports on this instance).
  "Limited" profit reports: Manager *is* in `group_aquarium_financial_data`,
  so the cost/profit fields on a fish batch are genuinely readable - "limited"
  here means "sees the numbers, doesn't run the full accounting reports",
  matching the spec's own wording rather than hiding the fields entirely. No
  Settings.
- **Admin** - Everything. Implies Manager plus `base.group_system`,
  `account.group_account_manager`, `purchase.group_purchase_manager`,
  `point_of_sale.group_pos_manager`.

## Field-level restriction (real, not just view-level)

A `groups` attribute on a `<field>` in a view only hides the field from that
particular view - anyone with model read access can still fetch it via
`read()`/`search_read()` over XML-RPC/JSON-RPC or the ORM directly. A field's
own `groups` keyword (set at the Python field-definition level) is enforced
by the ORM's own field-access check on every read/write route, which is the
real security boundary the spec asks for.

`models/field_security.py` re-declares each field below on an inheriting
model with only `groups=` changed - Odoo merges field attributes across the
MRO, so `compute`/`store`/`currency_field`/etc. all still come from the
original definition in `aquarium_fish_management`/`purchase`/`product`.
This is a deliberate departure from the commonly-documented
`<record model="ir.model.fields">` XML pattern: on this Odoo 17 instance
that XML approach fails outright (`ir.model.fields.write()` refuses to alter
any property of a non-"manual" field - confirmed live, see
`security/aquarium_field_security.xml`'s comments for the exact error and
reasoning) - the Python field-redeclaration approach below is what actually
works:

| Model | Field | What it is |
|---|---|---|
| `stock.lot` | `cost_per_fish` | Per-fish purchase cost on a batch |
| `stock.lot` | `total_purchase_cost` | Batch purchase cost total |
| `stock.lot` | `total_sales_revenue` | Batch sales revenue (SEQ 40) |
| `stock.lot` | `profit` | Batch profit (SEQ 40) |
| `stock.lot` | `profit_margin` | Batch profit margin % (SEQ 40) |
| `purchase.order.line` | `price_unit` | Per-unit purchase cost entered on a PO line |
| `product.template` | `standard_price` | Standard "Cost" field on any product |
| `product.product` | `standard_price` | Same, variant level |

Only `group_aquarium_manager` and `group_aquarium_admin` carry
`group_aquarium_financial_data` - Cashier and Fish Staff never do, in any
`implied_ids` chain, so a `read()` of any of these fields by a
Cashier/Fish-Staff-only user raises `AccessError`, not an empty/omitted
value. Verified live for real - see below.

## Defense-in-depth `ir.rule` for fish management (not, as first assumed, an active leak)

`aquarium_fish_management`'s own `security/ir.model.access.csv` grants
`aquarium.fish.mortality` and `aquarium.fish.transfer` read+write+create to
`base.group_user` - i.e. to **every internal user**, regardless of role,
because that module predates this role matrix. The initial assumption while
building this module was that `point_of_sale.group_pos_user` (which Cashier
gets) implies `base.group_user`, which would have meant a Cashier inherits
fish-management *write* access purely by being an internal user. **Checked
live and that assumption was wrong**: `res.groups.read` on
`point_of_sale.group_pos_user`'s `implied_ids` on this instance returns an
empty list, and a real Cashier test user's own `groups_id` after creation
was exactly `[Aquarium Cashier, Point of Sale/User]` - no `base.group_user`.
So today, Cashier is already blocked from `aquarium.fish.mortality`/
`aquarium.fish.transfer` by `ir.model.access.csv` alone.

The `ir.rule` in `security/aquarium_field_security.xml` is kept anyway as a
deliberate safety net, not a fix for an observed leak - in case a real
Cashier account ever also ends up with `base.group_user` for some other
legitimate reason (portal features, a future Odoo version changing that
implication, etc.). `ir.model.access.csv` rows for the same model OR
together (any matching row grants access), so a new CSV row in this module
couldn't *remove* what `aquarium_fish_management`'s row grants if that ever
did apply - `ir.rule` is the right tool for that: rules combine with **AND**
on top of whatever `ir.model.access.csv` allows, and a rule's own `groups`
field scopes it to only the users who should be denied.
`security/aquarium_field_security.xml` adds a `domain_force = [('id', '=', 0)]`
(never matches - id 0 is never a real record) rule on both models, scoped
via `groups` to `group_aquarium_cashier` only - Fish Staff/Manager/Admin
never carry that group, so they're unaffected. This is deliberately scoped
narrowly (Cashier only) rather than as a global deny-by-default rule, to
avoid accidentally blocking a future role that isn't Fish Staff/Manager/Admin
either - if more roles are added later, revisit this. (The classic
`[(1, '=', 1)]`/`[(1, '=', 0)]` int-literal "always true/false" domain
trick from older Odoo versions does not work on this instance either -
Odoo 17's stricter domain validator rejects it with "Invalid domain: 'int'
object has no attribute 'split'", confirmed live - hence `[('id', '=', 0)]`.)

This module does not otherwise touch `aquarium_fish_management`'s own
`security/` files, by design (per the task brief, to avoid any risk of
conflicting with concurrent work on that module's POS pieces).

## Menu-level hiding (defense in depth, not the security boundary)

`security/aquarium_menu_restrictions.xml` re-declares two of
`aquarium_fish_management`'s existing menuitem xmlids (a module can extend
another module's record by reusing its external id once it depends on that
module - no edits to that module's own `views/menus.xml`):

- `menu_aquarium_root` ("Aquarium Fish" app menu) - hidden from Cashier (kept
  for Fish Staff/Manager/Admin).
- `menu_aquarium_report_profitability` ("Fish Profitability" report) - kept
  for Manager/Admin only (matches who's actually in
  `group_aquarium_financial_data`).

This is purely a UI nicety on top of the real, field-level and
`ir.rule`-enforced restrictions above - it stops a restricted user from
clicking into a screen that would immediately throw `AccessError`, it is
*not* what makes the data actually inaccessible.

## Manual verification checklist

1. **Install**: Settings -> Apps -> search "Aquarium Shop Roles &amp;
   Permissions" -> Install (or `ir.module.module.button_immediate_install`
   over XML-RPC as admin). Confirm the four role groups + the internal gate
   group appear under Settings -> Users &amp; Companies -> Groups, category
   "Aquarium Shop Roles".
2. **Assign**: create (or reuse) a real `res.users` record, set its `groups_id`
   to *exactly one* of the four role groups (Odoo will also apply that
   group's `implied_ids` automatically).
3. **Cashier checks** (log in as a Cashier-only user):
   - Settings menu is absent from the top bar.
   - "Aquarium Fish" app menu is absent entirely.
   - Point of Sale is fully usable (open a session, ring up a sale).
   - Inventory is visible (stock levels) but no ability to validate/edit
     transfers.
   - Purchase app is absent (no `purchase.group_purchase_user`).
   - **Real proof, not just UI absence**: authenticate as that user's own uid
     over XML-RPC and call
     `execute_kw(db, cashier_uid, cashier_pw, 'stock.lot', 'read', [[some_fish_batch_id], ['cost_per_fish']])`
     - this must raise an `AccessError` fault (field-level ORM restriction),
     not return `0.0` or omit the key silently. Same for `profit`,
     `total_purchase_cost` on `stock.lot`, and `standard_price` on
     `product.template`. Also confirm
     `execute_kw(..., 'aquarium.fish.mortality', 'search', [[]])` raises
     `AccessError` (the `ir.rule` gap-fix).
4. **Fish Staff checks**: fish batches/mortality/transfers fully usable; POS
   and Purchase apps absent; `cost_per_fish`/`profit` reads raise
   `AccessError` same as Cashier.
5. **Manager checks**: POS, Inventory, Purchase, fish management all fully
   usable; `cost_per_fish`/`profit`/`standard_price` reads **succeed** and
   return real values; Settings menu still absent; Invoicing -> Reporting ->
   OCA accounting reports menu absent (that needs
   `account.group_account_manager`, Admin-only).
6. **Admin checks**: everything above, plus Settings menu present and the OCA
   accounting reports menu present.

This exact procedure (throwaway `[TEST-ROLE] <Role> Test` users, one per
role, each with only that role's group, authenticated individually over
XML-RPC, then archived afterward) was run against the live instance while
building this module - see the orchestrating session's report for the actual
evidence captured (uids, the exact `AccessError` fault text, etc.).
