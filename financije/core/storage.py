"""Pohrana podataka u lokalnu SQLite datoteku.

Shema verzije 1 sadrži sve tablice iz dizajna (i one koje koriste tek kasniji
milestonei: uvoz izvoda, usklađivanje, pravila razvrstavanja), kako ne bi
trebala migracija. Datumi se spremaju kao ISO tekst, pravila kao JSON.
"""

import json
import os
import sqlite3
from datetime import date
from pathlib import Path

from .models import (
    CATEGORY_KINDS, BalanceCheckpoint, Category, RecurringItem, Transaction,
)
from .recurrence import rule_from_dict, rule_to_dict, validate_rule

SCHEMA_VERSION = "1"

DEFAULT_CATEGORIES = [
    ("Plaća", "income"),
    ("Stanovanje", "fixed"),
    ("Režije", "fixed"),
    ("Pretplate", "fixed"),
    ("Hrana", "variable"),
    ("Gorivo", "variable"),
    ("Izlasci", "variable"),
    ("Ostalo", "other"),
    ("Nerazvrstano", "other"),
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS category (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('fixed', 'variable', 'income', 'other'))
);
CREATE TABLE IF NOT EXISTS recurring_item (
    id                     INTEGER PRIMARY KEY,
    name                   TEXT NOT NULL,
    amount_cents           INTEGER NOT NULL,
    category_id            INTEGER REFERENCES category(id) ON DELETE SET NULL,
    rule_json              TEXT NOT NULL,
    match_pattern          TEXT NOT NULL DEFAULT '',
    amount_tolerance_cents INTEGER NOT NULL DEFAULT 0,
    amount_tolerance_pct   REAL NOT NULL DEFAULT 0,
    date_window_days       INTEGER NOT NULL DEFAULT 7,
    start_date             TEXT,
    end_date               TEXT,
    active                 INTEGER NOT NULL DEFAULT 1,
    note                   TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS import_batch (
    id                    INTEGER PRIMARY KEY,
    file_name             TEXT NOT NULL,
    imported_at           TEXT NOT NULL,
    period_from           TEXT,
    period_to             TEXT,
    closing_balance_cents INTEGER,
    closing_balance_date  TEXT
);
CREATE TABLE IF NOT EXISTS "transaction" (
    id                  INTEGER PRIMARY KEY,
    date                TEXT NOT NULL,
    amount_cents        INTEGER NOT NULL,
    description         TEXT NOT NULL,
    counterparty        TEXT NOT NULL DEFAULT '',
    category_id         INTEGER REFERENCES category(id) ON DELETE SET NULL,
    import_id           INTEGER REFERENCES import_batch(id) ON DELETE CASCADE,
    fingerprint         TEXT UNIQUE,
    balance_after_cents INTEGER,
    note                TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_transaction_date ON "transaction"(date);
CREATE TABLE IF NOT EXISTS balance_checkpoint (
    date          TEXT PRIMARY KEY,
    balance_cents INTEGER NOT NULL,
    source        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS occurrence_link (
    recurring_item_id INTEGER NOT NULL REFERENCES recurring_item(id) ON DELETE CASCADE,
    due_date          TEXT NOT NULL,
    transaction_id    INTEGER REFERENCES "transaction"(id) ON DELETE CASCADE,
    status            TEXT NOT NULL CHECK (status IN ('matched', 'skipped')),
    confirmed_by_user INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (recurring_item_id, due_date)
);
CREATE TABLE IF NOT EXISTS category_rule (
    id          INTEGER PRIMARY KEY,
    pattern     TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES category(id) ON DELETE CASCADE,
    priority    INTEGER NOT NULL DEFAULT 0
);
"""


def default_db_path() -> Path:
    """Putanja baze: varijabla FINANCIJE_DB ili ~/.financije/financije.db."""
    env = os.environ.get("FINANCIJE_DB")
    if env:
        return Path(env)
    return Path.home() / ".financije" / "financije.db"


def _d(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


class Storage:
    """Pristup bazi. Koristi se kao `with Storage(path) as db: ...`."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(_SCHEMA)
            row = self.conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            if row is None:
                self.conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
                self.conn.executemany("INSERT INTO category (name, kind) VALUES (?, ?)", DEFAULT_CATEGORIES)

    # --- kategorije -------------------------------------------------------

    def list_categories(self) -> list[Category]:
        rows = self.conn.execute("SELECT id, name, kind FROM category ORDER BY id").fetchall()
        return [Category(r["id"], r["name"], r["kind"]) for r in rows]

    def get_category_by_name(self, name: str) -> Category | None:
        # Usporedba u Pythonu jer SQLite NOCASE ne zna za č, ć, š, ž, đ.
        wanted = name.strip().casefold()
        return next((c for c in self.list_categories() if c.name.casefold() == wanted), None)

    def add_category(self, name: str, kind: str) -> Category:
        if kind not in CATEGORY_KINDS:
            raise ValueError(f"Nepoznata vrsta kategorije: '{kind}'")
        if self.get_category_by_name(name):
            raise ValueError(f"Kategorija '{name}' već postoji.")
        with self.conn:
            cur = self.conn.execute("INSERT INTO category (name, kind) VALUES (?, ?)", (name.strip(), kind))
        return Category(cur.lastrowid, name.strip(), kind)

    # --- ponavljajuće stavke ----------------------------------------------

    def _recurring_params(self, item: RecurringItem) -> tuple:
        validate_rule(item.rule)
        return (
            item.name, item.amount_cents, item.category_id, json.dumps(rule_to_dict(item.rule)),
            item.match_pattern, item.amount_tolerance_cents, item.amount_tolerance_pct,
            item.date_window_days, _iso(item.start_date), _iso(item.end_date),
            int(item.active), item.note,
        )

    def add_recurring(self, item: RecurringItem) -> RecurringItem:
        with self.conn:
            cur = self.conn.execute(
                """INSERT INTO recurring_item (name, amount_cents, category_id, rule_json,
                       match_pattern, amount_tolerance_cents, amount_tolerance_pct,
                       date_window_days, start_date, end_date, active, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                self._recurring_params(item),
            )
        item.id = cur.lastrowid
        return item

    def update_recurring(self, item: RecurringItem) -> None:
        with self.conn:
            cur = self.conn.execute(
                """UPDATE recurring_item SET name = ?, amount_cents = ?, category_id = ?,
                       rule_json = ?, match_pattern = ?, amount_tolerance_cents = ?,
                       amount_tolerance_pct = ?, date_window_days = ?, start_date = ?,
                       end_date = ?, active = ?, note = ?
                   WHERE id = ?""",
                (*self._recurring_params(item), item.id),
            )
        if cur.rowcount == 0:
            raise KeyError(f"Stavka #{item.id} ne postoji.")

    def delete_recurring(self, item_id: int) -> None:
        with self.conn:
            cur = self.conn.execute("DELETE FROM recurring_item WHERE id = ?", (item_id,))
        if cur.rowcount == 0:
            raise KeyError(f"Stavka #{item_id} ne postoji.")

    def get_recurring(self, item_id: int) -> RecurringItem:
        row = self.conn.execute("SELECT * FROM recurring_item WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise KeyError(f"Stavka #{item_id} ne postoji.")
        return self._row_to_recurring(row)

    def list_recurring(self, active_only: bool = False) -> list[RecurringItem]:
        sql = "SELECT * FROM recurring_item"
        if active_only:
            sql += " WHERE active = 1"
        rows = self.conn.execute(sql + " ORDER BY id").fetchall()
        return [self._row_to_recurring(r) for r in rows]

    @staticmethod
    def _row_to_recurring(r: sqlite3.Row) -> RecurringItem:
        return RecurringItem(
            id=r["id"], name=r["name"], amount_cents=r["amount_cents"],
            rule=rule_from_dict(json.loads(r["rule_json"])), category_id=r["category_id"],
            match_pattern=r["match_pattern"], amount_tolerance_cents=r["amount_tolerance_cents"],
            amount_tolerance_pct=r["amount_tolerance_pct"], date_window_days=r["date_window_days"],
            start_date=_d(r["start_date"]), end_date=_d(r["end_date"]),
            active=bool(r["active"]), note=r["note"],
        )

    # --- transakcije --------------------------------------------------------

    def add_transaction(self, tx: Transaction) -> Transaction:
        with self.conn:
            cur = self.conn.execute(
                """INSERT INTO "transaction" (date, amount_cents, description, counterparty,
                       category_id, import_id, fingerprint, balance_after_cents, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (tx.date.isoformat(), tx.amount_cents, tx.description, tx.counterparty,
                 tx.category_id, tx.import_id, tx.fingerprint, tx.balance_after_cents, tx.note),
            )
        tx.id = cur.lastrowid
        return tx

    def list_transactions(self, start: date | None = None, end: date | None = None) -> list[Transaction]:
        sql, params = 'SELECT * FROM "transaction" WHERE 1 = 1', []
        if start:
            sql += " AND date >= ?"
            params.append(start.isoformat())
        if end:
            sql += " AND date <= ?"
            params.append(end.isoformat())
        rows = self.conn.execute(sql + " ORDER BY date, id", params).fetchall()
        return [
            Transaction(
                id=r["id"], date=date.fromisoformat(r["date"]), amount_cents=r["amount_cents"],
                description=r["description"], category_id=r["category_id"],
                counterparty=r["counterparty"], import_id=r["import_id"],
                fingerprint=r["fingerprint"], balance_after_cents=r["balance_after_cents"],
                note=r["note"],
            )
            for r in rows
        ]

    def delete_transaction(self, tx_id: int) -> None:
        with self.conn:
            cur = self.conn.execute('DELETE FROM "transaction" WHERE id = ?', (tx_id,))
        if cur.rowcount == 0:
            raise KeyError(f"Transakcija #{tx_id} ne postoji.")

    # --- poznata stanja računa ----------------------------------------------

    def add_checkpoint(self, cp: BalanceCheckpoint) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO balance_checkpoint (date, balance_cents, source) VALUES (?, ?, ?)",
                (cp.date.isoformat(), cp.balance_cents, cp.source),
            )

    def latest_checkpoint(self) -> BalanceCheckpoint | None:
        r = self.conn.execute(
            "SELECT * FROM balance_checkpoint ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if r is None:
            return None
        return BalanceCheckpoint(date.fromisoformat(r["date"]), r["balance_cents"], r["source"])
