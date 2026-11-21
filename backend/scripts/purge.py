# backend/scripts/purge.py
# P7 — Wipe transcript_enc column (and optionally all visit rows).
#
# WHY this script: We promise judges "transcripts encrypted + purge after demo".
# Run after judging to honour the privacy claim in the README (D12).
#
# Usage:
#   python -m scripts.purge         → sets transcript_enc = NULL (keeps visit rows)
#   python -m scripts.purge --all   → prompts, then deletes ALL visit rows

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import sqlalchemy as sa  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import get_engine        # noqa: E402
from app.models import Visit         # noqa: E402


def purge(delete_all: bool = False) -> None:
    """Wipe transcripts (and optionally all visit rows) from Postgres."""

    if not get_settings().DATABASE_URL:
        print("ERROR: DATABASE_URL is empty. Nothing to purge.")
        sys.exit(1)

    engine = get_engine()

    if delete_all:
        # Count rows first so we can show a meaningful prompt
        with engine.connect() as conn:
            count = conn.execute(sa.select(sa.func.count()).select_from(Visit)).scalar()

        # Safety prompt — require explicit confirmation
        answer = input(f"Delete all {count} visit rows? This cannot be undone. [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted. No rows deleted.")
            return

        with engine.begin() as conn:
            result = conn.execute(sa.delete(Visit))
        print(f"Deleted {result.rowcount} visit rows.")

    else:
        # Only clear the transcript column, keep all visit metadata
        with engine.begin() as conn:
            result = conn.execute(
                sa.update(Visit).values(transcript_enc=None)
            )
        print(f"Cleared transcript_enc on {result.rowcount} visit rows. Visit rows kept.")

    print("Purge complete.")


if __name__ == "__main__":
    purge(delete_all="--all" in sys.argv)
