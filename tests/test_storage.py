from datetime import date as d

import pytest

from financije.core.models import BalanceCheckpoint, RecurringItem, Rule, Transaction
from financije.core.storage import Storage, default_db_path


@pytest.fixture
def db(tmp_path):
    with Storage(tmp_path / "sub" / "t.db") as s:   # roditeljska mapa još ne postoji
        yield s


def test_default_categories_seeded_once(tmp_path):
    p = tmp_path / "t.db"
    Storage(p).close()
    with Storage(p) as s:
        names = [c.name for c in s.list_categories()]
    assert names.count("Hrana") == 1
    assert len(names) == 9


def test_category_lookup_and_add(db):
    assert db.get_category_by_name("hrana").kind == "variable"
    assert db.get_category_by_name("nema") is None
    cat = db.add_category("Ljubimci", "variable")
    assert cat.id is not None and db.get_category_by_name("LJUBIMCI") == cat
    with pytest.raises(ValueError):
        db.add_category("Hrana", "variable")      # ime već postoji
    with pytest.raises(ValueError):
        db.add_category("X", "nepoznato")         # nepoznata vrsta


def test_recurring_roundtrip(db):
    cat = db.get_category_by_name("Stanovanje")
    item = db.add_recurring(RecurringItem(
        None, "Najam", -40000, Rule("monthly_day", day=5, shift="next_workday"),
        category_id=cat.id, match_pattern="NAJAM", amount_tolerance_pct=2.5,
        start_date=d(2026, 1, 1), note="stan u Rijeci"))
    assert item.id is not None
    assert db.get_recurring(item.id) == item

    item.amount_cents = -42000
    item.active = False
    item.rule = Rule("weekly", every=2, anchor=d(2026, 1, 9))
    db.update_recurring(item)
    assert db.get_recurring(item.id) == item
    assert db.list_recurring(active_only=True) == []
    assert db.list_recurring() == [item]

    db.delete_recurring(item.id)
    with pytest.raises(KeyError):
        db.get_recurring(item.id)
    with pytest.raises(KeyError):
        db.delete_recurring(item.id)


def test_recurring_rejects_invalid_rule(db):
    with pytest.raises(ValueError, match="Neispravno pravilo"):
        db.add_recurring(RecurringItem(None, "X", -100, Rule("monthly_day", day=40)))


def test_transactions(db):
    for day, amt in [(31, -300), (1, -100), (15, -200)]:
        db.add_transaction(Transaction(None, d(2026, 12, day), amt, "x"))
    got = db.list_transactions(d(2026, 12, 1), d(2026, 12, 15))
    assert [t.amount_cents for t in got] == [-100, -200]
    assert [t.date.day for t in db.list_transactions()] == [1, 15, 31]
    first = got[0]
    db.delete_transaction(first.id)
    assert len(db.list_transactions()) == 2
    with pytest.raises(KeyError):
        db.delete_transaction(first.id)


def test_latest_checkpoint(db):
    assert db.latest_checkpoint() is None
    db.add_checkpoint(BalanceCheckpoint(d(2026, 11, 1), 10000, "manual"))
    db.add_checkpoint(BalanceCheckpoint(d(2026, 11, 27), 124000, "manual"))
    db.add_checkpoint(BalanceCheckpoint(d(2026, 11, 27), 125000, "manual"))   # isti dan -> zamjena
    assert db.latest_checkpoint() == BalanceCheckpoint(d(2026, 11, 27), 125000, "manual")


def test_data_persists_between_openings(tmp_path):
    p = tmp_path / "t.db"
    with Storage(p) as s:
        s.add_transaction(Transaction(None, d(2026, 12, 1), -3550, "Konzum"))
    with Storage(p) as s:
        assert [t.description for t in s.list_transactions()] == ["Konzum"]


def test_default_db_path(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCIJE_DB", str(tmp_path / "x.db"))
    assert default_db_path() == tmp_path / "x.db"
    monkeypatch.delenv("FINANCIJE_DB")
    assert default_db_path().parts[-2:] == (".financije", "financije.db")
