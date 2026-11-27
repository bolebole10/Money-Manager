"""Model podataka aplikacije (čisti dataclassovi, bez logike pohrane).

Iznosi su u centima (int): prihodi pozitivni, troškovi negativni.
"""

from dataclasses import dataclass
from datetime import date

RULE_TYPES = ("monthly_day", "last_workday", "nth_workday", "weekly", "yearly")
SHIFTS = ("none", "next_workday", "prev_workday")
CATEGORY_KINDS = ("fixed", "variable", "income", "other")


@dataclass
class Rule:
    """Pravilo ponavljanja.

    type:
      - monthly_day  -- `day`-ti dan u mjesecu (reže se na kraj kraćih mjeseci)
      - last_workday -- zadnji radni dan u mjesecu
      - nth_workday  -- `n`-ti radni dan u mjesecu
      - weekly       -- svakih `every` tjedana počevši od `anchor`
      - yearly       -- svake godine `day`.`month`. (29.2. -> 28.2. u neprijestupnoj)
    shift: što ako datum padne na neradni dan (none / next_workday / prev_workday).
    """
    type: str
    day: int | None = None
    n: int | None = None
    every: int | None = None
    anchor: date | None = None
    month: int | None = None
    shift: str = "none"


@dataclass(frozen=True)
class Occurrence:
    """Jedno pojavljivanje stavke: `nominal` je datum po pravilu, `due` nakon pomaka."""
    nominal: date
    due: date


@dataclass
class Category:
    id: int | None
    name: str
    kind: str


@dataclass
class RecurringItem:
    """Očekivana ponavljajuća stavka (plaća, najam, pretplata...)."""
    id: int | None
    name: str
    amount_cents: int
    rule: Rule
    category_id: int | None = None
    match_pattern: str = ""            # tekst po kojem se stavka prepoznaje u izvodu
    amount_tolerance_cents: int = 0
    amount_tolerance_pct: float = 0.0
    date_window_days: int = 7
    start_date: date | None = None
    end_date: date | None = None
    active: bool = True
    note: str = ""


@dataclass
class Transaction:
    """Stvarna transakcija (iz izvoda) ili ručno upisana jednokratna stavka."""
    id: int | None
    date: date
    amount_cents: int
    description: str
    category_id: int | None = None
    counterparty: str = ""
    import_id: int | None = None
    fingerprint: str | None = None
    balance_after_cents: int | None = None
    note: str = ""


@dataclass
class BalanceCheckpoint:
    """Poznato stvarno stanje računa na određeni dan (source: manual / import)."""
    date: date
    balance_cents: int
    source: str
