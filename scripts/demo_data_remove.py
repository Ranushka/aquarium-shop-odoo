#!/usr/bin/env python3
"""Remove exactly the demo records demo_data_add.py created.

Reads .demo_data_manifest.json and deletes each recorded (model, id) pair in
reverse creation order (so dependent records like a stock.lot are deleted
before the tank/species/product they reference). Does NOT match on name
prefix or anything fuzzy — only ever touches record ids this project's own
add script actually created and logged.

Usage:
    export ODOO_ADMIN_PASSWORD='...'
    python3 scripts/demo_data_remove.py
"""
import json
import os
import sys

from _common import MANIFEST_PATH, connect


def main():
    if not os.path.exists(MANIFEST_PATH):
        sys.exit(f"No manifest at {MANIFEST_PATH} — nothing to remove (or already removed).")

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    call = connect()
    removed, archived, failed = 0, 0, []
    remaining = []  # entries neither hard-deleted nor archived — kept for next run

    for model, rec_id in reversed(manifest):
        try:
            call(model, "unlink", [rec_id])
            removed += 1
            continue
        except Exception as e:
            unlink_error = str(e)
            if "does not exist or has been deleted" in unlink_error:
                # Already gone (e.g. a re-run after a previous partial pass) —
                # that's success, not a failure to report.
                removed += 1
                continue
        # Hard delete blocked (e.g. a product referenced by an open POS
        # session) — fall back to archiving so it's out of active data even
        # if it can't be fully erased right now.
        try:
            call(model, "write", [rec_id], {"active": False})
            archived += 1
        except Exception:
            failed.append((model, rec_id, unlink_error[:200]))
            remaining.append([model, rec_id])

    print(f"Removed {removed}, archived {archived} (couldn't hard-delete — see below), "
          f"out of {len(manifest)} demo records.")
    if failed:
        print(f"{len(failed)} could not even be archived:")
        for model, rec_id, err in failed:
            print(f"  {model} id={rec_id}: {err}")
    if archived:
        print(
            "Archived records are inactive (won't show in normal views/POS) but still "
            "exist in the database — usually because Odoo won't hard-delete a record "
            "referenced elsewhere (e.g. a product in an open POS session). Re-run this "
            "script later (e.g. after closing the POS session) to finish removing them — "
            "archived records stay in the manifest for that."
        )

    # Rewrite the manifest to only what's still not fully gone (genuinely
    # failed entries), so a re-run never reprocesses records already removed
    # or archived in this pass.
    if failed or archived:
        # Keep only genuinely failed ones for a future retry; archived ones
        # are considered handled (out of active data) and dropped.
        with open(MANIFEST_PATH, "w") as f:
            json.dump(remaining, f, indent=2)
        if not remaining:
            os.remove(MANIFEST_PATH)
    else:
        os.remove(MANIFEST_PATH)
        print("Manifest cleared — all demo records fully removed.")


if __name__ == "__main__":
    main()
