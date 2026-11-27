"""Projekcija stanja računa.

Polazi od poznatog stanja na dan `start_date` (to stanje već uključuje sve
s tog dana) i za svaki sljedeći dan do `end_date` dodaje:
  - pojavljivanja ponavljajućih stavki (plaća, najam, pretplate...),
  - ručno upisane jednokratne stavke s datumom u budućnosti.

(M5 dodaje zaostale stavke iz usklađivanja i procjenu promjenjivih troškova.)
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from .calendar_hr import last_day_of_month
from .models import RecurringItem, Transaction
from .recurrence import item_occurrences


@dataclass
class ProjectionEntry:
    date: date
    amount_cents: int
    label: str
    kind: str          # "recurring" | "one_off"


@dataclass
class ProjectionDay:
    date: date
    balance_cents: int                       # stanje na kraju dana
    entries: list[ProjectionEntry] = field(default_factory=list)


@dataclass
class Projection:
    start_date: date
    start_balance_cents: int
    end_date: date
    days: list[ProjectionDay]
    month_ends: list[tuple[date, int]]       # stanje na zadnji dan svakog mjeseca
    min_balance_cents: int
    min_date: date


def project(
    start_date: date,
    start_balance_cents: int,
    end_date: date,
    items: list[RecurringItem],
    transactions: list[Transaction],
) -> Projection:
    if end_date < start_date:
        raise ValueError("Kraj projekcije ne može biti prije početka.")

    first = start_date + timedelta(days=1)
    by_date: dict[date, list[ProjectionEntry]] = {}

    recurring = [
        ProjectionEntry(o.due, item.amount_cents, item.name, "recurring")
        for item in items
        for o in item_occurrences(item, first, end_date)
    ]
    one_off = [
        ProjectionEntry(t.date, t.amount_cents, t.description, "one_off")
        for t in transactions
        if first <= t.date <= end_date
    ]
    # Unutar dana: prvo ponavljajuće stavke po imenu, zatim jednokratne.
    for entry in sorted(recurring, key=lambda e: e.label) + one_off:
        by_date.setdefault(entry.date, []).append(entry)

    days: list[ProjectionDay] = []
    month_ends: list[tuple[date, int]] = []
    balance = start_balance_cents
    min_balance, min_date = start_balance_cents, start_date
    current = first
    while current <= end_date:
        entries = by_date.get(current, [])
        balance += sum(e.amount_cents for e in entries)
        days.append(ProjectionDay(current, balance, entries))
        # Prvi dan projekcije uvijek postavlja minimum, kasniji samo ako je strogo manji.
        if len(days) == 1 or balance < min_balance:
            min_balance, min_date = balance, current
        if current == last_day_of_month(current.year, current.month):
            month_ends.append((current, balance))
        current += timedelta(days=1)

    return Projection(start_date, start_balance_cents, end_date, days, month_ends, min_balance, min_date)
