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


def _api(rows: int, quarters: int | None, span: str = "2001 Q2–2026 Q1", truncated: bool = False) -> dict:
    """A query_public_api envelope as the tool returns it (app.live.public_api), counts and wording only."""
    periods = f"{quarters} quarters, {span}" if quarters else None
    meaning = f"One row is one airport-pair market in one quarter (Table 1a record). The result has {rows} rows"
    if quarters is None:
        meaning += " and no period columns, so it states no period count."
    elif quarters == rows:
        meaning += f" covering {quarters} distinct quarters ({span}): one row per quarter."
    else:
        meaning += (f" covering {quarters} distinct quarters ({span}), so one quarter can span several rows; count "
                    "quarters from `periods`, rows from `row_count`.")
    assumptions = ["Ad-hoc SoQL over tfrh-tu9e written by the agent; the query is shown with the result.", meaning]
    if truncated:
        assumptions.append(f"Only the first {rows} rows were returned (limit {rows}); more rows match the query, "
                           "so the period count covers the returned rows only.")
    return {"data": {"row_count": rows, "period_count": quarters, "periods": periods, "truncated": truncated},
            "sources": [{"name": "DOT Consumer Airfare Report Table 1a", "window": periods}],
            "assumptions": assumptions, "ad_hoc": True}


def _table(n: int) -> str:
    rows = [f"| {2026 - i // 4} | {4 - i % 4} | 345.59 |" for i in range(n)]
    return "\n".join(["| Year | Quarter | Avg fare ($) |", "|---|---|---|", *rows])


FULL = [_api(100, 100, truncated=True)]  # 100 rows, one per quarter, 2001 Q2–2026 Q1


def test_misstated_counts_true_full_count_passes():
    text = ("The query returned 100 quarters, from 2001 Q2 to 2026 Q1, in 100 rows. "
            "Source: DOT Table 1a, window 100 quarters, 2001 Q2–2026 Q1.")
    assert misstated_counts(text, FULL) == []


def test_misstated_counts_a_subset_must_match_the_table_the_answer_shows():
    text = "The table shows the latest 12 quarters.\n\n{}\n\nThe query returned 100 quarters."
    assert misstated_counts(text.format(_table(12)), FULL) == []
    # The old rule let any N below the returned count through; 12 quarters over a 10-row table is wrong.
    assert misstated_counts(text.format(_table(10)), FULL) == ["12 quarters"]
    assert misstated_counts("The latest 12 quarters averaged 345.59.", FULL) == ["12 quarters"]


def test_misstated_counts_rows_are_not_quarters():
    # 100 rows over 25 distinct quarters: "100 quarters" fails although the tool's assumptions say "100 rows".
    many_rows = [_api(100, 25, span="2020 Q1–2026 Q1", truncated=True)]
    assert misstated_counts("Window returned: 100 quarters", many_rows) == ["100 quarters"]
    assert misstated_counts("It returned 100 rows covering 25 distinct quarters.", many_rows) == []
    assert misstated_counts("It returned 37 quarters in 120 rows", [_api(100, 37)]) == ["120 rows"]
    assert misstated_counts("over 40 quarters", [_api(100, 37)]) == ["40 quarters"]
    assert misstated_counts("5 quarters", [_api(5, None)]) == ["5 quarters"]
    assert misstated_counts("100 months", FULL) == ["100 months"]  # the unit must match too


def test_misstated_counts_source_windows_and_grouped_counts():
    window = [{"sources": [{"window": "12 months, Aug 2025–Jul 2026"}], "data": {"row_count": "1,005"}}]
    assert misstated_counts("Window: 12 months, all carriers; 1,005 rows.", window) == []
    assert misstated_counts("over 24 months", window) == ["24 months"]
    # "year 2026, months 6 and 7" is not a count of 2,026 months.
    assert misstated_counts("filtered to year 2026, months 6 and 7", window) == []
