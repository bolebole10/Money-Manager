from datetime import date

import pytest

from financije.core.calendar_hr import (
    add_months, easter, holidays, is_workday, last_day_of_month, next_workday,
    parse_date, prev_workday,
)


@pytest.mark.parametrize("year,d", [
    (2019, date(2019, 4, 21)), (2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)),
    (2026, date(2026, 4, 5)), (2027, date(2027, 3, 28)),
])
def test_easter(year, d):
    assert easter(year) == d


def test_holidays_2026():
    h = holidays(2026)
    assert len(h) == 14
    # Uskrsni ponedjeljak, Tijelovo (Uskrs + 60), Dan državnosti, Dan sjećanja
    assert {date(2026, 4, 6), date(2026, 6, 4), date(2026, 5, 30), date(2026, 11, 18)} <= h


def test_workdays():
    assert not is_workday(date(2026, 12, 25))   # Božić, petak
    assert not is_workday(date(2026, 12, 5))    # subota
    assert is_workday(date(2026, 11, 30))
    assert next_workday(date(2026, 12, 25)) == date(2026, 12, 28)
    assert prev_workday(date(2026, 12, 25)) == date(2026, 12, 24)
    assert next_workday(date(2026, 11, 30)) == date(2026, 11, 30)
    assert prev_workday(date(2027, 1, 1)) == date(2026, 12, 31)   # preko granice godine


def test_month_helpers():
    assert last_day_of_month(2026, 2) == date(2026, 2, 28)
    assert last_day_of_month(2028, 2) == date(2028, 2, 29)
    assert last_day_of_month(2026, 12) == date(2026, 12, 31)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 11, 27), 3) == date(2027, 2, 27)
    assert add_months(date(2026, 3, 31), -1) == date(2026, 2, 28)


@pytest.mark.parametrize("text", ["2026-12-05", "05.12.2026.", "5.12.2026", " 5.12.2026. "])
def test_parse_date(text):
    assert parse_date(text) == date(2026, 12, 5)


@pytest.mark.parametrize("bad", ["32.12.2026", "2026-13-01", "danas", "5.12.", ""])
def test_parse_date_rejects(bad):
    with pytest.raises(ValueError, match="Neispravan datum"):
        parse_date(bad)
