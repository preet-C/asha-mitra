# backend/app/brain/checks.py
# P3 — History cross-checks
# WHY: These catch data inconsistencies that the worker should confirm before saving.
#      They are NOT medical judgements. They are typo/mismatch catchers.
#      All return simple bool or list[str]. Caller (dialogue.py P5) decides what to say.

# ─── Weight change check ───────────────────────────────────────────────────────

# Thresholds for suspicious weight change.
# WHY these values: a child losing >30% or gaining >50% in one visit is almost
# certainly a recording error (wrong digit), not a clinical event.
# These are not medical thresholds — just plausibility guards.
_WEIGHT_DROP_RATIO = 0.70   # new/last <= 0.70 → suspicious drop
_WEIGHT_GAIN_RATIO = 1.50   # new/last >= 1.50 → suspicious gain


def check_weight(new: float | None, last: float | None, kind: str) -> bool:
    """Return True if the weight change looks like a data entry error.

    Args:
        new:  Newly recorded weight in kg.
        last: Last recorded weight in kg from beneficiary history.
        kind: "child" | "mother" (reserved for future kind-specific thresholds).

    Returns True → caller should ask "is the weight correct?" before saving.
    Returns False → weight change is plausible, no question needed.

    WHY: Never silently save a suspiciously changed weight. The worker may have
         said "do kilo" meaning 2 kg but the record shows 20 kg from last visit.

    Boundary: ratio == 0.70 exactly → True (suspicious, ask).
              ratio == 1.50 exactly → True (suspicious, ask).
    """
    if new is None or last is None:
        return False  # Can't compare — no question to ask
    if last == 0:
        return False  # No previous weight to compare against
    ratio = new / last
    return ratio <= _WEIGHT_DROP_RATIO or ratio >= _WEIGHT_GAIN_RATIO


# ─── Vaccine mismatch check ────────────────────────────────────────────────────

def check_vaccine_mismatch(
    stated_due: list[str],
    expected_due: list[str],
) -> list[str]:
    """Return vaccine IDs that differ between worker-stated and schedule-expected.

    Args:
        stated_due:   List of vaccine IDs the worker said are due today.
        expected_due: List of vaccine IDs the schedule says are due (from vaccines_due()).

    Returns: List of IDs in one list but not both.
             Empty list = no mismatch.

    WHY: If the worker says "Penta 2 is due" but schedule says "Penta 1 is due",
         something is wrong — maybe a recording error, maybe a catch-up dose.
         We don't decide; we surface it for the worker to confirm.

    Caller action: If this returns non-empty, ask worker to confirm the difference.
    """
    stated_set = set(stated_due or [])
    expected_set = set(expected_due or [])
    # Symmetric difference: in one but not the other
    mismatch = stated_set.symmetric_difference(expected_set)
    return sorted(mismatch)  # sorted for deterministic output in tests


# ─── Visit type conflict check ─────────────────────────────────────────────────

# Valid visit types per beneficiary kind.
# WHY: ANC is "Antenatal Care" — only for pregnant mothers.
#      NEWBORN, IMMUNISATION are for children. Mixing them is a data error.
_VALID_TYPES: dict[str, set[str]] = {
    "child":  {"NEWBORN", "IMMUNISATION", "OTHER"},
    "mother": {"ANC", "PNC", "OTHER"},
}


def check_visit_type(visit_type: str | None, kind: str | None) -> bool:
    """Return True if the visit type conflicts with the beneficiary kind.

    Args:
        visit_type: "ANC" | "PNC" | "NEWBORN" | "IMMUNISATION" | "OTHER" | None
        kind:       "child" | "mother" | None

    Returns True → conflict detected, caller should ask worker to confirm.
    Returns False → no conflict, or not enough info to check.

    WHY: If a child's record gets an ANC visit type, the data is wrong.
         Catch it now, before saving, with a question — not silently.
    """
    if visit_type is None or kind is None:
        return False  # Can't check — not enough info, no question needed

    valid = _VALID_TYPES.get(kind.lower(), set())
    if not valid:
        return False  # Unknown kind — can't check

    return visit_type.upper() not in valid
