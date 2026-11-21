# backend/tests/test_normalize.py
# P2 — Tests for normalize.py
# WHY: Every normaliser function must be tested before the LLM or dialogue layer
#      uses it. These run with no network, no LLM, no external service.
# Run: cd backend && pytest tests/test_normalize.py -v

import pytest
from datetime import date

from app.brain.normalize import (
    parse_beneficiary_id,
    validate_weight_kg,
    parse_weight_fallback,
    resolve_next_visit,
    number_to_words_en,
    digits_to_words,
    date_to_words,
    weight_to_words,
    render_number,
    parse_spoken_number,
)

# ─── Minimal fixture table that mirrors number_words.yaml structure ────────────
# WHY: Tests must NOT depend on the real YAML path or content changing.

MOCK_TABLES = {
    "hi": {
        "style": "native",
        "digits": {
            0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार",
            5: "पाँच", 6: "छह", 7: "सात", 8: "आठ", 9: "नौ",
        },
        "numbers": {
            0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार",
            5: "पाँच", 6: "छह", 7: "सात", 8: "आठ", 9: "नौ",
            10: "दस", 11: "ग्यारह", 15: "पंद्रह", 20: "बीस",
            28: "अट्ठाईस", 31: "इकतीस", 58: "अट्ठावन",
        },
        "hundreds": {
            100: "एक सौ", 200: "दो सौ", 300: "तीन सौ", 400: "चार सौ",
            500: "पाँच सौ", 600: "छह सौ", 700: "सात सौ", 800: "आठ सौ", 900: "नौ सौ",
        },
        "weight_units": {"kilo": "किलो", "gram": "ग्राम"},
        "months": {
            1: "जनवरी", 2: "फ़रवरी", 3: "मार्च", 4: "अप्रैल",
            5: "मई", 6: "जून", 7: "जुलाई", 8: "अगस्त",
            9: "सितंबर", 10: "अक्टूबर", 11: "नवंबर", 12: "दिसंबर",
        },
    },
    "kn": {
        "style": "native",
        "digits": {
            0: "ಶೂನ್ಯ", 1: "ಒಂದು", 2: "ಎರಡು", 3: "ಮೂರು", 4: "ನಾಲ್ಕು",
            5: "ಐದು", 6: "ಆರು", 7: "ಏಳು", 8: "ಎಂಟು", 9: "ಒಂಬತ್ತು",
        },
        "numbers": {
            0: "ಶೂನ್ಯ", 1: "ಒಂದು", 2: "ಎರಡು", 3: "ಮೂರು", 4: "ನಾಲ್ಕು",
            5: "ಐದು", 6: "ಆರು", 7: "ಏಳು", 8: "ಎಂಟು", 9: "ಒಂಬತ್ತು",
            10: "ಹತ್ತು", 15: "ಹದಿನೈದು", 20: "ಇಪ್ಪತ್ತು",
            28: "ಇಪ್ಪತ್ತೆಂಟು", 31: "ಮೂವತ್ತೊಂದು",
        },
        "hundreds": {
            100: "ನೂರು", 200: "ಎರಡು ನೂರು", 300: "ಮೂರು ನೂರು",
            400: "ನಾಲ್ಕು ನೂರು", 500: "ಐದು ನೂರು", 600: "ಆರು ನೂರು",
            700: "ಏಳು ನೂರು", 800: "ಎಂಟು ನೂರು", 900: "ಒಂಬತ್ತು ನೂರು",
        },
        "weight_units": {"kilo": "ಕೆಜಿ", "gram": "ಗ್ರಾಂ"},
        "months": {
            1: "ಜನವರಿ", 2: "ಫೆಬ್ರವರಿ", 3: "ಮಾರ್ಚ್", 4: "ಏಪ್ರಿಲ್",
            5: "ಮೇ", 6: "ಜೂನ್", 7: "ಜುಲೈ", 8: "ಆಗಸ್ಟ್",
            9: "ಸೆಪ್ಟೆಂಬರ್", 10: "ಅಕ್ಟೋಬರ್", 11: "ನವೆಂಬರ್", 12: "ಡಿಸೆಂಬರ್",
        },
    },
    "en": {
        "style": "english",
        "weight_units": {"kilo": "kilo", "gram": "gram"},
        "months": {
            1: "January", 2: "February", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December",
        },
    },
}


@pytest.fixture(autouse=True)
def mock_tables(monkeypatch):
    """Patch _load_tables so all tests use the fixture table, not the real YAML."""
    import app.brain.normalize as norm
    monkeypatch.setattr(norm, "_load_tables", lambda: MOCK_TABLES)


# ════════════════════════════════════════════════════════════════════════════════
# parse_beneficiary_id
# ════════════════════════════════════════════════════════════════════════════════

class TestParseBeneficiaryId:
    def test_plain_4_digits(self):
        assert parse_beneficiary_id("1042") == "1042"

    def test_digits_with_spaces(self):
        assert parse_beneficiary_id("1 0 4 2") == "1042"

    def test_english_words(self):
        assert parse_beneficiary_id("one zero four two") == "1042"

    def test_hindi_romanised(self):
        assert parse_beneficiary_id("ek zero chaar do") == "1042"

    def test_hindi_mixed_roman_digit(self):
        assert parse_beneficiary_id("ek 0 4 do") == "1042"

    def test_leading_zeros(self):
        assert parse_beneficiary_id("0001") == "0001"

    def test_too_short_returns_none(self):
        assert parse_beneficiary_id("123") is None

    def test_too_long_returns_none(self):
        assert parse_beneficiary_id("12345") is None

    def test_empty_string_returns_none(self):
        assert parse_beneficiary_id("") is None

    def test_none_input_returns_none(self):
        assert parse_beneficiary_id(None) is None  # type: ignore

    def test_alpha_input_returns_none(self):
        assert parse_beneficiary_id("abcd") is None

    def test_partial_words_returns_none(self):
        assert parse_beneficiary_id("one two three") is None


# ════════════════════════════════════════════════════════════════════════════════
# validate_weight_kg
# ════════════════════════════════════════════════════════════════════════════════

class TestValidateWeightKg:
    def test_child_valid_low(self):
        assert validate_weight_kg(1.0, "child") == 1.0

    def test_child_valid_high(self):
        assert validate_weight_kg(25.0, "child") == 25.0

    def test_child_valid_typical(self):
        assert validate_weight_kg(2.8, "child") == 2.8

    def test_child_too_low(self):
        assert validate_weight_kg(0.9, "child") is None

    def test_child_too_high(self):
        assert validate_weight_kg(26.0, "child") is None

    def test_mother_valid(self):
        assert validate_weight_kg(58.0, "mother") == 58.0

    def test_mother_too_low(self):
        assert validate_weight_kg(29.9, "mother") is None

    def test_mother_too_high(self):
        assert validate_weight_kg(121.0, "mother") is None

    def test_rounds_to_1_decimal(self):
        assert validate_weight_kg(2.85, "child") == 2.9

    def test_unknown_kind_returns_none(self):
        assert validate_weight_kg(10.0, "alien") is None

    def test_none_value_returns_none(self):
        assert validate_weight_kg(None, "child") is None  # type: ignore

    def test_negative_returns_none(self):
        assert validate_weight_kg(-1.0, "child") is None


# ════════════════════════════════════════════════════════════════════════════════
# parse_weight_fallback
# ════════════════════════════════════════════════════════════════════════════════

class TestParseWeightFallback:
    def test_plain_decimal(self):
        assert parse_weight_fallback("2.8") == 2.8

    def test_decimal_with_kg(self):
        assert parse_weight_fallback("2.8 kg") == 2.8

    def test_grams_large(self):
        assert parse_weight_fallback("2800 gram") == 2.8

    def test_grams_small(self):
        assert parse_weight_fallback("800 gram") == 0.8

    def test_kilo_and_gram(self):
        assert parse_weight_fallback("2 kilo 800 gram") == 2.8

    def test_kilo_only(self):
        assert parse_weight_fallback("3 kilo") == 3.0

    def test_empty_returns_none(self):
        assert parse_weight_fallback("") is None

    def test_none_input_returns_none(self):
        assert parse_weight_fallback(None) is None  # type: ignore

    def test_gibberish_returns_none(self):
        assert parse_weight_fallback("hello world") is None

    def test_kilograms_plural(self):
        assert parse_weight_fallback("3 kilograms") == 3.0


# ════════════════════════════════════════════════════════════════════════════════
# resolve_next_visit
# ════════════════════════════════════════════════════════════════════════════════

TODAY = date(2026, 11, 21)  # Saturday (weekday=5)


class TestResolveNextVisit:
    def test_relative_days(self):
        assert resolve_next_visit({"kind": "relative_days", "n": 15}, TODAY) == date(2026, 12, 6)

    def test_relative_1_day(self):
        assert resolve_next_visit({"kind": "relative_days", "n": 1}, TODAY) == date(2026, 11, 22)

    def test_relative_zero_returns_none(self):
        assert resolve_next_visit({"kind": "relative_days", "n": 0}, TODAY) is None

    def test_relative_negative_returns_none(self):
        assert resolve_next_visit({"kind": "relative_days", "n": -5}, TODAY) is None

    def test_absolute_future(self):
        assert resolve_next_visit({"kind": "absolute", "day": 15, "month": 12, "year": None}, TODAY) == date(2026, 12, 15)

    def test_absolute_past_flips_to_next_year(self):
        # Nov 1 is in the past relative to Nov 21
        assert resolve_next_visit({"kind": "absolute", "day": 1, "month": 11, "year": None}, TODAY) == date(2027, 11, 1)

    def test_absolute_with_explicit_year(self):
        assert resolve_next_visit({"kind": "absolute", "day": 5, "month": 12, "year": 2026}, TODAY) == date(2026, 12, 5)

    def test_absolute_explicit_past_year_returns_none(self):
        assert resolve_next_visit({"kind": "absolute", "day": 1, "month": 1, "year": 2025}, TODAY) is None

    def test_absolute_invalid_date_returns_none(self):
        assert resolve_next_visit({"kind": "absolute", "day": 30, "month": 2, "year": None}, TODAY) is None

    def test_weekday_next_monday(self):
        # TODAY is Saturday (5). Monday = 0. Next Monday is in 2 days.
        assert resolve_next_visit({"kind": "weekday", "weekday": 0, "which": "next"}, TODAY) == date(2026, 11, 23)

    def test_weekday_next_friday(self):
        # TODAY is Saturday (5). Friday = 4. Next Friday is in 6 days.
        assert resolve_next_visit({"kind": "weekday", "weekday": 4, "which": "next"}, TODAY) == date(2026, 11, 27)

    def test_weekday_same_day_goes_to_next_week(self):
        # TODAY is Saturday (5). "this Saturday" should go to next Saturday.
        assert resolve_next_visit({"kind": "weekday", "weekday": 5, "which": "this"}, TODAY) == date(2026, 11, 28)

    def test_weekday_invalid_weekday_returns_none(self):
        assert resolve_next_visit({"kind": "weekday", "weekday": 7, "which": "next"}, TODAY) is None

    def test_none_spec_returns_none(self):
        assert resolve_next_visit(None, TODAY) is None  # type: ignore

    def test_unknown_kind_returns_none(self):
        assert resolve_next_visit({"kind": "unknown"}, TODAY) is None


# ════════════════════════════════════════════════════════════════════════════════
# number_to_words_en
# ════════════════════════════════════════════════════════════════════════════════

class TestNumberToWordsEn:
    def test_integer(self):
        assert number_to_words_en(2.0) == "two"

    def test_decimal_contains_two_and_eight(self):
        result = number_to_words_en(2.8)
        assert "two" in result
        assert "eight" in result

    def test_zero(self):
        assert "zero" in number_to_words_en(0.0)


# ════════════════════════════════════════════════════════════════════════════════
# digits_to_words
# ════════════════════════════════════════════════════════════════════════════════

class TestDigitsToWords:
    def test_hindi_id(self):
        result = digits_to_words("1042", "hi-IN")
        assert "एक" in result
        assert "शून्य" in result
        assert "चार" in result
        assert "दो" in result

    def test_kannada_id(self):
        result = digits_to_words("1042", "kn-IN")
        assert "ಒಂದು" in result
        assert "ಶೂನ್ಯ" in result
        assert "ನಾಲ್ಕು" in result
        assert "ಎರಡು" in result

    def test_english_id(self):
        assert digits_to_words("1042", "en-IN") == "one zero four two"

    def test_non_digit_passthrough(self):
        assert digits_to_words("abc", "en-IN") == "abc"

    def test_single_digit(self):
        assert digits_to_words("5", "en-IN") == "five"


# ════════════════════════════════════════════════════════════════════════════════
# date_to_words
# ════════════════════════════════════════════════════════════════════════════════

class TestDateToWords:
    def test_hindi_date(self):
        result = date_to_words(date(2026, 12, 15), "hi-IN")
        assert "पंद्रह" in result
        assert "दिसंबर" in result

    def test_kannada_date(self):
        result = date_to_words(date(2026, 12, 15), "kn-IN")
        assert "ಹದಿನೈದು" in result
        assert "ಡಿಸೆಂಬರ್" in result

    def test_english_date(self):
        result = date_to_words(date(2026, 12, 15), "en-IN")
        assert "fifteen" in result.lower()
        assert "December" in result

    def test_hindi_first_of_month(self):
        result = date_to_words(date(2026, 11, 1), "hi-IN")
        assert "एक" in result
        assert "नवंबर" in result


# ════════════════════════════════════════════════════════════════════════════════
# weight_to_words
# ════════════════════════════════════════════════════════════════════════════════

class TestWeightToWords:
    def test_hindi_2_8_has_kilo_gram_no_point(self):
        result = weight_to_words(2.8, "hi-IN")
        assert "दो" in result
        assert "किलो" in result
        assert "आठ सौ" in result
        assert "ग्राम" in result
        assert "point" not in result.lower()  # D6: never "point"

    def test_kannada_2_8(self):
        result = weight_to_words(2.8, "kn-IN")
        assert "ಎರಡು" in result
        assert "ಕೆಜಿ" in result
        assert "ಎಂಟು ನೂರು" in result
        assert "ಗ್ರಾಂ" in result

    def test_english_2_8_no_decimal(self):
        result = weight_to_words(2.8, "en-IN")
        assert "two" in result.lower()
        assert "kilo" in result.lower()
        assert "eight" in result.lower()
        assert "gram" in result.lower()
        assert "." not in result  # D6: never decimal point

    def test_whole_kg_no_gram_suffix(self):
        result = weight_to_words(3.0, "hi-IN")
        assert "तीन" in result
        assert "किलो" in result
        assert "ग्राम" not in result  # 0 grams → no gram part

    def test_hindi_58_kg_mother(self):
        result = weight_to_words(58.0, "hi-IN")
        assert "अट्ठावन" in result
        assert "किलो" in result


# ════════════════════════════════════════════════════════════════════════════════
# render_number (single entry point for speak())
# ════════════════════════════════════════════════════════════════════════════════

class TestRenderNumber:
    def test_weight_hindi(self):
        result = render_number("hi-IN", "weight", 2.8)
        assert "किलो" in result

    def test_id_digit_by_digit_hindi(self):
        result = render_number("hi-IN", "id", "1042")
        assert "एक" in result  # digit-by-digit always

    def test_date_hindi(self):
        result = render_number("hi-IN", "date", date(2026, 12, 15))
        assert "पंद्रह" in result
        assert "दिसंबर" in result

    def test_count_hindi(self):
        result = render_number("hi-IN", "count", 5)
        assert "पाँच" in result

    def test_english_weight(self):
        result = render_number("en-IN", "weight", 2.8)
        assert "kilo" in result.lower()

    def test_unknown_kind_fallback_no_crash(self):
        result = render_number("en-IN", "unknown_kind", 42)
        assert "42" in result


# ════════════════════════════════════════════════════════════════════════════════
# parse_spoken_number  (reverse lookup)
# ════════════════════════════════════════════════════════════════════════════════

class TestParseSpokenNumber:
    def test_hindi_devanagari_digit_word(self):
        assert parse_spoken_number("आठ", "hi-IN") == 8

    def test_kannada_script_digit_word(self):
        assert parse_spoken_number("ಎಂಟು", "kn-IN") == 8

    def test_english_word(self):
        assert parse_spoken_number("eight", "en-IN") == 8

    def test_plain_digit_string(self):
        assert parse_spoken_number("8", "hi-IN") == 8

    def test_unknown_word_returns_none(self):
        assert parse_spoken_number("gibberish", "hi-IN") is None

    def test_empty_returns_none(self):
        assert parse_spoken_number("", "hi-IN") is None

    def test_none_returns_none(self):
        assert parse_spoken_number(None, "hi-IN") is None  # type: ignore

    # Round-trip tests: number → word → parse back
    def test_roundtrip_hindi_digit_8(self):
        """8 → 'आठ' → 8"""
        word = str(MOCK_TABLES["hi"]["digits"][8])
        assert parse_spoken_number(word, "hi-IN") == 8

    def test_roundtrip_hindi_number_15(self):
        """15 → 'पंद्रह' → 15"""
        word = str(MOCK_TABLES["hi"]["numbers"][15])
        assert parse_spoken_number(word, "hi-IN") == 15

    def test_roundtrip_hindi_number_28(self):
        """28 → 'अट्ठाईस' → 28"""
        word = str(MOCK_TABLES["hi"]["numbers"][28])
        assert parse_spoken_number(word, "hi-IN") == 28

    def test_roundtrip_kannada_digit_4(self):
        """4 → 'ನಾಲ್ಕು' → 4"""
        word = str(MOCK_TABLES["kn"]["digits"][4])
        assert parse_spoken_number(word, "kn-IN") == 4

    def test_roundtrip_kannada_number_10(self):
        """10 → 'ಹತ್ತು' → 10"""
        word = str(MOCK_TABLES["kn"]["numbers"][10])
        assert parse_spoken_number(word, "kn-IN") == 10

    def test_roundtrip_kannada_number_15(self):
        """15 → 'ಹದಿನೈದು' → 15"""
        word = str(MOCK_TABLES["kn"]["numbers"][15])
        assert parse_spoken_number(word, "kn-IN") == 15

    def test_roundtrip_english_8(self):
        assert parse_spoken_number("eight", "en-IN") == 8

    def test_roundtrip_english_zero(self):
        assert parse_spoken_number("zero", "en-IN") == 0
