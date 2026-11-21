"""
test_p1_data.py
Validates all P1 data files load correctly and meet structural requirements.

Run:  cd backend && pytest tests/test_p1_data.py -v

These tests catch broken YAML/JSON before any brain code runs.
"""

import json
import yaml
import pytest
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "app" / "data"
REQUIRED_LANGS = {"en-IN", "hi-IN", "kn-IN"}

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_yaml(name: str):
    with open(DATA / name, encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_json(name: str):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)

# ── danger_signs.yaml ─────────────────────────────────────────────────────────

class TestDangerSigns:
    def setup_method(self):
        self.signs = load_yaml("danger_signs.yaml")

    def test_loads_as_list(self):
        assert isinstance(self.signs, list)

    def test_at_least_10_signs(self):
        assert len(self.signs) >= 10, f"Expected >= 10 signs, got {len(self.signs)}"

    def test_all_have_id(self):
        for s in self.signs:
            assert "id" in s and s["id"], f"Missing id: {s}"

    def test_ids_are_unique(self):
        ids = [s["id"] for s in self.signs]
        assert len(ids) == len(set(ids)), f"Duplicate sign IDs: {ids}"

    def test_all_have_source(self):
        for s in self.signs:
            assert "source" in s and s["source"], f"Missing source for {s.get('id')}"

    def test_all_have_applies_to(self):
        valid = {"MOTHER", "NEWBORN", "BOTH"}
        for s in self.signs:
            assert s.get("applies_to") in valid, f"Bad applies_to for {s.get('id')}"

    def test_all_have_labels_in_three_languages(self):
        for s in self.signs:
            labels = s.get("labels", {})
            for lang in ("en", "hi", "kn"):
                assert lang in labels and labels[lang], \
                    f"Missing {lang} label for {s.get('id')}"

    def test_all_have_keywords_in_three_languages(self):
        for s in self.signs:
            kw = s.get("keywords", {})
            for lang in ("en", "hi", "kn"):
                assert lang in kw and len(kw[lang]) >= 3, \
                    f"Need >= 3 {lang} keywords for {s.get('id')}, got {kw.get(lang)}"

    def test_mother_signs_exist(self):
        mother_ids = {s["id"] for s in self.signs if s["applies_to"] in ("MOTHER", "BOTH")}
        required = {"MO_BLEEDING", "MO_FEVER", "MO_CONVULSIONS"}
        missing = required - mother_ids
        assert not missing, f"Required mother signs missing: {missing}"

    def test_newborn_signs_exist(self):
        nb_ids = {s["id"] for s in self.signs if s["applies_to"] in ("NEWBORN", "BOTH")}
        required = {"NB_FEVER_OR_COLD", "NB_FAST_BREATHING", "NB_NOT_FEEDING"}
        missing = required - nb_ids
        assert not missing, f"Required newborn signs missing: {missing}"

# ── vaccine_schedule.json ─────────────────────────────────────────────────────

class TestVaccineSchedule:
    def setup_method(self):
        self.sched = load_json("vaccine_schedule.json")

    def test_loads_as_dict(self):
        assert isinstance(self.sched, dict)

    def test_has_child_and_mother(self):
        assert "child" in self.sched
        assert "mother" in self.sched

    def test_child_has_at_least_15_vaccines(self):
        assert len(self.sched["child"]) >= 15

    def test_mother_has_td1_td2(self):
        ids = {v["id"] for v in self.sched["mother"]}
        assert "TD1" in ids and "TD2" in ids

    def test_all_child_vaccines_have_due_weeks(self):
        for v in self.sched["child"]:
            assert "due_weeks" in v, f"Missing due_weeks for {v.get('id')}"

    def test_all_vaccines_have_spoken_labels(self):
        for v in self.sched["child"] + self.sched["mother"]:
            spoken = v.get("spoken", {})
            for lang in ("en", "hi", "kn"):
                assert lang in spoken and spoken[lang], \
                    f"Missing spoken.{lang} for {v.get('id')}"

    def test_has_source(self):
        assert "source" in self.sched and self.sched["source"]

    def test_birth_vaccines_at_week_zero(self):
        week0 = {v["id"] for v in self.sched["child"] if v.get("due_weeks") == 0}
        assert "BCG" in week0, "BCG should be due at week 0"

    def test_penta_at_6_10_14_weeks(self):
        by_week = {}
        for v in self.sched["child"]:
            w = v.get("due_weeks")
            by_week.setdefault(w, []).append(v["id"])
        assert "PENTA1" in by_week.get(6, [])
        assert "PENTA2" in by_week.get(10, [])
        assert "PENTA3" in by_week.get(14, [])

# ── templates.yaml ────────────────────────────────────────────────────────────

TIER_A_KEYS = {"disclosure", "refer_phc", "cannot_advise", "readback", "readback_changed", "saved"}
TIER_B_KEYS = {
    "ask_id", "id_not_found", "ask_visit_type", "ask_weight", "ask_vaccine_given",
    "ask_next_visit", "ask_missing", "confirm_weight_change", "confirm_vaccine_mismatch",
    "confirm_sign_absent", "ask_prev_flag", "not_understood", "goodbye", "ack",
    "who_are_you", "what_can_you_do", "how_to_use", "off_topic",
    "switch_language_ok", "slower_ok", "repeat_nothing", "system_error",
}
LABEL_KEYS = {"field_labels", "visit_type_labels", "language_labels"}

class TestTemplates:
    def setup_method(self):
        self.t = load_yaml("templates.yaml")

    def test_loads_as_dict(self):
        assert isinstance(self.t, dict)

    def test_all_tier_a_keys_present(self):
        missing = TIER_A_KEYS - set(self.t.keys())
        assert not missing, f"Missing Tier A keys: {missing}"

    def test_all_tier_b_keys_present(self):
        missing = TIER_B_KEYS - set(self.t.keys())
        assert not missing, f"Missing Tier B keys: {missing}"

    def test_label_keys_present(self):
        missing = LABEL_KEYS - set(self.t.keys())
        assert not missing, f"Missing label keys: {missing}"

    def test_tier_a_keys_have_tier_A(self):
        for key in TIER_A_KEYS:
            assert self.t[key].get("tier") == "A", f"{key} should have tier: A"

    def test_tier_a_keys_are_single_strings_not_lists(self):
        # Tier A must be one string per language, never a list
        for key in TIER_A_KEYS:
            for lang in ("en-IN", "hi-IN", "kn-IN"):
                val = self.t[key].get(lang)
                assert val is not None, f"Missing {lang} in {key}"
                assert isinstance(val, str), f"{key}.{lang} must be str (Tier A), got {type(val)}"

    def test_tier_b_keys_have_tier_B(self):
        for key in TIER_B_KEYS:
            assert self.t[key].get("tier") == "B", f"{key} should have tier: B"

    def test_tier_b_keys_have_all_languages(self):
        for key in TIER_B_KEYS:
            for lang in ("en-IN", "hi-IN", "kn-IN"):
                val = self.t[key].get(lang)
                assert val is not None, f"Missing {lang} in Tier B key {key}"

    def test_tier_b_variants_are_lists(self):
        for key in TIER_B_KEYS:
            for lang in ("en-IN", "hi-IN", "kn-IN"):
                val = self.t[key].get(lang)
                if val is not None:
                    assert isinstance(val, list), \
                        f"{key}.{lang} should be a list (1-3 variants), got {type(val)}"
                    assert 1 <= len(val) <= 3, \
                        f"{key}.{lang} should have 1-3 variants, got {len(val)}"

    def test_field_labels_has_required_fields(self):
        fl = self.t["field_labels"]
        required = {"weight_kg", "next_visit_date", "vaccines_given_today", "beneficiary_id", "visit_type"}
        missing = required - set(fl.keys())
        assert not missing, f"Missing field_labels entries: {missing}"

    def test_visit_type_labels_has_all_types(self):
        vt = self.t["visit_type_labels"]
        required = {"ANC", "PNC", "NEWBORN", "IMMUNISATION", "OTHER"}
        missing = required - set(vt.keys())
        assert not missing, f"Missing visit_type_labels entries: {missing}"

    def test_all_entries_have_verified_flag(self):
        skip = LABEL_KEYS  # label mappings don't need verified flag
        for key, val in self.t.items():
            if key not in skip:
                assert "verified" in val, f"Missing verified flag in {key}"

# ── number_words.yaml ─────────────────────────────────────────────────────────

class TestNumberWords:
    def setup_method(self):
        self.nw = load_yaml("number_words.yaml")

    def test_loads_as_dict(self):
        assert isinstance(self.nw, dict)

    def test_has_hi_and_kn(self):
        assert "hi" in self.nw and "kn" in self.nw

    def test_hi_has_digits_0_to_9(self):
        digits = self.nw["hi"]["digits"]
        for i in range(10):
            assert i in digits and digits[i], f"Missing Hindi digit {i}"

    def test_kn_has_digits_0_to_9(self):
        digits = self.nw["kn"]["digits"]
        for i in range(10):
            assert i in digits and digits[i], f"Missing Kannada digit {i}"

    def test_hi_has_numbers_0_to_99(self):
        nums = self.nw["hi"]["numbers"]
        for i in range(100):
            assert i in nums and nums[i], f"Missing Hindi number {i}"

    def test_kn_has_numbers_0_to_99(self):
        nums = self.nw["kn"]["numbers"]
        for i in range(100):
            assert i in nums and nums[i], f"Missing Kannada number {i}"

    def test_hi_has_hundreds(self):
        h = self.nw["hi"]["hundreds"]
        for v in (100, 200, 300, 400, 500, 600, 700, 800, 900):
            assert v in h and h[v], f"Missing Hindi hundred {v}"

    def test_kn_has_hundreds(self):
        h = self.nw["kn"]["hundreds"]
        for v in (100, 200, 300, 400, 500, 600, 700, 800, 900):
            assert v in h and h[v], f"Missing Kannada hundred {v}"

    def test_hi_has_12_months(self):
        m = self.nw["hi"]["months"]
        assert len(m) == 12

    def test_kn_has_12_months(self):
        m = self.nw["kn"]["months"]
        assert len(m) == 12

    def test_hi_has_weight_units(self):
        wu = self.nw["hi"]["weight_units"]
        assert "kilo" in wu and "gram" in wu

    def test_kn_has_weight_units(self):
        wu = self.nw["kn"]["weight_units"]
        assert "kilo" in wu and "gram" in wu

    def test_has_style_field(self):
        for lang in ("hi", "kn"):
            assert "style" in self.nw[lang], f"Missing style field for {lang}"
            assert self.nw[lang]["style"] in ("native", "english", "digits"), \
                f"Invalid style for {lang}"

# ── synthetic_beneficiaries.json ──────────────────────────────────────────────

class TestSyntheticBeneficiaries:
    def setup_method(self):
        path = DATA / "synthetic_beneficiaries.json"
        if not path.exists():
            pytest.skip("synthetic_beneficiaries.json not generated yet — run scripts/make_synthetic.py")
        self.b = load_json("synthetic_beneficiaries.json")

    def test_loads_as_list(self):
        assert isinstance(self.b, list)

    def test_has_12_entries(self):
        assert len(self.b) == 12

    def test_ids_1001_to_1012(self):
        ids = {b["id"] for b in self.b}
        expected = {str(i) for i in range(1001, 1013)}
        assert ids == expected

    def test_has_8_children_4_mothers(self):
        children = [b for b in self.b if b["kind"] == "child"]
        mothers  = [b for b in self.b if b["kind"] == "mother"]
        assert len(children) == 8, f"Expected 8 children, got {len(children)}"
        assert len(mothers) == 4, f"Expected 4 mothers, got {len(mothers)}"

    def test_at_least_2_with_previous_flags(self):
        flagged = [b for b in self.b if b.get("last_flags")]
        assert len(flagged) >= 2, f"Expected >= 2 with flags, got {len(flagged)}"

    def test_at_least_2_with_last_weight(self):
        with_weight = [b for b in self.b if b.get("last_weight_kg")]
        assert len(with_weight) >= 2

    def test_all_have_required_fields(self):
        required = {"id", "name", "kind", "vaccines_given", "last_flags"}
        for b in self.b:
            missing = required - set(b.keys())
            assert not missing, f"ID {b.get('id')} missing fields: {missing}"
