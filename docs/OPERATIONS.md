# Operations Guide — Aquarium Shop Odoo

This is the handover/reference doc for running and maintaining this deployment
(AQS project task 50, "Documentation package"). It covers infrastructure, day-to-day
admin, and what's still outstanding. For the fish/tank module's own data model and
feature docs, see `addons/aquarium_fish_management/README.md`.

## What this is

Odoo 17 Community Edition, self-hosted, running the shop's POS, billing, inventory,
accounting, and a custom fish/tank management module. Built for a shop in Sharjah, UAE
per the project's SRD (Software Requirements Document). Planning and task tracking live
in Plane, project **AQS** — check there for current status before assuming anything is
done; this doc describes the system as built, not a task list.

## Infrastructure

- **Host**: Mac Mini home server, managed via Dokploy (`http://192.168.0.104:3000`).
- **Live URL**: https://aquarium.ranu.win — TLS terminated at Cloudflare's edge via a
  Cloudflare Tunnel; Traefik on the Mac Mini proxies plain HTTP internally. Do not
  enable Dokploy's `https:true` domain option for this app — see the gotcha below.
- **Dokploy project**: "Aquarium Shop", two plain Applications (not Compose):
  - `aquarium-postgres` — official `postgres:16` image, persistent volume
    `aquarium-postgres-data` at `/var/lib/postgresql/data`.
  - `aquarium-odoo` — this repo, Dockerfile build, persistent volume
    `aquarium-odoo-filestore` at `/var/lib/odoo` (Odoo's filestore — product images,
    PDF attachments, etc. live here; losing this volume loses those files even though
    the database itself is intact).
- **Repo**: `github.com/Ranushka/aquarium-shop-odoo` (public). Pushing to `main`
  requires manually triggering a Dokploy deploy (`application.deploy` via the Dokploy
  API/MCP) — there is no webhook auto-deploy configured for this app (it uses a plain
  git-URL source, not a GitHub App connection).

### Gotcha: don't use Dokploy's `https:true` domain option here

This Mac Mini's Cloudflare Tunnel only ever forwards to Traefik's plain-HTTP entrypoint
(TLS is already terminated at Cloudflare's edge). If a Dokploy domain is created with
`https:true`, Dokploy adds a `redirect-to-https` Traefik middleware on that HTTP
entrypoint — which the Tunnel never escapes, producing an infinite-looking redirect
loop. Always create/update domains for this app with `https:false,
certificateType:"none"`.

## Extra Odoo modules beyond stock Community edition

Two OCA (Odoo Community Association) modules are built into the Docker image
(`Dockerfile`, sparse-checked-out into `/mnt/oca-addons` at build time, listed in
`odoo.conf.template`'s `addons_path`) to cover gaps in Community edition:

- **`auditlog`** (OCA/server-tools) — Community has no built-in audit trail. 8 rules are
  configured (Settings → Technical → Audit Logs → Rules) on `account.move`,
  `account.payment`, `pos.order`, `stock.picking`, `res.users`, `res.groups`,
  `aquarium.fish.mortality`, `purchase.order` — logging create/write/unlink in full.
- **`account_financial_report`** (OCA/account-financial-reporting) + its dependencies
  `date_range` and `report_xlsx` — Community has no P&L/Balance Sheet/General
  Ledger/Trial Balance UI (that's Enterprise's `account_reports`). Find these under
  **Invoicing → Reporting → OCA accounting reports**.

If either the Odoo base image or these OCA branches ever need bumping, re-run the
Dockerfile's `git clone --branch 17.0` steps against the OCA repos' actual latest
compatible branch — pin an exact commit if reproducibility matters more than picking up
upstream fixes automatically.

## Backups

Daily automated Postgres dump via cron on the Mac Mini itself (not a Dokploy-native
backup resource, since this Postgres is a plain Application, not a Dokploy "Postgres"
resource — Dokploy's own scheduled-backup feature doesn't apply to it):

- Script: `/home/ranu/aquarium-backup.sh` on the Mac Mini.
- Schedule: `crontab -l` → `30 3 * * *` (daily, 3:30am).
- Destination: `/etc/dokploy/volume-backups/aquarium-shop/`, gzip'd SQL dumps,
  14-day retention (older files auto-deleted by the script).
- Log: `/home/ranu/aquarium-backup.log` on the Mac Mini.

**Restore procedure:**

```bash
ssh ranu@192.168.0.104
CID=$(docker ps -qf name=aquarium-postgres-n7p9qh)
gunzip -c /etc/dokploy/volume-backups/aquarium-shop/aquarium_shop-<timestamp>.sql.gz \
  | docker exec -i "$CID" psql -U odoo postgres
```

This restores into the *existing* `postgres` database inside the container — for a
full disaster-recovery drill (new empty container), create the database fresh first via
the Odoo database-manager screen, or `dropdb`/`createdb` inside the container before
piping the dump in. **This restore procedure has not yet been tested end-to-end** (SRD
asks for a documented restore *and* a tested one before go-live) — that's a real gap,
do a test restore before this goes live for the shop.

## Admin access

- Odoo admin login: `admin@aquarium.shop` (password held in this project's memory
  entry / password manager — not written here since this file is committed to a public
  repo).
- Odoo master password (`ODOO_MASTER_PASSWORD`, needed for the database-manager screen —
  backup/restore/duplicate/delete database): set as a Dokploy environment variable on
  the `aquarium-odoo` application, not committed anywhere.
- Postgres credentials: set as Dokploy environment variables on both applications.

## What's configured vs. still placeholder

Company legal name, TRN, and the POS receipt header currently hold **placeholder
values** — set the real ones (Settings → Companies, and Point of Sale → Configuration →
Billing Counter) before this goes live for actual sales, since UAE VAT invoices legally
require the real TRN.

No real product catalog, no real staff user accounts, and no POS/fish-area hardware are
configured yet — those need the shop's actual data and physical setup, tracked as
separate Plane AQS tasks.

## Day-to-day admin quick reference

- **Add a product (accessory)**: Inventory or Point of Sale → Products.
- **Add a fish species**: Aquarium Fish → Fish Species.
- **Receive a fish batch**: create a Purchase Order for the species' product with a
  vendor; confirming it auto-creates a batch (lot) and prompts for a tank assignment —
  see `addons/aquarium_fish_management/README.md`.
- **Record fish mortality**: Aquarium Fish → Mortality — draft entries don't affect
  stock until approved.
- **Tank QR codes**: Aquarium Fish → Tanks → print the QR label report; scanning it
  opens the public `/aquarium/tank/scan/<token>` page (mobile-friendly, no login
  needed — meant for a tablet mounted at the tank).
- **Financial reports**: Invoicing → Reporting → OCA accounting reports.
- **Audit log**: Settings → Technical → Audit Logs → Logs (requires the technical
  features / developer mode setting to be enabled, or direct URL
  `/odoo/action-base_setup.action_general_configuration` → enable developer tools first).
