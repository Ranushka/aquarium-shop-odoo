# Aquarium Shop — Odoo

Odoo Community Edition deployment for the Aquarium Shop POS, Billing, Inventory &amp; Live
Fish Management System (Sharjah, UAE). See the Plane project **AQS** for the full task
breakdown.

**Docs**: [`docs/OPERATIONS.md`](docs/OPERATIONS.md) (infra, admin access,
backup/restore, handover) · [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md) (per-role
day-to-day usage) · [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) (schema reference) ·
[`addons/aquarium_fish_management/README.md`](addons/aquarium_fish_management/README.md)
(the custom fish/tank module's own design doc).

## What's here

- `Dockerfile` — built on the official `odoo:17.0` image, adds this repo's `addons/`
  directory as extra addons and renders `odoo.conf` from a template at container start.
- `addons/` — custom Odoo modules. Phase 2 of the project plan (fish species, batch,
  tank, mortality, transfers, QR codes) will live here as one module,
  e.g. `addons/aquarium_fish_management/`.
- `odoo.conf.template` / `entrypoint.sh` — the master password (`ODOO_MASTER_PASSWORD`)
  is injected at runtime via `envsubst`, not committed to the repo.

## Runtime configuration (set as Dokploy environment variables)

Odoo's official image reads these natively for the database connection:

- `HOST` — Postgres service hostname (the separate Postgres application, addressed by
  its Dokploy internal service name)
- `PORT` — usually `5432`
- `USER` / `PASSWORD` — Postgres credentials
- `ODOO_MASTER_PASSWORD` — Odoo's database-manager master password (used by
  `odoo.conf.template`)

## Deployment

Deployed on the Mac Mini via Dokploy as a **git-sourced Application** (Dockerfile build),
alongside a separate single-container **Postgres Application** (official `postgres:16`
image) — two plain Dokploy Applications rather than a Compose stack, since this
environment's Dokploy MCP tooling doesn't currently expose Compose/database resource
creation.
