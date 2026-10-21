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
