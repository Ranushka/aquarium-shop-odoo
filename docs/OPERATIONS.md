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
  Cloudflare Tunnel; Traefik on the Mac Mini proxies plain HTTP internally.
- **Dokploy project**: "Aquarium Shop", **one Compose resource** (`aquarium-shop`,
  `composeId 18hpNUA_R9crirz7tObD3`, internal Dokploy `appName`
  `compose-hack-haptic-interface-i75xzh` — this random-looking suffix is just Dokploy's
  auto-generated slug, not something meaningful to preserve) — same pattern as
  gms/getitdone/plane on this server: `docker-compose.yml` at the repo root defines two
  services with Traefik routing labels directly on the `odoo` service, deployed as
  plain `docker compose` containers (not Docker Swarm services, unlike a Dokploy plain
  "Application" — check container names via `docker ps` if debugging: they'll be
  `compose-hack-haptic-interface-i75xzh-odoo-1` / `...-postgres-1`, not the swarm-style
  `<appName>.1.<hash>` pattern).
  - `postgres` service — official `postgres:16` image, persistent volume
    `aquarium-postgres-data` at `/var/lib/postgresql/data`.
  - `odoo` service — this repo, Dockerfile build, persistent volume
    `aquarium-odoo-filestore` at `/var/lib/odoo` (Odoo's filestore — product images,
    PDF attachments, etc. live here; losing this volume loses those files even though
    the database itself is intact). Both volumes are declared `external: true` in
    `docker-compose.yml` with the exact same names — this deployment migrated from two
    plain Dokploy Applications on 2026-09-02, reusing the same Docker volumes rather
    than starting fresh, so the volume names predate the compose file and don't follow
    Compose's usual `<project>_<name>` auto-naming.
- **Repo**: `github.com/Ranushka/aquarium-shop-odoo` (public). Pushing to `main`
  requires manually triggering a Dokploy deploy (`compose.deploy` via the Dokploy
  API/MCP) — there is no webhook auto-deploy configured for this app (it uses a plain
  git-URL source, not a GitHub App connection).

### Why Compose, not a plain Application

This started as two plain Dokploy "Applications" (one per container) because this
environment's Dokploy MCP tooling didn't expose Compose creation at the time. Migrated
to Compose on 2026-09-02 to match how every other app on this server (gms, getitdone,
plane) is managed — one `docker-compose.yml`, Traefik labels on the container instead of
a separate Dokploy domain resource. If Compose creation tooling is ever unavailable
again, the raw tRPC fallback is `compose.create` / `compose.update` (sets
`sourceType`/`customGitUrl`/`composePath`/`env`) / `compose.deploy` — see this project's
global CLAUDE.md.

**Gotcha carried over from the plain-Application days, now solved differently**: this
Mac Mini's Cloudflare Tunnel only ever forwards to Traefik's plain-HTTP entrypoint (TLS
is already terminated at Cloudflare's edge). A plain Dokploy Application's `https:true`
domain option adds a `redirect-to-https` Traefik middleware on that HTTP entrypoint,
which the Tunnel can never escape — an infinite-looking redirect loop. The Compose
file's Traefik labels sidestep this entirely by only ever declaring the `web`
(plain-HTTP) entrypoint, matching every other Compose app here — there's no separate
Dokploy "domain" resource for this app any more, the routing lives entirely in
`docker-compose.yml`'s labels.

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
backup resource — Dokploy's scheduled-backup feature only applies to its native
database resource types, and this Postgres is a plain Compose service):

- Script: `/home/ranu/aquarium-backup.sh` on the Mac Mini. Finds the running postgres
  container by Compose labels (`com.docker.compose.project` /
  `com.docker.compose.service=postgres`), not by a hardcoded container name — this
  survives a redeploy (new container ID) but **would need updating if the Compose
  resource is ever deleted and recreated**, since Dokploy assigns a new random
  `appName` each time (see the "Why Compose" section above).
- Schedule: `crontab -l` → `30 3 * * *` (daily, 3:30am).
- Destination: `/etc/dokploy/volume-backups/aquarium-shop/`, gzip'd SQL dumps,
  14-day retention (older files auto-deleted by the script).
- Log: `/home/ranu/aquarium-backup.log` on the Mac Mini.

**Restore procedure:**

```bash
ssh ranu@192.168.0.104
CID=$(docker ps -qf label=com.docker.compose.project=compose-hack-haptic-interface-i75xzh \
  -f label=com.docker.compose.service=postgres | head -1)
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

## Source code & access handover (AQS task 51)

Unlike a typical client-vendor handover, this system was built directly on the owner's
own infrastructure and accounts throughout, so there's no separate transfer step —
confirming what the owner already has:

- **Source code**: `github.com/Ranushka/aquarium-shop-odoo`, owned by the business
  owner's own GitHub account. No separate repo/org to transfer.
- **Production system**: runs on the owner's own Mac Mini home server, managed through
  their own Dokploy instance — not a third-party host.
- **Database**: Postgres container on the same server; admin login and master password
  documented above, held by the owner (password manager / this project's memory
  entry, not committed to the repo).
- **Odoo admin account**: `admin@aquarium.shop`, full access, created directly by/for
  the owner — no vendor-held "master" account exists separately from this.

Nothing here needs a transfer ceremony — it's confirmation the owner already has full,
unmediated access. What *would* still need doing before this is a true multi-person
handover (e.g. handing this off to hired staff or a new admin) is documented in
`docs/USER_MANUAL.md`'s role breakdown and AQS task 12 (real staff accounts).

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
