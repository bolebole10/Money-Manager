from datetime import date as d

import pytest

from financije.core.models import Occurrence, RecurringItem, Rule
from financije.core.recurrence import (
    describe_rule, item_occurrences, occurrences, parse_rule_spec, rule_from_dict,
    rule_to_dict, validate_rule,
)


def dues(rule, a, b):
    return [o.due for o in occurrences(rule, a, b)]


def test_monthly_day_clamps_short_months():
    assert dues(Rule("monthly_day", day=31), d(2026, 1, 1), d(2026, 4, 30)) == [
        d(2026, 1, 31), d(2026, 2, 28), d(2026, 3, 31), d(2026, 4, 30)]
    assert dues(Rule("monthly_day", day=31), d(2028, 2, 1), d(2028, 2, 29)) == [d(2028, 2, 29)]


def test_monthly_day_shift():
    # 5.12.2026. je subota -> najam se plaća u ponedjeljak 7.12.
    assert occurrences(Rule("monthly_day", day=5, shift="next_workday"), d(2026, 12, 1), d(2026, 12, 31)) == [
        Occurrence(d(2026, 12, 5), d(2026, 12, 7))]
    # 25.12. Božić (pet), 26.12. Sveti Stjepan (sub), 27.12. nedjelja
    assert dues(Rule("monthly_day", day=25, shift="next_workday"), d(2026, 12, 1), d(2026, 12, 31)) == [d(2026, 12, 28)]
    assert dues(Rule("monthly_day", day=25, shift="prev_workday"), d(2026, 12, 1), d(2026, 12, 31)) == [d(2026, 12, 24)]
    assert dues(Rule("monthly_day", day=5), d(2026, 12, 1), d(2026, 12, 31)) == [d(2026, 12, 5)]


def test_shift_across_range_boundary():
    # 31.10.2026. je subota -> pomak na ponedjeljak 2.11.
    r = Rule("monthly_day", day=31, shift="next_workday")
    assert dues(r, d(2026, 10, 1), d(2026, 10, 31)) == []
    assert occurrences(r, d(2026, 11, 1), d(2026, 11, 30))[0] == Occurrence(d(2026, 10, 31), d(2026, 11, 2))


def test_last_workday():
    r = Rule("last_workday")
    # 31.5.2026. nedjelja, 30.5. subota i Dan državnosti -> petak 29.5.
    assert dues(r, d(2026, 5, 1), d(2026, 5, 31)) == [d(2026, 5, 29)]
    assert dues(r, d(2026, 11, 1), d(2027, 1, 31)) == [d(2026, 11, 30), d(2026, 12, 31), d(2027, 1, 29)]


def test_nth_workday_skips_holiday():
    # 1.1.2027. petak, Nova godina -> prvi radni dan je ponedjeljak 4.1.
    assert dues(Rule("nth_workday", n=1), d(2027, 1, 1), d(2027, 1, 31)) == [d(2027, 1, 4)]
    assert dues(Rule("nth_workday", n=2), d(2027, 1, 1), d(2027, 1, 31)) == [d(2027, 1, 5)]


def test_weekly():
    r = Rule("weekly", every=2, anchor=d(2026, 1, 9))
    assert dues(r, d(2026, 1, 1), d(2026, 2, 28)) == [d(2026, 1, 9), d(2026, 1, 23), d(2026, 2, 6), d(2026, 2, 20)]
    assert dues(r, d(2025, 12, 1), d(2025, 12, 31)) == []      # prije sidrenog datuma nema ničega


def test_yearly_feb_29():
    r = Rule("yearly", month=2, day=29)
    assert dues(r, d(2027, 1, 1), d(2027, 12, 31)) == [d(2027, 2, 28)]
    assert dues(r, d(2028, 1, 1), d(2028, 12, 31)) == [d(2028, 2, 29)]


def test_item_occurrences_respects_period_and_active():
    item = RecurringItem(None, "Netflix", -1199, Rule("monthly_day", day=15),
                         start_date=d(2026, 10, 1), end_date=d(2026, 12, 31))
    got = [o.nominal for o in item_occurrences(item, d(2026, 9, 1), d(2027, 2, 28))]
    assert got == [d(2026, 10, 15), d(2026, 11, 15), d(2026, 12, 15)]
    item.active = False
    assert item_occurrences(item, d(2026, 9, 1), d(2027, 2, 28)) == []


@pytest.mark.parametrize("spec,rule", [
    ("monthly_day:5", Rule("monthly_day", day=5)),
    ("last_workday", Rule("last_workday")),
    ("nth_workday:1", Rule("nth_workday", n=1)),
    ("weekly:2:2026-01-09", Rule("weekly", every=2, anchor=d(2026, 1, 9))),
    ("yearly:3-14", Rule("yearly", month=3, day=14)),
])
def test_parse_rule_spec(spec, rule):
    assert parse_rule_spec(spec) == rule
    assert rule_from_dict(rule_to_dict(rule)) == rule


def test_parse_rule_spec_with_shift():
    assert parse_rule_spec("monthly_day:5", shift="next_workday") == Rule("monthly_day", day=5, shift="next_workday")


@pytest.mark.parametrize("bad", [
    "monthly_day:0", "monthly_day:32", "weekly:0:2026-01-09", "weekly:2", "yearly:2-30",
    "yearly:13-1", "daily", "monthly_day:x", "nth_workday:0", "",
])
def test_parse_rule_spec_rejects(bad):
    with pytest.raises(ValueError, match="Neispravno pravilo"):
        parse_rule_spec(bad)


def test_validate_rule_rejects_bad_shift():
    with pytest.raises(ValueError, match="Neispravno pravilo"):
        validate_rule(Rule("monthly_day", day=5, shift="sideways"))


def test_describe_rule():
    assert describe_rule(Rule("last_workday")) == "zadnji radni dan u mjesecu"
    assert describe_rule(Rule("monthly_day", day=5, shift="next_workday")) == \
        "svakog 5. u mjesecu (pomak na sljedeći radni dan)"
    assert describe_rule(Rule("nth_workday", n=1)) == "1. radni dan u mjesecu"
    assert describe_rule(Rule("weekly", every=2, anchor=d(2026, 1, 9))) == "svaka 2 tjedna od 09.01.2026."
    assert describe_rule(Rule("weekly", every=1, anchor=d(2026, 1, 9))) == "svaki tjedan od 09.01.2026."
    assert describe_rule(Rule("weekly", every=5, anchor=d(2026, 1, 9))) == "svakih 5 tjedana od 09.01.2026."
    assert describe_rule(Rule("yearly", month=3, day=14, shift="prev_workday")) == \
        "svake godine 14.3. (pomak na prethodni radni dan)"
