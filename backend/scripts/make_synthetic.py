"""
make_synthetic.py
Generates backend/app/data/synthetic_beneficiaries.json

WHY: We use synthetic (fake) data only. No real patient data.
     Dates are computed from TODAY so vaccine schedules are always current.

Run from repo root:
    cd backend
    python scripts/make_synthetic.py

Output: backend/app/data/synthetic_beneficiaries.json
"""

import json
import datetime
from pathlib import Path

TODAY = datetime.date.today()


def dob_weeks_ago(weeks: int) -> str:
    """Return ISO date string for a child born `weeks` ago from today."""
    return (TODAY - datetime.timedelta(weeks=weeks)).isoformat()


def dob_months_ago(months: int) -> str:
    """Return ISO date string approximately `months` ago (30 days each)."""
    return (TODAY - datetime.timedelta(days=months * 30)).isoformat()


def edd_from_now(weeks: int) -> str:
    """Return ISO estimated delivery date `weeks` from today."""
    return (TODAY + datetime.timedelta(weeks=weeks)).isoformat()


def delivery_days_ago(days: int) -> str:
    """Return ISO delivery date `days` ago (for PNC mothers)."""
    return (TODAY - datetime.timedelta(days=days)).isoformat()


beneficiaries = [
    # ── CHILDREN (IDs 1001-1008) ─────────────────────────────────────────────

    {
        # Newborn, 6 days old. BCG/OPV0/HepB given at birth. Penta1 due at 6 weeks.
        "id": "1001",
        "name": "Arjun Singh",
        "kind": "child",
        "dob": dob_weeks_ago(0),   # born this week
        "edd": None,
        "village": "Hosahalli",
        "last_weight_kg": 3.1,
        "vaccines_given": [
            {"id": "BCG",         "date": dob_weeks_ago(0)},
            {"id": "HEP_B_BIRTH", "date": dob_weeks_ago(0)},
            {"id": "OPV_ZERO",    "date": dob_weeks_ago(0)},
        ],
        "last_flags": [],
        "note": "Newborn. First HBNC visit. All birth vaccines given."
    },

    {
        # 6 weeks old. Due for Penta1, OPV1, fIPV1, RVV1, PCV1.
        "id": "1002",
        "name": "Priya Kumari",
        "kind": "child",
        "dob": dob_weeks_ago(6),
        "edd": None,
        "village": "Rampur",
        "last_weight_kg": 4.2,
        "vaccines_given": [
            {"id": "BCG",         "date": dob_weeks_ago(6)},
            {"id": "HEP_B_BIRTH", "date": dob_weeks_ago(6)},
            {"id": "OPV_ZERO",    "date": dob_weeks_ago(6)},
        ],
        "last_flags": [],
        "note": "6-week visit. Penta1, OPV1, fIPV1, RVV1, PCV1 due today."
    },

    {
        # 10 weeks old. Penta1 done. Penta2, OPV2, RVV2 due.
        "id": "1003",
        "name": "Rahul Meena",
        "kind": "child",
        "dob": dob_weeks_ago(10),
        "edd": None,
        "village": "Nandpur",
        "last_weight_kg": 5.0,
        "vaccines_given": [
            {"id": "BCG",         "date": dob_weeks_ago(10)},
            {"id": "HEP_B_BIRTH", "date": dob_weeks_ago(10)},
            {"id": "OPV_ZERO",    "date": dob_weeks_ago(10)},
            {"id": "OPV1",        "date": dob_weeks_ago(4)},
            {"id": "PENTA1",      "date": dob_weeks_ago(4)},
            {"id": "FIPV1",       "date": dob_weeks_ago(4)},
            {"id": "RVV1",        "date": dob_weeks_ago(4)},
            {"id": "PCV1",        "date": dob_weeks_ago(4)},
        ],
        "last_flags": [],
        "note": "10-week visit. Penta2, OPV2, RVV2 due."
    },

    {
        # 14 weeks old. Penta1+2 done. Penta3, OPV3, fIPV2, RVV3, PCV2 due.
        "id": "1004",
        "name": "Kavya Reddy",
        "kind": "child",
        "dob": dob_weeks_ago(14),
        "edd": None,
        "village": "Hosahalli",
        "last_weight_kg": 5.8,
        "vaccines_given": [
            {"id": "BCG",         "date": dob_weeks_ago(14)},
            {"id": "HEP_B_BIRTH", "date": dob_weeks_ago(14)},
            {"id": "OPV_ZERO",    "date": dob_weeks_ago(14)},
            {"id": "OPV1",        "date": dob_weeks_ago(8)},
            {"id": "PENTA1",      "date": dob_weeks_ago(8)},
            {"id": "FIPV1",       "date": dob_weeks_ago(8)},
            {"id": "RVV1",        "date": dob_weeks_ago(8)},
            {"id": "PCV1",        "date": dob_weeks_ago(8)},
            {"id": "OPV2",        "date": dob_weeks_ago(4)},
            {"id": "PENTA2",      "date": dob_weeks_ago(4)},
            {"id": "RVV2",        "date": dob_weeks_ago(4)},
        ],
        "last_flags": [],
        "note": "14-week visit. Penta3, OPV3, fIPV2, RVV3, PCV2 due."
    },

    {
        # 9 months old. All 6-week/10-week/14-week doses done. MR1, fIPV3, PCV-booster due.
        # Has last weight recorded.
        "id": "1005",
        "name": "Sunita Devi",
        "kind": "child",
        "dob": dob_months_ago(9),
        "edd": None,
        "village": "Hosahalli",
        "last_weight_kg": 7.5,
        "vaccines_given": [
            {"id": "BCG",         "date": dob_months_ago(9)},
            {"id": "HEP_B_BIRTH", "date": dob_months_ago(9)},
            {"id": "OPV_ZERO",    "date": dob_months_ago(9)},
            {"id": "OPV1",        "date": dob_months_ago(7)},
            {"id": "PENTA1",      "date": dob_months_ago(7)},
            {"id": "FIPV1",       "date": dob_months_ago(7)},
            {"id": "RVV1",        "date": dob_months_ago(7)},
            {"id": "PCV1",        "date": dob_months_ago(7)},
            {"id": "OPV2",        "date": dob_months_ago(6)},
            {"id": "PENTA2",      "date": dob_months_ago(6)},
            {"id": "RVV2",        "date": dob_months_ago(6)},
            {"id": "OPV3",        "date": dob_months_ago(5)},
            {"id": "PENTA3",      "date": dob_months_ago(5)},
            {"id": "FIPV2",       "date": dob_months_ago(5)},
            {"id": "RVV3",        "date": dob_months_ago(5)},
            {"id": "PCV2",        "date": dob_months_ago(5)},
        ],
        "last_flags": [],
        "note": "9-month visit. MR1, fIPV3, PCV-booster, Vitamin A due. Last weight recorded."
    },

    {
        # 15 months. All prior doses done. DPT-booster, OPV-booster, MR2 due.
        "id": "1006",
        "name": "Rajesh Kumar",
        "kind": "child",
        "dob": dob_months_ago(15),
        "edd": None,
        "village": "Rampur",
        "last_weight_kg": 9.2,
        "vaccines_given": [
            {"id": "BCG",         "date": dob_months_ago(15)},
            {"id": "HEP_B_BIRTH", "date": dob_months_ago(15)},
            {"id": "OPV_ZERO",    "date": dob_months_ago(15)},
            {"id": "OPV1",        "date": dob_months_ago(13)},
            {"id": "PENTA1",      "date": dob_months_ago(13)},
            {"id": "FIPV1",       "date": dob_months_ago(13)},
            {"id": "RVV1",        "date": dob_months_ago(13)},
            {"id": "PCV1",        "date": dob_months_ago(13)},
            {"id": "OPV2",        "date": dob_months_ago(11)},
            {"id": "PENTA2",      "date": dob_months_ago(11)},
            {"id": "RVV2",        "date": dob_months_ago(11)},
            {"id": "OPV3",        "date": dob_months_ago(9)},
            {"id": "PENTA3",      "date": dob_months_ago(9)},
            {"id": "FIPV2",       "date": dob_months_ago(9)},
            {"id": "RVV3",        "date": dob_months_ago(9)},
            {"id": "PCV2",        "date": dob_months_ago(9)},
            {"id": "MR1",         "date": dob_months_ago(6)},
            {"id": "FIPV3",       "date": dob_months_ago(6)},
            {"id": "PCV_BOOSTER", "date": dob_months_ago(6)},
            {"id": "VITA1",       "date": dob_months_ago(6)},
        ],
        "last_flags": [],
        "note": "15-month visit. DPT-booster, OPV-booster, MR2 due."
    },

    {
        # 5 months old. Had NB_FEVER_OR_COLD flag at last visit. Good weight gain.
        "id": "1007",
        "name": "Meena Bai",
        "kind": "child",
        "dob": dob_months_ago(5),
        "edd": None,
        "village": "Nandpur",
        "last_weight_kg": 5.4,
        "vaccines_given": [
            {"id": "BCG",    "date": dob_months_ago(5)},
            {"id": "OPV1",   "date": dob_months_ago(3)},
            {"id": "PENTA1", "date": dob_months_ago(3)},
            {"id": "OPV2",   "date": dob_months_ago(2)},
            {"id": "PENTA2", "date": dob_months_ago(2)},
        ],
        "last_flags": ["NB_FEVER_OR_COLD"],
        "note": "Previous danger flag: NB_FEVER_OR_COLD. ASHA should ask status."
    },

    {
        # 3 months old. Low weight for age. No previous danger flag but worker should check.
        # Has last_weight_kg for weight-change check test.
        "id": "1008",
        "name": "Deepa Rani",
        "kind": "child",
        "dob": dob_months_ago(3),
        "edd": None,
        "village": "Hosahalli",
        "last_weight_kg": 3.9,   # low — will trigger weight-change confirm if new weight given
        "vaccines_given": [
            {"id": "BCG",    "date": dob_months_ago(3)},
            {"id": "OPV1",   "date": dob_months_ago(1)},
            {"id": "PENTA1", "date": dob_months_ago(1)},
        ],
        "last_flags": [],
        "note": "Low weight for age. 3-month visit. Penta2, OPV2 due."
    },

    # ── MOTHERS (IDs 1009-1012) ───────────────────────────────────────────────

    {
        # ANC mother, 28 weeks pregnant. TD1 given, TD2 due.
        "id": "1009",
        "name": "Fatima Begum",
        "kind": "mother",
        "dob": None,
        "edd": edd_from_now(12),   # due in 12 weeks (~28 weeks pregnant)
        "village": "Rampur",
        "last_weight_kg": 58.0,
        "vaccines_given": [
            {"id": "TD1", "date": dob_months_ago(2)},
        ],
        "last_flags": [],
        "note": "ANC. 28 weeks. TD1 done. TD2 due (4+ weeks since TD1)."
    },

    {
        # PNC mother, delivered 14 days ago. No danger flags.
        "id": "1010",
        "name": "Lakshmi Devi",
        "kind": "mother",
        "dob": None,
        "edd": None,
        "delivery_date": delivery_days_ago(14),
        "village": "Hosahalli",
        "last_weight_kg": 54.0,
        "vaccines_given": [
            {"id": "TD1", "date": dob_months_ago(5)},
            {"id": "TD2", "date": dob_months_ago(4)},
        ],
        "last_flags": [],
        "note": "PNC. Delivered 14 days ago. Both TDs done. HBNC newborn visit concurrent."
    },

    {
        # ANC mother, 20 weeks pregnant. No TDs yet.
        "id": "1011",
        "name": "Anita Sharma",
        "kind": "mother",
        "dob": None,
        "edd": edd_from_now(20),
        "village": "Nandpur",
        "last_weight_kg": 51.5,
        "vaccines_given": [],
        "last_flags": [],
        "note": "ANC. 20 weeks. TD1 and TD2 both due."
    },

    {
        # PNC mother with previous MO_FEVER flag. Delivered 30 days ago.
        # For testing: ASHA should be asked about status of fever.
        "id": "1012",
        "name": "Rukmini Bai",
        "kind": "mother",
        "dob": None,
        "edd": None,
        "delivery_date": delivery_days_ago(30),
        "village": "Rampur",
        "last_weight_kg": 49.0,
        "vaccines_given": [
            {"id": "TD1", "date": dob_months_ago(4)},
            {"id": "TD2", "date": dob_months_ago(3)},
        ],
        "last_flags": ["MO_FEVER"],
        "note": "PNC. Previous danger flag: MO_FEVER. ASHA should be asked about current status."
    },
]


def main():
    out_path = Path(__file__).resolve().parents[1] / "app" / "data" / "synthetic_beneficiaries.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(beneficiaries, f, ensure_ascii=False, indent=2)
    print(f"Written {len(beneficiaries)} beneficiaries to {out_path}")
    print(f"Today: {TODAY}")
    print("IDs:", [b["id"] for b in beneficiaries])
    print("Children:", sum(1 for b in beneficiaries if b["kind"] == "child"))
    print("Mothers: ", sum(1 for b in beneficiaries if b["kind"] == "mother"))
    print("With previous flags:", [b["id"] for b in beneficiaries if b["last_flags"]])


if __name__ == "__main__":
    main()
