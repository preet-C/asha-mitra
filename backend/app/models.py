# backend/app/models.py
# P7 — SQLAlchemy ORM table definitions.
#
# WHY this file: SQLAlchemy reads these Python classes to know what columns
# and types each table has. We only use dialect-neutral column types
# (String, Float, Boolean, JSON, Text) so the same models work with
# in-memory SQLite in tests AND with Postgres in production.
#
# Tables:
#   beneficiaries — one row per registered patient (child or mother)
#   visits        — one row per completed home visit; transcript stored encrypted

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """All ORM models inherit from this.
    SQLAlchemy uses it to track tables via metadata.
    """
    pass


class Beneficiary(Base):
    """One registered patient — child or mother.

    Loaded at startup from synthetic_beneficiaries.json via seed.py.
    Updated by pg_repo.save_visit() when new weight / vaccines / flags arrive.
    """
    __tablename__ = "beneficiaries"

    # 4-digit string ID like "1001"
    id: Mapped[str] = mapped_column(sa.String(10), primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(200))

    # "child" or "mother"
    kind: Mapped[str] = mapped_column(sa.String(10))

    # Date of birth for children (ISO string "2026-10-01"); NULL for mothers
    dob: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)

    # Expected delivery date for ANC mothers; NULL for children / PNC
    edd: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)

    village: Mapped[str] = mapped_column(sa.String(200), default="")

    # Latest recorded weight in kg; NULL if never weighed
    last_weight_kg: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    # JSON list of {"id": "BCG", "date": "2026-10-08"} objects.
    # WHY JSON: flexible, matches the synthetic_beneficiaries.json shape exactly.
    vaccines_given: Mapped[list] = mapped_column(sa.JSON, default=list)

    # JSON list of danger sign IDs from the most recent visit, e.g. ["NB_FEVER_OR_COLD"].
    # Empty list means no flags on last visit (not "no flags ever").
    last_flags: Mapped[list] = mapped_column(sa.JSON, default=list)


class Visit(Base):
    """One completed home visit record.

    Created by pg_repo.save_visit(). Transcript stored encrypted (never raw).
    transcript_enc is set to NULL by scripts/purge.py after demo.
    """
    __tablename__ = "visits"

    # UUID string "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    # WHY String not Postgres UUID: SQLite in tests has no native UUID type.
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)

    # Links to beneficiaries.id. No FK constraint so SQLite tests don't need it.
    # Indexed for fast followup queries by beneficiary.
    beneficiary_id: Mapped[str] = mapped_column(sa.String(10), index=True)

    # ISO date string "2026-11-21"
    visit_date: Mapped[str] = mapped_column(sa.String(10))

    # ANC / PNC / NEWBORN / IMMUNISATION / OTHER; NULL if not set
    visit_type: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)

    weight_kg: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    # JSON lists of vaccine ID strings
    vaccines_given_today: Mapped[list] = mapped_column(sa.JSON, default=list)
    vaccines_due: Mapped[list] = mapped_column(sa.JSON, default=list)

    # ISO date for the next scheduled visit; NULL if not set by worker
    next_visit_date: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)

    # JSON list of danger sign IDs, e.g. ["NB_FEVER_OR_COLD"]
    danger_flags: Mapped[list] = mapped_column(sa.JSON, default=list)

    # True if any danger sign was detected in this visit
    flagged: Mapped[bool] = mapped_column(sa.Boolean, default=False)

    # Fernet-encrypted transcript stored as a base64 ASCII string.
    # NULL after scripts/purge.py wipes it, or if no transcript was captured.
    transcript_enc: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # Server-side timestamp. sa.func.now() works in both SQLite and Postgres.
    created_at: Mapped[str] = mapped_column(
        sa.String(30),
        server_default=sa.func.now(),
    )
