# backend/scripts/seed.py
# P7 — Load synthetic beneficiaries into Postgres.
#
# WHY this script: Judges need to see real names and data in the UI.
# Without seeding, the beneficiaries table is empty and the brain
# returns "ID not found" for every request.
#
# Run: python -m scripts.seed
# Safe to run multiple times — skips rows whose ID already exists.

import json
import pathlib
import sys

# Allow running as: python -m scripts.seed from backend/
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.config import get_settings   # noqa: E402
from app.db import create_tables, get_session  # noqa: E402
from app.models import Beneficiary    # noqa: E402

DATA_FILE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "app" / "data" / "synthetic_beneficiaries.json"
)


def seed() -> None:
    """Read synthetic_beneficiaries.json and insert every row into Postgres.
    Skips rows whose ID already exists (safe to re-run).
    """
    if not get_settings().DATABASE_URL:
        print("ERROR: DATABASE_URL is empty. Set it in backend/.env first.")
        sys.exit(1)

    # Create tables if they don't exist yet (safe on every run)
    print("Ensuring tables exist...")
    create_tables()

    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    print(f"Found {len(raw)} beneficiaries in {DATA_FILE.name}")

    inserted = 0
    skipped = 0

    with get_session() as session:
        for item in raw:
            # Skip if the ID already exists — don't overwrite live data
            if session.get(Beneficiary, item["id"]) is not None:
                print(f"  Skipped  {item['id']} — {item['name']} (already exists)")
                skipped += 1
                continue

            session.add(Beneficiary(
                id=item["id"],
                name=item["name"],
                kind=item["kind"],
                dob=item.get("dob"),
                edd=item.get("edd"),
                village=item.get("village", ""),
                last_weight_kg=item.get("last_weight_kg"),
                vaccines_given=item.get("vaccines_given", []),
                last_flags=item.get("last_flags", []),
            ))
            print(f"  Inserted {item['id']} — {item['name']}")
            inserted += 1

    print(f"\nSeeded {inserted} beneficiaries. ({skipped} skipped — already existed.)")


if __name__ == "__main__":
    seed()
