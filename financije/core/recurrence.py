"""Pravila ponavljanja: iz pravila računa datume pojavljivanja stavke.

Primjer: najam "svakog 5. u mjesecu, pomak na sljedeći radni dan" u prosincu 2026.
ima nominalni datum 5.12. (subota) i stvarni datum dospijeća 7.12. (ponedjeljak).
"""

from datetime import date, timedelta

from .calendar_hr import (
    add_months, is_workday, last_day_of_month, next_workday, parse_date, prev_workday,
)
from .models import RULE_TYPES, SHIFTS, Occurrence, RecurringItem, Rule

# Koliko dana izvan traženog raspona tražimo nominalne datume, da bi pojavljivanje
# koje se pomakom prelije preko granice raspona bilo ispravno uključeno.
# (Najdulji niz neradnih dana u Hrvatskoj je 3-4 dana.)
_SHIFT_MARGIN = timedelta(days=10)


def _invalid(what: object, reason: str = "") -> ValueError:
    suffix = f" ({reason})" if reason else ""
    return ValueError(f"Neispravno pravilo: '{what}'{suffix}")


def validate_rule(rule: Rule) -> None:
    """Baca ValueError ako pravilo nema smisla."""
    if rule.type not in RULE_TYPES:
        raise _invalid(rule.type, "nepoznata vrsta pravila")
    if rule.shift not in SHIFTS:
        raise _invalid(rule.shift, "nepoznat pomak")
    if rule.type == "monthly_day":
        if rule.day is None or not 1 <= rule.day <= 31:
            raise _invalid(rule.day, "dan mora biti od 1 do 31")
    elif rule.type == "nth_workday":
        if rule.n is None or not 1 <= rule.n <= 23:
            raise _invalid(rule.n, "redni broj radnog dana mora biti od 1 do 23")
    elif rule.type == "weekly":
        if rule.every is None or rule.every < 1:
            raise _invalid(rule.every, "razmak u tjednima mora biti barem 1")
        if rule.anchor is None:
            raise _invalid("weekly", "nedostaje početni datum")
    elif rule.type == "yearly":
        if rule.month is None or rule.day is None:
            raise _invalid("yearly", "nedostaje mjesec ili dan")
        try:
            date(2000, rule.month, rule.day)   # 2000. je prijestupna: 29.2. je dopušten
        except ValueError:
            raise _invalid(f"{rule.day}.{rule.month}.", "takav datum ne postoji") from None


def rule_to_dict(rule: Rule) -> dict:
    d: dict = {"type": rule.type}
    for key in ("day", "n", "every", "month"):
        value = getattr(rule, key)
        if value is not None:
            d[key] = value
    if rule.anchor is not None:
        d["anchor"] = rule.anchor.isoformat()
    d["shift"] = rule.shift
    return d


def rule_from_dict(d: dict) -> Rule:
    anchor = d.get("anchor")
    return Rule(
        type=d["type"], day=d.get("day"), n=d.get("n"), every=d.get("every"),
        anchor=date.fromisoformat(anchor) if anchor else None,
        month=d.get("month"), shift=d.get("shift", "none"),
    )


def parse_rule_spec(text: str, shift: str = "none") -> Rule:
    """Skraćeni zapis pravila (za terminal):

    monthly_day:5 | last_workday | nth_workday:1 | weekly:2:2026-01-09 | yearly:3-14
    """
    parts = text.strip().split(":", 2)
    kind, args = parts[0], parts[1:]
    try:
        if kind == "monthly_day" and len(args) == 1:
            rule = Rule("monthly_day", day=int(args[0]), shift=shift)
        elif kind == "last_workday" and not args:
            rule = Rule("last_workday", shift=shift)
        elif kind == "nth_workday" and len(args) == 1:
            rule = Rule("nth_workday", n=int(args[0]), shift=shift)
        elif kind == "weekly" and len(args) == 2:
            rule = Rule("weekly", every=int(args[0]), anchor=parse_date(args[1]), shift=shift)
        elif kind == "yearly" and len(args) == 1:
            month, day = args[0].split("-")
            rule = Rule("yearly", month=int(month), day=int(day), shift=shift)
        else:
            raise _invalid(text)
    except ValueError as e:
        if str(e).startswith("Neispravno pravilo"):
            raise
        raise _invalid(text) from None
    validate_rule(rule)
    return rule


_SHIFT_TEXT = {
    "next_workday": "pomak na sljedeći radni dan",
    "prev_workday": "pomak na prethodni radni dan",
}


def describe_rule(rule: Rule) -> str:
    """Opis pravila na hrvatskom, za prikaz korisniku."""
    match rule.type:
        case "monthly_day":
            text = f"svakog {rule.day}. u mjesecu"
        case "last_workday":
            return "zadnji radni dan u mjesecu"
        case "nth_workday":
            return f"{rule.n}. radni dan u mjesecu"
        case "weekly":
            start = rule.anchor.strftime("%d.%m.%Y.")
            if rule.every == 1:
                text = f"svaki tjedan od {start}"
            elif rule.every % 10 in (2, 3, 4) and rule.every % 100 not in (12, 13, 14):
                text = f"svaka {rule.every} tjedna od {start}"
            else:
                text = f"svakih {rule.every} tjedana od {start}"
        case "yearly":
            text = f"svake godine {rule.day}.{rule.month}."
        case _:
            text = rule.type
    if rule.shift in _SHIFT_TEXT:
        text += f" ({_SHIFT_TEXT[rule.shift]})"
    return text


def _shift(d: date, shift: str) -> date:
    if shift == "next_workday":
        return next_workday(d)
    if shift == "prev_workday":
        return prev_workday(d)
    return d


def _months(start: date, end: date):
    """(godina, mjesec) za svaki mjesec od `start` do `end`."""
    current = date(start.year, start.month, 1)
    while current <= end:
        yield current.year, current.month
        current = add_months(current, 1)


def _nominal_dates(rule: Rule, start: date, end: date) -> list[date]:
    """Datumi po pravilu (prije pomaka) unutar [start, end]."""
    result: list[date] = []
    match rule.type:
        case "monthly_day":
            for y, m in _months(start, end):
                last = last_day_of_month(y, m)
                result.append(date(y, m, min(rule.day, last.day)))
        case "last_workday":
            for y, m in _months(start, end):
                result.append(prev_workday(last_day_of_month(y, m)))
        case "nth_workday":
            for y, m in _months(start, end):
                day, count = date(y, m, 1), 0
                while day.month == m:
                    if is_workday(day):
                        count += 1
                        if count == rule.n:
                            result.append(day)
                            break
                    day += timedelta(days=1)
        case "weekly":
            step = timedelta(weeks=rule.every)
            current = rule.anchor
            if current < start:
                periods = (start - current) // step
                current += periods * step
            while current <= end:
                result.append(current)
                current += step
        case "yearly":
            for y in range(start.year, end.year + 1):
                last = last_day_of_month(y, rule.month)
                result.append(date(y, rule.month, min(rule.day, last.day)))
    return [x for x in result if start <= x <= end]


def occurrences(rule: Rule, start: date, end: date) -> list[Occurrence]:
    """Pojavljivanja čiji je datum dospijeća (nakon pomaka) unutar [start, end]."""
    validate_rule(rule)
    nominals = _nominal_dates(rule, start - _SHIFT_MARGIN, end + _SHIFT_MARGIN)
    result = []
    for nominal in nominals:
        # Za pravila koja već daju radni dan pomak nema smisla.
        due = nominal if rule.type in ("last_workday", "nth_workday") else _shift(nominal, rule.shift)
        if start <= due <= end:
            result.append(Occurrence(nominal, due))
    return sorted(result, key=lambda o: o.due)


def item_occurrences(item: RecurringItem, start: date, end: date) -> list[Occurrence]:
    """Pojavljivanja stavke unutar [start, end], uz poštivanje njezina razdoblja važenja."""
    if not item.active:
        return []
    return [
        o for o in occurrences(item.rule, start, end)
        if (item.start_date is None or o.nominal >= item.start_date)
        and (item.end_date is None or o.nominal <= item.end_date)
    ]
