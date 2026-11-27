"""Hrvatski kalendar: državni praznici, radni dani i pomoćne funkcije za datume.

Radni dan je dan koji nije subota, nedjelja ni državni praznik u Hrvatskoj
(prema Zakonu o blagdanima, spomendanima i neradnim danima, od 2020.).
"""

import calendar
import re
from datetime import date, timedelta
from functools import cache

# Praznici s fiksnim datumom: (mjesec, dan)
_FIXED_HOLIDAYS = [
    (1, 1),    # Nova godina
    (1, 6),    # Bogojavljenje ili Sveta tri kralja
    (5, 1),    # Praznik rada
    (5, 30),   # Dan državnosti
    (6, 22),   # Dan antifašističke borbe
    (8, 5),    # Dan pobjede i domovinske zahvalnosti i Dan hrvatskih branitelja
    (8, 15),   # Velika Gospa
    (11, 1),   # Svi sveti
    (11, 18),  # Dan sjećanja na žrtve Domovinskog rata
    (12, 25),  # Božić
    (12, 26),  # Sveti Stjepan
]


def easter(year: int) -> date:
    """Datum Uskrsa (gregorijanski kalendar), anonimni algoritam Meeus/Jones/Butcher."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


@cache
def holidays(year: int) -> frozenset[date]:
    """Svi hrvatski državni praznici u zadanoj godini."""
    e = easter(year)
    movable = {
        e,                          # Uskrs
        e + timedelta(days=1),      # Uskrsni ponedjeljak
        e + timedelta(days=60),     # Tijelovo
    }
    return frozenset({date(year, m, d) for m, d in _FIXED_HOLIDAYS} | movable)


def is_workday(d: date) -> bool:
    return d.weekday() < 5 and d not in holidays(d.year)


def next_workday(d: date) -> date:
    """Prvi radni dan od `d` nadalje (vraća `d` ako je radni)."""
    while not is_workday(d):
        d += timedelta(days=1)
    return d


def prev_workday(d: date) -> date:
    """Zadnji radni dan do `d` uključivo (vraća `d` ako je radni)."""
    while not is_workday(d):
        d -= timedelta(days=1)
    return d


def last_day_of_month(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def add_months(d: date, n: int) -> date:
    """Pomiče datum za `n` mjeseci; dan se reže na kraj mjeseca (31.1. + 1 = 28.2.)."""
    index = d.year * 12 + (d.month - 1) + n
    year, month0 = divmod(index, 12)
    last = last_day_of_month(year, month0 + 1)
    return date(year, month0 + 1, min(d.day, last.day))


_HR_DATE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\.?")


def parse_date(text: str) -> date:
    """Prihvaća ISO zapis (2026-12-05) i hrvatski zapis (05.12.2026. ili 5.12.2026)."""
    s = text.strip()
    try:
        m = _HR_DATE.fullmatch(s)
        if m:
            day, month, year = map(int, m.groups())
            return date(year, month, day)
        return date.fromisoformat(s)
    except ValueError:
        raise ValueError(f"Neispravan datum: '{text}'") from None
