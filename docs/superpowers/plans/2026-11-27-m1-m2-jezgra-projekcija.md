# M1 + M2: jezgra, pravila ponavljanja, osnovna projekcija i CLI — plan implementacije

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Do kraja II. KT (27.11.2026.) isporučiti jezgru (iznosi, hrvatski kalendar, pravila ponavljanja, SQLite pohrana), osnovnu projekciju stanja i terminalsko sučelje `fin`, u ≥2 smislena commita.

**Architecture:** Paket `financije/` s podpaketom `core/` (čista logika, bez typer/rich) i tankim `cli.py` (Typer + Rich) iznad njega. Iznosi su cijeli brojevi centi, datumi `datetime.date`, baza je jedna SQLite datoteka.

**Tech Stack:** Python 3.12, `sqlite3` (stdlib), `typer`, `rich`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-11-27-financije-design.md` (odjeljci 5, 6.1, 6.2, 6.7, 7.1, 8 — M1 i M2)

## Global Constraints

- Python ≥ 3.12; jedini jezik je Python.
- Ovisnosti u ovom planu: `typer`, `rich`; dev: `pytest`. Ništa drugo (praznici se računaju vlastitim kodom).
- `financije/core/*` ne smije uvoziti `typer`, `rich` ni `streamlit`.
- Svi iznosi u **centima (int)**; prihodi pozitivni, troškovi negativni.
- Imena u kodu na engleskom; tekst sučelja i poruke na hrvatskom.
- Baza: zadano `~/.financije/financije.db`, nadjačava se varijablom `FINANCIJE_DB` ili opcijom `--db`.
- Radni dan = nije subota/nedjelja ni hrvatski državni praznik (popis u Task 2).
- Rad u repozitoriju `/home/bojan/Documents/Money-Manager`, grana `main`, virtualno okruženje `.venv/`.

## Review Focus

1. Negativan iznos upisan u terminalu (`-400`, `-35,50`) Click čita kao opciju → mora raditi kao pozicijski argument (test u Task 6).
2. Iznos u hrvatskom zapisu s tisućicama i znakom valute (`1.234,56 €`), te `1234.56` → ispravni centi; besmislica → jasna greška (test u Task 1).
3. Pretplata s `end_date` (otkazana) ili `start_date` u budućnosti ne smije se pojaviti izvan svog razdoblja (test u Task 3).
4. `fin projekcija` bez ikakvog poznatog stanja → poruka na hrvatskom i izlazni kod 1, ne traceback (test u Task 6).
5. Ponovno otvaranje postojeće baze ne smije ponovno dodati zadane kategorije (test u Task 4).

---

## M1 — Jezgra: model, pohrana i pravila ponavljanja

### Task 1: Struktura projekta i iznosi (`money`)

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `financije/__init__.py`, `financije/core/__init__.py`, `financije/core/money.py`
- Test: `tests/test_money.py`

**Interfaces:**
- Produces: `parse_amount(text: str) -> int`, `format_amount(cents: int) -> str`

- [ ] **Step 1: Postavi projekt**

`pyproject.toml`: build backend `setuptools`, `name = "financije"`, `version = "0.1.0"`, `requires-python = ">=3.12"`, `dependencies = ["typer>=0.12", "rich>=13"]`, `[project.optional-dependencies] dev = ["pytest>=8"]`, `[project.scripts] fin = "financije.cli:app"`, paketi `financije*`. `.gitignore`: `.venv/`, `__pycache__/`, `*.db`, `.pytest_cache/`, `*.egg-info/`.

Run: `cd /home/bojan/Documents/Money-Manager && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
Expected: završava bez greške. (Instalacija `fin` skripte prijavit će grešku tek pri pokretanju dok `cli.py` ne postoji — to je u redu.)

- [ ] **Step 2: Napiši testove koji padaju**

```python
import pytest
from financije.core.money import parse_amount, format_amount

@pytest.mark.parametrize("text,cents", [
    ("1.234,56", 123456), ("-35,50", -3550), ("12", 1200), ("1.234,56 €", 123456),
    ("1234.56", 123456), ("-0,99", -99), ("1.234", 123400), ("+1500", 150000),
    (" 11,99 EUR ", 1199), ("1.000.000,00", 100000000),
])
def test_parse_amount(text, cents):
    assert parse_amount(text) == cents

@pytest.mark.parametrize("bad", ["", "abc", "1,2,3", "12,345", "--5"])
def test_parse_amount_rejects(bad):
    with pytest.raises(ValueError):
        parse_amount(bad)

@pytest.mark.parametrize("cents,text", [
    (123456, "1.234,56 €"), (-3550, "-35,50 €"), (0, "0,00 €"), (-99, "-0,99 €"), (100000000, "1.000.000,00 €"),
])
def test_format_amount(cents, text):
    assert format_amount(cents) == text
```

- [ ] **Step 3: Pokreni — mora pasti**

Run: `.venv/bin/pytest tests/test_money.py -q`
Expected: FAIL (`ModuleNotFoundError: financije.core.money`)

- [ ] **Step 4: Implementiraj `parse_amount` i `format_amount` u `financije/core/money.py`**

Pravila parsiranja: ukloni razmake, `€`, `EUR`; dopušten jedan predznak `+`/`-`. Ako postoji zarez → zarez je decimalni separator (najviše 2 znamenke iza), točke su tisućice. Ako nema zareza: točka iza koje su točno 1–2 znamenke na kraju je decimalna, inače su točke tisućice (`1.234` = 1234 €). Sve ostalo → `ValueError` s porukom na hrvatskom (`Neispravan iznos: '...'`). Koristi `decimal.Decimal` ili cjelobrojnu aritmetiku, nikad `float`.

- [ ] **Step 5: Pokreni — mora proći**

Run: `.venv/bin/pytest tests/test_money.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore financije tests/test_money.py docs
git commit -m "Postavljanje projekta i rad s iznosima u centima"
```

### Task 2: Hrvatski kalendar (`calendar_hr`)

**Files:**
- Create: `financije/core/calendar_hr.py`
- Test: `tests/test_calendar_hr.py`

**Interfaces:**
- Produces: `easter(year: int) -> date`, `holidays(year: int) -> frozenset[date]` (s `functools.cache`), `is_workday(d: date) -> bool`, `next_workday(d: date) -> date` (vraća `d` ako je radni), `prev_workday(d: date) -> date` (isto), `last_day_of_month(year: int, month: int) -> date`, `add_months(d: date, n: int) -> date` (dan se reže na kraj mjeseca), `parse_date(text: str) -> date` (prihvaća `2026-12-05`, `05.12.2026.`, `5.12.2026`; inače `ValueError` „Neispravan datum: '...'”).

Praznici (spec 6.2): 1.1., 6.1., Uskrs, Uskrsni ponedjeljak (Uskrs+1), 1.5., 30.5., Tijelovo (Uskrs+60), 22.6., 5.8., 15.8., 1.11., 18.11., 25.12., 26.12. Uskrs: anonimni gregorijanski algoritam (Meeus/Jones/Butcher).

- [ ] **Step 1: Napiši testove koji padaju**

```python
from datetime import date
import pytest
from financije.core.calendar_hr import (easter, holidays, is_workday, next_workday,
    prev_workday, last_day_of_month, add_months, parse_date)

@pytest.mark.parametrize("year,d", [(2024, date(2024,3,31)), (2025, date(2025,4,20)),
    (2026, date(2026,4,5)), (2027, date(2027,3,28)), (2019, date(2019,4,21))])
def test_easter(year, d):
    assert easter(year) == d

def test_holidays_2026():
    h = holidays(2026)
    assert len(h) == 14
    assert {date(2026,4,6), date(2026,6,4), date(2026,5,30), date(2026,11,18)} <= h

def test_workdays():
    assert not is_workday(date(2026,12,25))      # Božić, petak
    assert not is_workday(date(2026,12,5))       # subota
    assert is_workday(date(2026,11,30))
    assert next_workday(date(2026,12,25)) == date(2026,12,28)
    assert prev_workday(date(2026,12,25)) == date(2026,12,24)
    assert next_workday(date(2026,11,30)) == date(2026,11,30)

def test_month_helpers():
    assert last_day_of_month(2026, 2) == date(2026,2,28)
    assert last_day_of_month(2028, 2) == date(2028,2,29)
    assert add_months(date(2026,1,31), 1) == date(2026,2,28)
    assert add_months(date(2026,11,27), 3) == date(2027,2,27)

@pytest.mark.parametrize("text", ["2026-12-05", "05.12.2026.", "5.12.2026"])
def test_parse_date(text):
    assert parse_date(text) == date(2026,12,5)

def test_parse_date_rejects():
    with pytest.raises(ValueError):
        parse_date("32.12.2026")
```

- [ ] **Step 2: Pokreni — mora pasti**

Run: `.venv/bin/pytest tests/test_calendar_hr.py -q` → FAIL (modul ne postoji)

- [ ] **Step 3: Implementiraj sve funkcije iz Interfaces u `financije/core/calendar_hr.py`**

- [ ] **Step 4: Pokreni — mora proći**

Run: `.venv/bin/pytest -q` → PASS

- [ ] **Step 5: Commit**

```bash
git add financije/core/calendar_hr.py tests/test_calendar_hr.py
git commit -m "Hrvatski kalendar: praznici, Uskrs i radni dani"
```

### Task 3: Modeli i pravila ponavljanja (`models`, `recurrence`)

**Files:**
- Create: `financije/core/models.py`, `financije/core/recurrence.py`
- Test: `tests/test_recurrence.py`

**Interfaces:**
- Consumes: `calendar_hr` (Task 2)
- Produces (`models.py`, sve `@dataclass`):
  - `Rule(type: str, day: int | None = None, n: int | None = None, every: int | None = None, anchor: date | None = None, month: int | None = None, shift: str = "none")` — `type ∈ {"monthly_day","last_workday","nth_workday","weekly","yearly"}`, `shift ∈ {"none","next_workday","prev_workday"}`
  - `Occurrence(nominal: date, due: date)` — `frozen=True`
  - `Category(id: int | None, name: str, kind: str)` — `kind ∈ {"fixed","variable","income","other"}`
  - `RecurringItem(id: int | None, name: str, amount_cents: int, rule: Rule, category_id: int | None = None, match_pattern: str = "", amount_tolerance_cents: int = 0, amount_tolerance_pct: float = 0.0, date_window_days: int = 7, start_date: date | None = None, end_date: date | None = None, active: bool = True, note: str = "")`
  - `Transaction(id: int | None, date: date, amount_cents: int, description: str, category_id: int | None = None, counterparty: str = "", import_id: int | None = None, fingerprint: str | None = None, balance_after_cents: int | None = None, note: str = "")`
  - `BalanceCheckpoint(date: date, balance_cents: int, source: str)` — `source ∈ {"manual","import"}`
- Produces (`recurrence.py`):
  - `validate_rule(rule: Rule) -> None` — `ValueError` (poruka počinje s `Neispravno pravilo:`) za: nepoznat `type`/`shift`, `day` izvan 1–31, `n` < 1 ili > 23, `every` < 1, `weekly` bez `anchor`, `month` izvan 1–12, `yearly` dan koji ne postoji ni u prijestupnoj godini (npr. 30.2.)
  - `rule_to_dict(rule: Rule) -> dict` / `rule_from_dict(d: dict) -> Rule` (izostavlja `None` polja; `anchor` kao ISO tekst)
  - `parse_rule_spec(text: str, shift: str = "none") -> Rule` — skraćeni zapis iz spec 7.1: `monthly_day:5`, `last_workday`, `nth_workday:1`, `weekly:2:2026-01-09`, `yearly:3-14`; poziva `validate_rule`
  - `describe_rule(rule: Rule) -> str` — hrvatski opis, npr. `svakog 5. u mjesecu (pomak na sljedeći radni dan)`, `zadnji radni dan u mjesecu`, `svaka 2 tjedna od 09.01.2026.`, `svake godine 14.3.`
  - `occurrences(rule: Rule, start: date, end: date) -> list[Occurrence]` — sortirano; uključuje pojavljivanja čiji je **`due`** u `[start, end]` (oba uključena)
  - `item_occurrences(item: RecurringItem, start: date, end: date) -> list[Occurrence]` — kao gore, ali odbacuje pojavljivanja čiji je `nominal` prije `item.start_date` ili poslije `item.end_date`; neaktivna stavka → `[]`

Semantika: `monthly_day` reže dan na kraj mjeseca (31 → 28.2.); `yearly` 29.2. → 28.2. u neprijestupnoj; `last_workday`/`nth_workday` ignoriraju `shift`; `weekly` daje `anchor + k·every·7` za k ≥ 0. Pomak se primjenjuje nakon izračuna nominalnog datuma. Da bi pomak preko granice raspona bio ispravan, nominalne datume generiraj za raspon proširen za 7 dana na obje strane, pa filtriraj po `due`.

- [ ] **Step 1: Napiši testove koji padaju**

```python
from datetime import date as d
import pytest
from financije.core.models import Rule, Occurrence, RecurringItem
from financije.core.recurrence import (occurrences, item_occurrences, parse_rule_spec,
    rule_to_dict, rule_from_dict, validate_rule, describe_rule)

def dues(rule, a, b): return [o.due for o in occurrences(rule, a, b)]

def test_monthly_day_clamps_short_months():
    assert dues(Rule("monthly_day", day=31), d(2026,1,1), d(2026,4,30)) == [d(2026,1,31), d(2026,2,28), d(2026,3,31), d(2026,4,30)]
    assert dues(Rule("monthly_day", day=31), d(2028,2,1), d(2028,2,29)) == [d(2028,2,29)]

def test_monthly_day_shift():
    assert occurrences(Rule("monthly_day", day=5, shift="next_workday"), d(2026,12,1), d(2026,12,31)) == [Occurrence(d(2026,12,5), d(2026,12,7))]
    assert dues(Rule("monthly_day", day=25, shift="next_workday"), d(2026,12,1), d(2026,12,31)) == [d(2026,12,28)]
    assert dues(Rule("monthly_day", day=25, shift="prev_workday"), d(2026,12,1), d(2026,12,31)) == [d(2026,12,24)]
    assert dues(Rule("monthly_day", day=5), d(2026,12,1), d(2026,12,31)) == [d(2026,12,5)]

def test_shift_across_range_boundary():
    # 31.10.2026. je subota → pomak na 2.11.
    r = Rule("monthly_day", day=31, shift="next_workday")
    assert dues(r, d(2026,10,1), d(2026,10,31)) == []
    assert d(2026,11,2) in dues(r, d(2026,11,1), d(2026,11,30))

def test_last_workday():
    r = Rule("last_workday")
    assert dues(r, d(2026,5,1), d(2026,5,31)) == [d(2026,5,29)]      # 30.5. subota i praznik, 31.5. nedjelja
    assert dues(r, d(2026,11,1), d(2027,1,31)) == [d(2026,11,30), d(2026,12,31), d(2027,1,29)]

def test_nth_workday_skips_holiday():
    assert dues(Rule("nth_workday", n=1), d(2027,1,1), d(2027,1,31)) == [d(2027,1,4)]

def test_weekly():
    r = Rule("weekly", every=2, anchor=d(2026,1,9))
    assert dues(r, d(2026,1,1), d(2026,2,28)) == [d(2026,1,9), d(2026,1,23), d(2026,2,6), d(2026,2,20)]
    assert dues(r, d(2025,12,1), d(2025,12,31)) == []

def test_yearly_feb_29():
    r = Rule("yearly", month=2, day=29)
    assert dues(r, d(2027,1,1), d(2027,12,31)) == [d(2027,2,28)]
    assert dues(r, d(2028,1,1), d(2028,12,31)) == [d(2028,2,29)]

def test_item_occurrences_respects_period_and_active():
    item = RecurringItem(None, "Netflix", -1199, Rule("monthly_day", day=15),
                         start_date=d(2026,10,1), end_date=d(2026,12,31))
    got = [o.nominal for o in item_occurrences(item, d(2026,9,1), d(2027,2,28))]
    assert got == [d(2026,10,15), d(2026,11,15), d(2026,12,15)]
    item.active = False
    assert item_occurrences(item, d(2026,9,1), d(2027,2,28)) == []

@pytest.mark.parametrize("spec,rule", [
    ("monthly_day:5", Rule("monthly_day", day=5)),
    ("last_workday", Rule("last_workday")),
    ("nth_workday:1", Rule("nth_workday", n=1)),
    ("weekly:2:2026-01-09", Rule("weekly", every=2, anchor=d(2026,1,9))),
    ("yearly:3-14", Rule("yearly", month=3, day=14)),
])
def test_parse_rule_spec(spec, rule):
    assert parse_rule_spec(spec) == rule
    assert rule_from_dict(rule_to_dict(rule)) == rule

@pytest.mark.parametrize("bad", ["monthly_day:0", "monthly_day:32", "weekly:0:2026-01-09", "weekly:2", "yearly:2-30", "yearly:13-1", "daily", "monthly_day:x"])
def test_parse_rule_spec_rejects(bad):
    with pytest.raises(ValueError):
        parse_rule_spec(bad)

def test_describe_rule():
    assert describe_rule(Rule("last_workday")) == "zadnji radni dan u mjesecu"
    assert describe_rule(Rule("monthly_day", day=5, shift="next_workday")) == "svakog 5. u mjesecu (pomak na sljedeći radni dan)"
```

- [ ] **Step 2: Pokreni — mora pasti**

Run: `.venv/bin/pytest tests/test_recurrence.py -q` → FAIL (moduli ne postoje)

- [ ] **Step 3: Implementiraj `models.py` i `recurrence.py` prema Interfaces**

- [ ] **Step 4: Pokreni — mora proći**

Run: `.venv/bin/pytest -q` → PASS

- [ ] **Step 5: Commit**

```bash
git add financije/core/models.py financije/core/recurrence.py tests/test_recurrence.py
git commit -m "Pravila ponavljanja s pomakom na radni dan"
```

### Task 4: SQLite pohrana (`storage`) — završava M1

**Files:**
- Create: `financije/core/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `models` (Task 3), `rule_to_dict`/`rule_from_dict` (Task 3)
- Produces:
  - `default_db_path() -> Path` — `FINANCIJE_DB` ako je postavljen, inače `~/.financije/financije.db`
  - `class Storage:` `__init__(self, path: str | Path)` (stvara roditeljsku mapu i shemu ako ne postoje; `PRAGMA foreign_keys = ON`), `close()`, podrška za `with`
  - Kategorije: `list_categories() -> list[Category]`, `get_category_by_name(name: str) -> Category | None` (bez razlike velikih/malih slova), `add_category(name: str, kind: str) -> Category`
  - Ponavljajuće: `add_recurring(item: RecurringItem) -> RecurringItem` (vraća s `id`), `update_recurring(item: RecurringItem) -> None`, `delete_recurring(item_id: int) -> None` (`KeyError` ako ne postoji), `get_recurring(item_id: int) -> RecurringItem` (`KeyError`), `list_recurring(active_only: bool = False) -> list[RecurringItem]` (po `id`)
  - Transakcije: `add_transaction(tx: Transaction) -> Transaction`, `list_transactions(start: date | None = None, end: date | None = None) -> list[Transaction]` (po datumu pa `id`, granice uključive), `delete_transaction(tx_id: int) -> None` (`KeyError`)
  - Stanja: `add_checkpoint(cp: BalanceCheckpoint) -> None` (isti datum → zamjena), `latest_checkpoint() -> BalanceCheckpoint | None`

Shema v1 (`meta.schema_version = '1'`) stvara **sve** tablice iz spec 6.1 (`category`, `recurring_item`, `transaction` — u SQL-u navodnici jer je ključna riječ, `import_batch`, `balance_checkpoint`, `occurrence_link`, `category_rule`, `meta`) da kasniji milestonei ne trebaju migraciju. Datumi kao ISO tekst, pravilo kao JSON u `rule_json`, `transaction.fingerprint UNIQUE`. Pri stvaranju nove baze dodaj zadane kategorije: Plaća (income), Stanovanje, Režije, Pretplate (fixed), Hrana, Gorivo, Izlasci (variable), Ostalo, Nerazvrstano (other).

- [ ] **Step 1: Napiši testove koji padaju**

```python
from datetime import date as d
import pytest
from financije.core.models import Rule, RecurringItem, Transaction, BalanceCheckpoint
from financije.core.storage import Storage, default_db_path

@pytest.fixture
def db(tmp_path):
    with Storage(tmp_path / "sub" / "t.db") as s:
        yield s

def test_default_categories_seeded_once(tmp_path):
    p = tmp_path / "t.db"
    Storage(p).close()
    with Storage(p) as s:
        names = [c.name for c in s.list_categories()]
    assert names.count("Hrana") == 1 and len(names) == 9

def test_category_lookup_case_insensitive(db):
    assert db.get_category_by_name("hrana").kind == "variable"
    assert db.get_category_by_name("nema") is None

def test_recurring_roundtrip(db):
    cat = db.get_category_by_name("Stanovanje")
    item = db.add_recurring(RecurringItem(None, "Najam", -40000,
        Rule("monthly_day", day=5, shift="next_workday"), category_id=cat.id,
        match_pattern="NAJAM", start_date=d(2026,1,1)))
    assert item.id is not None
    assert db.get_recurring(item.id) == item
    item.amount_cents = -42000; item.active = False
    db.update_recurring(item)
    assert db.get_recurring(item.id).amount_cents == -42000
    assert db.list_recurring(active_only=True) == []
    db.delete_recurring(item.id)
    with pytest.raises(KeyError):
        db.get_recurring(item.id)

def test_transactions_filtered_by_date(db):
    for day, amt in [(1, -100), (15, -200), (31, -300)]:
        db.add_transaction(Transaction(None, d(2026,12,day), amt, "x"))
    got = db.list_transactions(d(2026,12,1), d(2026,12,15))
    assert [t.amount_cents for t in got] == [-100, -200]

def test_latest_checkpoint(db):
    assert db.latest_checkpoint() is None
    db.add_checkpoint(BalanceCheckpoint(d(2026,11,1), 10000, "manual"))
    db.add_checkpoint(BalanceCheckpoint(d(2026,11,27), 124000, "manual"))
    db.add_checkpoint(BalanceCheckpoint(d(2026,11,27), 125000, "manual"))
    assert db.latest_checkpoint() == BalanceCheckpoint(d(2026,11,27), 125000, "manual")

def test_default_db_path_env(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCIJE_DB", str(tmp_path / "x.db"))
    assert default_db_path() == tmp_path / "x.db"
```

- [ ] **Step 2: Pokreni — mora pasti**

Run: `.venv/bin/pytest tests/test_storage.py -q` → FAIL

- [ ] **Step 3: Implementiraj `financije/core/storage.py` prema Interfaces**

- [ ] **Step 4: Pokreni sve testove**

Run: `.venv/bin/pytest -q` → PASS (svi)

- [ ] **Step 5: Commit (kraj M1)**

```bash
git add financije/core/storage.py tests/test_storage.py
git commit -m "M1: SQLite pohrana kategorija, ponavljajućih stavki, transakcija i stanja"
```

---

## M2 — Osnovna projekcija i terminalsko sučelje

### Task 5: Projekcija stanja (`projection`)

**Files:**
- Create: `financije/core/projection.py`
- Test: `tests/test_projection.py`

**Interfaces:**
- Consumes: `item_occurrences` (Task 3), `RecurringItem`, `Transaction` (Task 3), `last_day_of_month` (Task 2)
- Produces:
  - `ProjectionEntry(date: date, amount_cents: int, label: str, kind: str)` — `kind ∈ {"recurring","one_off"}` (M5 dodaje `"overdue"`, `"variable"`)
  - `ProjectionDay(date: date, balance_cents: int, entries: list[ProjectionEntry])`
  - `Projection(start_date: date, start_balance_cents: int, end_date: date, days: list[ProjectionDay], month_ends: list[tuple[date, int]], min_balance_cents: int, min_date: date)`
  - `project(start_date: date, start_balance_cents: int, end_date: date, items: list[RecurringItem], transactions: list[Transaction]) -> Projection`

Semantika (spec 6.7, slučaj bez izvoda): stanje na `start_date` već uključuje sve s tog dana. `days` ima jedan zapis za **svaki** dan od `start_date + 1` do `end_date` (i dane bez stavki). U njih ulaze pojavljivanja ponavljajućih stavki s `due` u `(start_date, end_date]` (oznaka = ime stavke) i transakcije s datumom u istom rasponu (`one_off`, oznaka = opis). Unutar dana: prvo `recurring` po imenu, pa `one_off`. `month_ends`: stanje na zadnji dan svakog mjeseca koji je ≤ `end_date`. `min_*`: najmanje stanje među `days` (prvi takav dan); ako je `days` prazan, `start_balance_cents` i `start_date`. `end_date < start_date` → `ValueError`.

- [ ] **Step 1: Napiši testove koji padaju (ručno izračunati primjer)**

```python
from datetime import date as d
import pytest
from financije.core.models import Rule, RecurringItem, Transaction
from financije.core.projection import project

ITEMS = [
    RecurringItem(1, "Plaća", 150000, Rule("last_workday")),
    RecurringItem(2, "Najam", -40000, Rule("monthly_day", day=5, shift="next_workday")),
    RecurringItem(3, "Netflix", -1199, Rule("monthly_day", day=15)),
]

def test_hand_computed_example():
    # Ručni izračun (stanje 500,00 € na 27.11.2026.):
    # 30.11. Plaća +1500,00 → 2000,00 | 7.12. Najam (5.12. subota) → 1600,00
    # 15.12. Netflix → 1588,01 | 20.12. Poklon −120,00 → 1468,01 | 31.12. Plaća → 2968,01
    # 5.1. Najam → 2568,01 | 15.1. Netflix → 2556,02 | 29.1. Plaća (31.1. nedjelja) → 4056,02
    tx = [Transaction(None, d(2026,12,20), -12000, "Poklon"),
          Transaction(None, d(2026,11,27), -999, "Već u stanju")]
    p = project(d(2026,11,27), 50000, d(2027,1,31), ITEMS, tx)
    assert len(p.days) == 65
    assert p.days[0].date == d(2026,11,28) and p.days[-1].date == d(2027,1,31)
    assert p.month_ends == [(d(2026,11,30), 200000), (d(2026,12,31), 296801), (d(2027,1,31), 405602)]
    by_date = {day.date: day for day in p.days}
    assert [e.label for e in by_date[d(2026,12,7)].entries] == ["Najam"]
    assert by_date[d(2026,12,20)].entries[0].kind == "one_off"
    assert (p.min_balance_cents, p.min_date) == (50000, d(2026,11,28))

def test_minimum_goes_negative():
    p = project(d(2026,12,1), 30000, d(2026,12,31), ITEMS[:2], [])
    assert (p.min_balance_cents, p.min_date) == (-10000, d(2026,12,7))
    assert p.month_ends == [(d(2026,12,31), 140000)]

def test_empty_range_and_invalid():
    p = project(d(2026,12,1), 30000, d(2026,12,1), ITEMS, [])
    assert p.days == [] and (p.min_balance_cents, p.min_date) == (30000, d(2026,12,1))
    with pytest.raises(ValueError):
        project(d(2026,12,2), 0, d(2026,12,1), ITEMS, [])
```

- [ ] **Step 2: Pokreni — mora pasti**

Run: `.venv/bin/pytest tests/test_projection.py -q` → FAIL

- [ ] **Step 3: Implementiraj `financije/core/projection.py` prema Interfaces**

- [ ] **Step 4: Pokreni sve testove**

Run: `.venv/bin/pytest -q` → PASS

- [ ] **Step 5: Commit**

```bash
git add financije/core/projection.py tests/test_projection.py
git commit -m "Projekcija stanja iz ponavljajućih i planiranih stavki"
```

### Task 6: Terminalsko sučelje `fin` i README — završava M2

**Files:**
- Create: `financije/cli.py`, `tests/test_cli.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: sve iz Task 1–5
- Produces: `app: typer.Typer` (ulazna točka `fin`)

Naredbe (spec 7.1; svaka prima globalnu opciju `--db PATH` na razini `app` callbacka, zadano `default_db_path()`):

| Naredba | Argumenti / opcije | Ispis |
|---|---|---|
| `fin stavka dodaj NAZIV IZNOS` | `--pravilo` (obavezno, skraćeni zapis), `--pomak none\|next\|prev` (zadano `none`), `--kategorija IME`, `--prepoznaj TEKST`, `--od DATUM`, `--do DATUM`, `--napomena` | `Dodana stavka #ID: Najam -400,00 € — svakog 5. u mjesecu (pomak na sljedeći radni dan)` |
| `fin stavka popis` | `--sve` (i neaktivne) | Rich tablica: ID, Naziv, Iznos, Pravilo (`describe_rule`), Kategorija, Sljedeći datum |
| `fin stavka uredi ID` | `--naziv`, `--iznos`, `--pravilo`, `--pomak`, `--kategorija`, `--prepoznaj`, `--aktivna/--neaktivna` | `Stavka #ID ažurirana.` |
| `fin stavka obrisi ID` | — | `Stavka #ID obrisana.` |
| `fin raspored` | `--mjeseci N` (1), `--od DATUM` (danas) | tablica Datum, Naziv, Iznos; uz pomaknute „(očekivano 05.12.)” |
| `fin transakcija dodaj DATUM IZNOS OPIS` | `--kategorija` | `Dodana transakcija #ID.` |
| `fin transakcija popis` | `--od`, `--do` | tablica |
| `fin stanje IZNOS` | `--datum` (danas) | `Stanje na 27.11.2026.: 1.240,00 €` |
| `fin projekcija` | `--mjeseci N` (3), `--stanje IZNOS`, `--od DATUM` (danas) | tablica stanja na kraju mjeseca, popis stavki po datumu, redak `Najniže stanje: X dana DD.MM.YYYY.`, crveno upozorenje `Stanje pada ispod nule!` ako je min < 0 |

Pravila ponašanja:
- `--pomak next|prev` mapira se na `next_workday|prev_workday`.
- Naredbe koje primaju `IZNOS` kao pozicijski argument koriste `context_settings={"ignore_unknown_options": True}` kako bi `-400` i `-35,50` radili.
- Svaka `ValueError`/`KeyError` iz jezgre (neispravan iznos, datum, pravilo, nepostojeći ID, nepostojeća kategorija) → crvena poruka na hrvatskom i `typer.Exit(1)`, nikad traceback. Poruka sadrži neispravnu vrijednost (`Stavka #99 ne postoji.`, `Kategorija 'Nepostoji' ne postoji.`).
- Rich ispis u testovima: konzola bez boja i dovoljno široka (npr. `Console(width=120)`) da se iznosi ne lome u više redaka.
- `fin projekcija`: ako je zadano `--stanje`, kreće od (`--od`, `--stanje`); inače od `latest_checkpoint()`; ako ga nema → `Nema poznatog stanja. Upiši ga s 'fin stanje IZNOS' ili koristi --stanje.` i izlaz 1. Kraj = `add_months(start, mjeseci)`. Transakcije za projekciju: `list_transactions(start + 1 dan, kraj)`.
- Datumi u ispisu `DD.MM.YYYY.`, iznosi `format_amount`.

- [ ] **Step 1: Napiši testove koji padaju**

```python
import pytest
from typer.testing import CliRunner
from financije.cli import app

runner = CliRunner()

@pytest.fixture
def run(tmp_path):
    db = str(tmp_path / "cli.db")
    def _run(*args):
        return runner.invoke(app, ["--db", db, *args])
    return _run

def test_add_list_and_negative_amount(run):
    r = run("stavka", "dodaj", "Najam", "-400", "--pravilo", "monthly_day:5", "--pomak", "next", "--kategorija", "Stanovanje")
    assert r.exit_code == 0, r.output
    assert "-400,00 €" in r.output
    r = run("stavka", "popis")
    assert "Najam" in r.output and "svakog 5. u mjesecu" in r.output

def test_projection_from_explicit_balance(run):
    run("stavka", "dodaj", "Plaća", "1500", "--pravilo", "last_workday")
    run("stavka", "dodaj", "Najam", "-400", "--pravilo", "monthly_day:5", "--pomak", "next")
    run("transakcija", "dodaj", "20.12.2026.", "-120", "Poklon")
    r = run("projekcija", "--stanje", "500", "--od", "2026-11-27", "--mjeseci", "2")
    assert r.exit_code == 0, r.output
    assert "2.000,00 €" in r.output      # kraj studenog
    assert "Najniže stanje" in r.output

def test_projection_uses_checkpoint(run):
    run("stanje", "300", "--datum", "2026-12-01")
    run("stavka", "dodaj", "Najam", "-400", "--pravilo", "monthly_day:5", "--pomak", "next")
    r = run("projekcija", "--mjeseci", "1")
    assert r.exit_code == 0, r.output
    assert "-100,00 €" in r.output and "ispod nule" in r.output

def test_projection_without_balance_is_friendly(run):
    r = run("projekcija")
    assert r.exit_code == 1
    assert "Nema poznatog stanja" in r.output
    assert "Traceback" not in r.output

@pytest.mark.parametrize("args,msg", [
    (("stavka", "dodaj", "X", "abc", "--pravilo", "last_workday"), "Neispravan iznos"),
    (("stavka", "dodaj", "X", "10", "--pravilo", "monthly_day:40"), "pravilo"),
    (("stavka", "obrisi", "99"), "99"),
    (("stavka", "dodaj", "X", "10", "--pravilo", "last_workday", "--kategorija", "Nepostoji"), "Nepostoji"),
])
def test_errors_are_friendly(run, args, msg):
    r = run(*args)
    assert r.exit_code == 1 and msg.lower() in r.output.lower()
```

- [ ] **Step 2: Pokreni — mora pasti**

Run: `.venv/bin/pytest tests/test_cli.py -q` → FAIL

- [ ] **Step 3: Implementiraj `financije/cli.py` prema tablici i pravilima ponašanja**

Ako `ignore_unknown_options` ne propušta `-400` kao pozicijski argument u instaliranoj verziji Clicka, isprobaj i dokumentiraj alternativu (npr. `IZNOS` kao `str` argument uz `allow_interspersed_args=False`) — test `test_add_list_and_negative_amount` je presudan.

- [ ] **Step 4: Pokreni sve testove i ručno provjeri**

Run: `.venv/bin/pytest -q` → PASS (svi)
Run: `FINANCIJE_DB=/tmp/fin-demo.db .venv/bin/fin stavka dodaj Plaća 1500 --pravilo last_workday && FINANCIJE_DB=/tmp/fin-demo.db .venv/bin/fin projekcija --stanje 500` → tablica i redak „Najniže stanje”.

- [ ] **Step 5: README**

Zamijeni `README.md`: jedan odlomak o svrsi (očekivano → izvod → usklađivanje → projekcija), instalacija (`python3 -m venv .venv`, `.venv/bin/pip install -e '.[dev]'`), primjeri naredbi iz tablice iznad, pokretanje testova (`.venv/bin/pytest`), stanje po milestoneima (M1, M2 gotovi; M3–M7 planirani, s linkom na spec).

- [ ] **Step 6: Commit (kraj M2)**

```bash
git add financije/cli.py tests/test_cli.py README.md
git commit -m "M2: terminalsko sučelje fin (stavke, raspored, stanje, projekcija)"
```
