from datetime import date as d

import pytest

from financije.core.models import RecurringItem, Rule, Transaction
from financije.core.projection import project

ITEMS = [
    RecurringItem(1, "Plaća", 150000, Rule("last_workday")),
    RecurringItem(2, "Najam", -40000, Rule("monthly_day", day=5, shift="next_workday")),
    RecurringItem(3, "Netflix", -1199, Rule("monthly_day", day=15)),
]


def test_hand_computed_example():
    # Ručni izračun, stanje 500,00 € na 27.11.2026.:
    #   30.11. Plaća      +1500,00 -> 2000,00
    #    7.12. Najam       -400,00 -> 1600,00   (5.12. je subota)
    #   15.12. Netflix      -11,99 -> 1588,01
    #   20.12. Poklon      -120,00 -> 1468,01   (planirana jednokratna stavka)
    #   31.12. Plaća      +1500,00 -> 2968,01
    #    5.1.  Najam       -400,00 -> 2568,01
    #   15.1.  Netflix      -11,99 -> 2556,02
    #   29.1.  Plaća      +1500,00 -> 4056,02   (31.1. je nedjelja)
    tx = [Transaction(None, d(2026, 12, 20), -12000, "Poklon"),
          Transaction(None, d(2026, 11, 27), -999, "Već uračunato u stanje")]
    p = project(d(2026, 11, 27), 50000, d(2027, 1, 31), ITEMS, tx)

    assert len(p.days) == 65
    assert p.days[0].date == d(2026, 11, 28) and p.days[-1].date == d(2027, 1, 31)
    assert p.month_ends == [(d(2026, 11, 30), 200000), (d(2026, 12, 31), 296801), (d(2027, 1, 31), 405602)]
    by_date = {day.date: day for day in p.days}
    assert [e.label for e in by_date[d(2026, 12, 7)].entries] == ["Najam"]
    assert by_date[d(2026, 12, 20)].entries[0].kind == "one_off"
    assert by_date[d(2026, 12, 20)].balance_cents == 146801
    assert (p.min_balance_cents, p.min_date) == (50000, d(2026, 11, 28))


def test_same_day_order_recurring_first():
    items = [RecurringItem(1, "Plaća", 150000, Rule("monthly_day", day=10)),
             RecurringItem(2, "Najam", -40000, Rule("monthly_day", day=10))]
    tx = [Transaction(None, d(2026, 12, 10), -1000, "Kava")]
    p = project(d(2026, 12, 1), 0, d(2026, 12, 10), items, tx)
    assert [e.label for e in p.days[-1].entries] == ["Najam", "Plaća", "Kava"]
    assert p.days[-1].balance_cents == 109000


def test_minimum_goes_negative():
    p = project(d(2026, 12, 1), 30000, d(2026, 12, 31), ITEMS[:2], [])
    assert (p.min_balance_cents, p.min_date) == (-10000, d(2026, 12, 7))
    assert p.month_ends == [(d(2026, 12, 31), 140000)]


def test_inactive_and_ended_items_ignored():
    items = [RecurringItem(1, "Stara pretplata", -1000, Rule("monthly_day", day=10), end_date=d(2026, 11, 30)),
             RecurringItem(2, "Pauzirano", -2000, Rule("monthly_day", day=10), active=False)]
    p = project(d(2026, 12, 1), 10000, d(2026, 12, 31), items, [])
    assert all(not day.entries for day in p.days)
    assert p.month_ends == [(d(2026, 12, 31), 10000)]


def test_empty_range_and_invalid():
    p = project(d(2026, 12, 1), 30000, d(2026, 12, 1), ITEMS, [])
    assert p.days == [] and p.month_ends == []
    assert (p.min_balance_cents, p.min_date) == (30000, d(2026, 12, 1))
    with pytest.raises(ValueError):
        project(d(2026, 12, 2), 0, d(2026, 12, 1), ITEMS, [])
