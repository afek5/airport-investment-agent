from tests.grounding import misstated_counts, ungrounded_numbers, ungrouped_counts

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


def test_ungrouped_counts_flag_bare_counts_but_not_years_or_labels():
    text = ("| F | 37,243 | 1005 | 2.7% |\nL charter 2289, total 1234.5; in 2026 and FY2030, 2025 Q3, "
            "rank 12, 30,516,426 and 3,000 miles, 999 flights")
    assert ungrouped_counts(text) == ["1005", "2289", "1234.5"]
    assert ungrouped_counts("FY2024 to FY2030, 2019–2025, 1,005 departures") == []


def test_misstated_counts_rows_versus_periods():
    live = ("The table shows the most recent 12 quarters. The query returned 100 quarters, 2001 Q2 to 2026 Q1. "
            "The query returned the first 100 rows.")
    assert misstated_counts(live, row_counts={100}, period_counts={100}) == []
    # 100 rows over 37 distinct quarters: calling them "100 quarters" is the defect.
    assert misstated_counts("Window returned: 100 quarters", row_counts={100}, period_counts={37}) == ["100 quarters"]
    assert misstated_counts("It returned 37 quarters in 120 rows", {100}, {37}) == ["120 rows"]
    assert misstated_counts("over 40 quarters", {100}, {37}) == ["40 quarters"]
    assert misstated_counts("5 quarters", {5}, set()) == ["5 quarters"]
