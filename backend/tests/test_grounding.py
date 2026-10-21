from tests.grounding import ungrounded_numbers

RESULT = {"data": {"share_pct": 29.5, "total": 87249, "window": "12 months, Aug 2025–Jul 2026", "pax": 2699637}}


def test_grounded_numbers_pass():
    text = "29.5% of 87,249 departures (12 months, Aug 2025–Jul 2026); 2.7 million passengers; 3 ways."
    assert ungrounded_numbers(text, [RESULT]) == []


def test_invented_numbers_fail():
    assert ungrounded_numbers("about 31.2% of 91,250 flights", [RESULT]) == ["31.2%", "91,250"]


def test_short_numbers_ignored_but_percentages_checked():
    assert ungrounded_numbers("12 months and 7 airports", [RESULT]) == []
    assert ungrounded_numbers("roughly 5%", [RESULT]) == ["5%"]


def test_scale_words_and_summed_tool_values():
    pool = [{"g_lh": 16234, "p_lh": 8409, "freight_lbs": 3474670762}]
    assert ungrounded_numbers("3.47 billion lbs of freight", pool) == []
    # 16,234 + 8,409: the LLM added two tool values (SPEC §6 forbids it), so it is not grounded.
    assert ungrounded_numbers("24,643 cargo long-haul departures", pool) == ["24,643"]


def test_malformed_digit_grouping_fails():
    pool = [{"enplanements_to": 30516426}]
    assert ungrounded_numbers("rises to 30,516,426 (FY2030)", pool) == []
    assert ungrounded_numbers("rises to 30,516426", pool) == ["30,516426"]
    # Comma-separated short lists are not numbers with bad grouping.
    assert ungrounded_numbers("months 6,7,8 of 2026", [{"y": 2026}]) == []
