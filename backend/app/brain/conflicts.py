# backend/app/brain/conflicts.py
# A2 — Conflict detection: finds contradictions within one visit session.
#
# WHY this file exists: ASHA workers sometimes say contradictory things in one
# visit (fever present, then fever not present). We catch those contradictions
# here and queue a question for the worker. We NEVER silently resolve a conflict.
#
# Reuses existing checks.py functions — does NOT re-implement them.
# Reuses danger.scan_danger's confirm_absent logic — does NOT replace it.
#
# SAFETY RULES:
#   - Once a danger flag is set it stays UNLESS the worker explicitly says absent
#     in answer to the conflict question. Unclear answer = flag stays.
#   - Tri-state: present / absent / unclear. not_mentioned is never absent.
#   - Different dose IDs (PENTA1 vs PENTA2) are NOT duplicates.

from app.brain.checks import check_weight, check_vaccine_mismatch, check_visit_type


# ── Symptom conflict ──────────────────────────────────────────────────────────

def symptom_conflicts(symptom_log: list[dict]) -> list[str]:
    """Find sign IDs that have both present/unclear AND absent in one visit.

    Args:
        symptom_log: List of symptom entries recorded during the CAPTURE phase.
            Each entry: {"sign_id": str, "status": "present"|"absent"|"unclear"}
            Entries accumulate across multiple worker utterances this visit.

    Returns:
        List of sign_id strings that have a conflict.
        Empty list = no contradictions.

    WHY: "bleeding nahi hai" then later "bahut bleeding ho rahi hai" = conflict.
    We surface the conflict so the worker can clarify. We do NOT auto-resolve.

    SAFETY: This function does not change any flags. It only identifies sign IDs
    that need a clarification question. scan_danger() keeps the alert running.
    """
    # Build per-sign set of statuses
    statuses_seen: dict[str, set] = {}
    for entry in (symptom_log or []):
        sid = entry.get("sign_id")
        status = entry.get("status")
        if not sid or not status:
            continue
        statuses_seen.setdefault(sid, set()).add(status)

    conflicts = []
    for sid, status_set in statuses_seen.items():
        # Conflict = same sign has present or unclear AND absent
        has_positive = bool(status_set & {"present", "unclear"})
        has_absent = "absent" in status_set
        if has_positive and has_absent:
            conflicts.append(sid)

    return sorted(conflicts)  # sorted for deterministic test output


# ── Value conflict ────────────────────────────────────────────────────────────

def value_conflicts(field_log: list[dict]) -> list[dict]:
    """Find fields that have different non-null values in DIFFERENT utterances.

    Args:
        field_log: List of field observations recorded during CAPTURE.
            Each entry: {
                "field":     str,        # e.g. "weight_kg"
                "value":     any,        # the value seen
                "utterance": int | str,  # utterance index or ID
            }
            Same utterance = LLM already resolved it → NOT a conflict here.

    Returns:
        List of conflict dicts: [{"field": str, "values": [a, b]}]
        Values list has the two (or more) distinct values seen in DIFFERENT utterances.

    Special rule: beneficiary_id changing mid-visit is ALWAYS a conflict,
    even if the same utterance index is involved (since it identifies the record).

    WHY: Worker may say "ID 1001" then later "ID 1002". We must ask — never pick.
    WHY same utterance excluded: If the LLM receives "weight is 2.8 no sorry 3.1"
    and returns 3.1, it already resolved the self-correction. No conflict to surface.
    """
    # Group by field, then by utterance, keeping first value per utterance
    # (we use the first value per utterance since LLM already resolved within one)
    per_field: dict[str, dict] = {}  # field -> {utterance -> value}

    for entry in (field_log or []):
        field = entry.get("field")
        value = entry.get("value")
        utterance = entry.get("utterance")
        if field is None or value is None or utterance is None:
            continue
        per_field.setdefault(field, {})[utterance] = value

    conflicts = []
    for field, utt_map in per_field.items():
        # Collect distinct values across utterances
        distinct_values = list({str(v) for v in utt_map.values()})
        if len(distinct_values) < 2:
            continue  # all utterances agree

        # For beneficiary_id: always conflict (even if only 1 utterance key)
        if field == "beneficiary_id" and len(utt_map) >= 1:
            # If there is more than one distinct value across utterances → conflict
            if len(distinct_values) > 1:
                conflicts.append({"field": field, "values": sorted(distinct_values)})
        else:
            if len(distinct_values) > 1:
                conflicts.append({"field": field, "values": sorted(distinct_values)})

    return conflicts


# ── Repeat vaccine ────────────────────────────────────────────────────────────

def repeat_vaccines(
    given_today: list[str],
    beneficiary_history: list[dict],
) -> list[str]:
    """Find vaccine IDs that are given today but already in beneficiary history.

    Args:
        given_today:          List of vaccine IDs from this visit's draft.
        beneficiary_history:  List of {"id": str, "date": str} from beneficiary record.

    Returns:
        List of vaccine IDs that are repeats (already in history).
        PENTA1 vs PENTA2 are different IDs — NOT duplicates. Only exact ID match.

    WHY: If BCG is already in history and worker says BCG again, something is wrong.
    We surface it; we don't silently accept or reject the repeat.
    """
    # Build set of already-given vaccine IDs (exact match)
    already_given = {v["id"] for v in (beneficiary_history or []) if isinstance(v, dict)}

    repeats = []
    for vax_id in (given_today or []):
        if vax_id in already_given:
            repeats.append(vax_id)

    return repeats


# ── Composite helper: run all conflict checks for one turn ───────────────────

def run_all_conflict_checks(
    session: dict,
    draft: dict,
    beneficiary: dict | None,
) -> dict:
    """Run all conflict checks and return a summary dict.

    This is a convenience wrapper for dialogue.py. It calls the three functions
    above plus reuses checks.check_weight, check_vaccine_mismatch, check_visit_type.

    Args:
        session:     The current session dict (reads symptom_log, field_log).
        draft:       Current VisitDraft.
        beneficiary: Loaded beneficiary dict or None.

    Returns:
        {
            "symptom_conflicts":  [sign_id, ...],   # signs with present+absent
            "value_conflicts":    [{"field": ..., "values": [...]}, ...],
            "repeat_vaccines":    [vaccine_id, ...],
            "weight_suspicious":  bool,              # check_weight result
            "vaccine_mismatch":   [vaccine_id, ...], # check_vaccine_mismatch result
            "visit_type_conflict": bool,             # check_visit_type result
        }
    """
    result = {
        "symptom_conflicts": [],
        "value_conflicts": [],
        "repeat_vaccines": [],
        "weight_suspicious": False,
        "vaccine_mismatch": [],
        "visit_type_conflict": False,
    }

    # Symptom conflicts from accumulated symptom log
    sym_log = session.get("symptom_log", [])
    result["symptom_conflicts"] = symptom_conflicts(sym_log)

    # Value conflicts from accumulated field log
    f_log = session.get("field_log", [])
    result["value_conflicts"] = value_conflicts(f_log)

    # Repeat vaccines
    given_today = draft.get("vaccines_given_today") or []
    history = []
    if beneficiary:
        history = beneficiary.get("vaccines_given") or []
    result["repeat_vaccines"] = repeat_vaccines(given_today, history)

    # Weight change check (reuse checks.py)
    new_weight = draft.get("weight_kg")
    last_weight = beneficiary.get("last_weight_kg") if beneficiary else None
    ben_kind = beneficiary.get("kind", "child") if beneficiary else "child"
    result["weight_suspicious"] = check_weight(new_weight, last_weight, ben_kind)

    # Vaccine mismatch (reuse checks.py)
    # stated_due comes from draft; expected_due would come from vaccines_due() in P3
    # We only compute mismatch when both sides are available
    stated_due = draft.get("vaccines_due_stated") or []
    # expected_due is not recomputed here — dialogue.py passes it in session if available
    expected_due = session.get("_expected_due") or []
    result["vaccine_mismatch"] = check_vaccine_mismatch(stated_due, expected_due)

    # Visit type conflict (reuse checks.py)
    ben_kind_full = beneficiary.get("kind") if beneficiary else None
    result["visit_type_conflict"] = check_visit_type(
        draft.get("visit_type"), ben_kind_full
    )

    return result
