"""Terminalsko sučelje `fin`: tanki sloj iznad jezgre (financije.core)."""

from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from .core.calendar_hr import add_months, month_name, parse_date
from .core.models import BalanceCheckpoint, RecurringItem, Transaction
from .core.money import format_amount, parse_amount
from .core.projection import project
from .core.recurrence import describe_rule, item_occurrences, parse_rule_spec
from .core.storage import Storage, default_db_path

app = typer.Typer(help="Osobne financije: očekivane stavke i projekcija stanja.",
                  no_args_is_help=True, add_completion=False)
stavka_app = typer.Typer(help="Ponavljajuće stavke (plaća, najam, pretplate...).", no_args_is_help=True)
transakcija_app = typer.Typer(help="Jednokratne stavke i transakcije.", no_args_is_help=True)
app.add_typer(stavka_app, name="stavka")
app.add_typer(transakcija_app, name="transakcija")

# Naredbe koje primaju iznos kao argument: bez ovoga bi se "-400" čitao kao opcija.
NEG = {"ignore_unknown_options": True}

_SHIFTS = {"none": "none", "next": "next_workday", "prev": "prev_workday"}


def out() -> Console:
    return Console(highlight=False)


def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y.")


@contextmanager
def friendly_errors():
    """Greške iz jezgre prikazuje kao poruku na hrvatskom umjesto tracebacka."""
    try:
        yield
    except (ValueError, KeyError) as e:
        message = e.args[0] if e.args else str(e)
        out().print(f"[red]Greška:[/red] {escape(str(message))}")
        raise typer.Exit(1) from None


@contextmanager
def open_db(ctx: typer.Context):
    with friendly_errors(), Storage(ctx.obj["db"]) as db:
        yield db


def parse_shift(text: str) -> str:
    if text not in _SHIFTS:
        raise ValueError(f"Neispravan pomak: '{text}' (dopušteno: none, next, prev)")
    return _SHIFTS[text]


def category_id(db: Storage, name: str | None) -> int | None:
    if name is None:
        return None
    cat = db.get_category_by_name(name)
    if cat is None:
        known = ", ".join(c.name for c in db.list_categories())
        raise ValueError(f"Kategorija '{name}' ne postoji. Postojeće: {known}")
    return cat.id


def optional_date(text: str | None, default: date | None = None) -> date | None:
    return parse_date(text) if text else default


@app.callback()
def main(
    ctx: typer.Context,
    db: Path = typer.Option(None, "--db", help="Putanja do baze (zadano: FINANCIJE_DB ili ~/.financije/financije.db)."),
):
    ctx.obj = {"db": db or default_db_path()}


# --- ponavljajuće stavke ----------------------------------------------------

@stavka_app.command("dodaj", context_settings=NEG)
def stavka_dodaj(
    ctx: typer.Context,
    naziv: str = typer.Argument(..., help="Naziv stavke, npr. Najam."),
    iznos: str = typer.Argument(..., help="Iznos: prihod pozitivan, trošak negativan (npr. -400 ili -11,99)."),
    pravilo: str = typer.Option(..., help="monthly_day:5 | last_workday | nth_workday:1 | weekly:2:2026-01-09 | yearly:3-14"),
    pomak: str = typer.Option("none", help="Ako datum padne na neradni dan: none | next | prev."),
    kategorija: str = typer.Option(None, help="Ime kategorije."),
    prepoznaj: str = typer.Option("", help="Tekst po kojem se stavka prepoznaje u izvodu."),
    od: str = typer.Option(None, help="Vrijedi od datuma."),
    do: str = typer.Option(None, help="Vrijedi do datuma."),
    napomena: str = typer.Option("", help="Bilješka."),
):
    """Dodaj očekivanu ponavljajuću stavku."""
    with open_db(ctx) as db:
        item = db.add_recurring(RecurringItem(
            None, naziv, parse_amount(iznos), parse_rule_spec(pravilo, parse_shift(pomak)),
            category_id=category_id(db, kategorija), match_pattern=prepoznaj,
            start_date=optional_date(od), end_date=optional_date(do), note=napomena,
        ))
        out().print(f"Dodana stavka #{item.id}: {escape(item.name)} {format_amount(item.amount_cents)}"
                    f" — {describe_rule(item.rule)}")


@stavka_app.command("popis")
def stavka_popis(
    ctx: typer.Context,
    sve: bool = typer.Option(False, "--sve", help="Prikaži i neaktivne stavke."),
):
    """Popis ponavljajućih stavki."""
    with open_db(ctx) as db:
        categories = {c.id: c.name for c in db.list_categories()}
        items = db.list_recurring(active_only=not sve)
        if not items:
            out().print("Nema ponavljajućih stavki. Dodaj ih s 'fin stavka dodaj'.")
            return
        today = date.today()
        table = Table(title="Ponavljajuće stavke")
        for col in ("ID", "Naziv", "Iznos", "Pravilo", "Kategorija", "Sljedeći datum"):
            table.add_column(col, justify="right" if col in ("ID", "Iznos") else "left")
        for item in items:
            upcoming = item_occurrences(item, today, add_months(today, 13))
            table.add_row(
                str(item.id),
                escape(item.name) + ("" if item.active else " (neaktivna)"),
                format_amount(item.amount_cents),
                describe_rule(item.rule),
                escape(categories.get(item.category_id, "")),
                fmt_date(upcoming[0].due) if upcoming else "—",
            )
        out().print(table)


@stavka_app.command("uredi", context_settings=NEG)
def stavka_uredi(
    ctx: typer.Context,
    item_id: int = typer.Argument(..., metavar="ID"),
    naziv: str = typer.Option(None),
    iznos: str = typer.Option(None),
    pravilo: str = typer.Option(None),
    pomak: str = typer.Option(None),
    kategorija: str = typer.Option(None),
    prepoznaj: str = typer.Option(None),
    aktivna: bool = typer.Option(None, "--aktivna/--neaktivna"),
):
    """Promijeni postojeću stavku (navedi samo ono što mijenjaš)."""
    with open_db(ctx) as db:
        item = db.get_recurring(item_id)
        if naziv is not None:
            item.name = naziv
        if iznos is not None:
            item.amount_cents = parse_amount(iznos)
        if pravilo is not None or pomak is not None:
            shift = parse_shift(pomak) if pomak is not None else item.rule.shift
            if pravilo is not None:
                item.rule = parse_rule_spec(pravilo, shift)
            else:
                item.rule.shift = shift
        if kategorija is not None:
            item.category_id = category_id(db, kategorija)
        if prepoznaj is not None:
            item.match_pattern = prepoznaj
        if aktivna is not None:
            item.active = aktivna
        db.update_recurring(item)
        out().print(f"Stavka #{item_id} ažurirana.")


@stavka_app.command("obrisi")
def stavka_obrisi(ctx: typer.Context, item_id: int = typer.Argument(..., metavar="ID")):
    """Obriši stavku."""
    with open_db(ctx) as db:
        db.delete_recurring(item_id)
        out().print(f"Stavka #{item_id} obrisana.")


@app.command("raspored")
def raspored(
    ctx: typer.Context,
    mjeseci: int = typer.Option(1, help="Koliko mjeseci unaprijed."),
    od: str = typer.Option(None, help="Od datuma (zadano: danas)."),
):
    """Nadolazeća pojavljivanja ponavljajućih stavki."""
    with open_db(ctx) as db:
        start = optional_date(od, date.today())
        end = add_months(start, mjeseci)
        rows = sorted(
            ((o, item) for item in db.list_recurring(active_only=True)
             for o in item_occurrences(item, start, end)),
            key=lambda pair: (pair[0].due, pair[1].name),
        )
        if not rows:
            out().print("U tom razdoblju nema očekivanih stavki.")
            return
        table = Table(title=f"Raspored {fmt_date(start)} – {fmt_date(end)}")
        table.add_column("Datum")
        table.add_column("Stavka")
        table.add_column("Iznos", justify="right")
        for o, item in rows:
            when = fmt_date(o.due)
            if o.due != o.nominal:
                when += f" (očekivano {o.nominal:%d.%m.})"
            table.add_row(when, escape(item.name), format_amount(item.amount_cents))
        out().print(table)


# --- transakcije ------------------------------------------------------------

@transakcija_app.command("dodaj", context_settings=NEG)
def transakcija_dodaj(
    ctx: typer.Context,
    datum: str = typer.Argument(..., help="Datum, npr. 20.12.2026."),
    iznos: str = typer.Argument(..., help="Iznos (trošak negativan)."),
    opis: str = typer.Argument(..., help="Opis."),
    kategorija: str = typer.Option(None),
):
    """Dodaj jednokratnu stavku (planirani ili već nastali trošak/prihod)."""
    with open_db(ctx) as db:
        tx = db.add_transaction(Transaction(
            None, parse_date(datum), parse_amount(iznos), opis, category_id=category_id(db, kategorija)))
        out().print(f"Dodana transakcija #{tx.id}: {fmt_date(tx.date)} {escape(opis)} {format_amount(tx.amount_cents)}")


@transakcija_app.command("popis")
def transakcija_popis(
    ctx: typer.Context,
    od: str = typer.Option(None),
    do: str = typer.Option(None),
):
    """Popis transakcija."""
    with open_db(ctx) as db:
        categories = {c.id: c.name for c in db.list_categories()}
        txs = db.list_transactions(optional_date(od), optional_date(do))
        if not txs:
            out().print("Nema transakcija.")
            return
        table = Table(title="Transakcije")
        for col in ("ID", "Datum", "Opis", "Iznos", "Kategorija"):
            table.add_column(col, justify="right" if col in ("ID", "Iznos") else "left")
        for t in txs:
            table.add_row(str(t.id), fmt_date(t.date), escape(t.description),
                          format_amount(t.amount_cents), escape(categories.get(t.category_id, "")))
        out().print(table)


@transakcija_app.command("obrisi")
def transakcija_obrisi(ctx: typer.Context, tx_id: int = typer.Argument(..., metavar="ID")):
    """Obriši transakciju."""
    with open_db(ctx) as db:
        db.delete_transaction(tx_id)
        out().print(f"Transakcija #{tx_id} obrisana.")


# --- stanje i projekcija ------------------------------------------------------

@app.command("stanje", context_settings=NEG)
def stanje(
    ctx: typer.Context,
    iznos: str = typer.Argument(None, help="Stvarno stanje računa. Bez iznosa prikazuje zadnje poznato."),
    datum: str = typer.Option(None, help="Na koji dan (zadano: danas)."),
):
    """Upiši ili prikaži stvarno stanje računa."""
    with open_db(ctx) as db:
        if iznos is None:
            cp = db.latest_checkpoint()
            if cp is None:
                out().print("Nema poznatog stanja. Upiši ga s 'fin stanje IZNOS'.")
            else:
                out().print(f"Zadnje poznato stanje na {fmt_date(cp.date)}: {format_amount(cp.balance_cents)}")
            return
        cp = BalanceCheckpoint(optional_date(datum, date.today()), parse_amount(iznos), "manual")
        db.add_checkpoint(cp)
        out().print(f"Stanje na {fmt_date(cp.date)}: {format_amount(cp.balance_cents)}")


@app.command("projekcija", context_settings=NEG)
def projekcija(
    ctx: typer.Context,
    mjeseci: int = typer.Option(3, help="Koliko mjeseci unaprijed."),
    stanje_: str = typer.Option(None, "--stanje", help="Početno stanje (inače zadnje upisano)."),
    od: str = typer.Option(None, help="Datum početnog stanja uz --stanje (zadano: danas)."),
):
    """Projekcija stanja računa za idućih nekoliko mjeseci."""
    with open_db(ctx) as db:
        if mjeseci < 1:
            raise ValueError("Broj mjeseci mora biti barem 1.")
        if stanje_ is not None:
            start, balance = optional_date(od, date.today()), parse_amount(stanje_)
        else:
            cp = db.latest_checkpoint()
            if cp is None:
                raise ValueError("Nema poznatog stanja. Upiši ga s 'fin stanje IZNOS' ili koristi --stanje.")
            start, balance = cp.date, cp.balance_cents
        end = add_months(start, mjeseci)
        p = project(start, balance, end, db.list_recurring(active_only=True),
                    db.list_transactions(start + timedelta(days=1), end))

        console = out()
        console.print(f"Projekcija od {fmt_date(start)} (stanje {format_amount(balance)}) do {fmt_date(end)}")

        events = Table(title="Očekivane promjene")
        events.add_column("Datum")
        events.add_column("Stavka")
        events.add_column("Iznos", justify="right")
        events.add_column("Stanje", justify="right")
        for day in p.days:
            for i, e in enumerate(day.entries):
                last = i == len(day.entries) - 1
                bal = format_amount(day.balance_cents) if last else ""
                if last and day.balance_cents < 0:
                    bal = f"[red]{bal}[/red]"
                label = escape(e.label) + (" (jednokratno)" if e.kind == "one_off" else "")
                events.add_row(fmt_date(day.date) if i == 0 else "", label, format_amount(e.amount_cents), bal)
        if events.row_count:
            console.print(events)
        else:
            console.print("U tom razdoblju nema očekivanih promjena.")

        months = Table(title="Stanje na kraju mjeseca")
        months.add_column("Mjesec")
        months.add_column("Stanje", justify="right")
        for d, bal in p.month_ends:
            months.add_row(f"{month_name(d.month)} {d.year}.", format_amount(bal))
        if p.days and p.days[-1].date not in {d for d, _ in p.month_ends}:
            months.add_row(f"{fmt_date(p.days[-1].date)} (kraj projekcije)",
                           format_amount(p.days[-1].balance_cents))
        console.print(months)

        console.print(f"Najniže stanje: [bold]{format_amount(p.min_balance_cents)}[/bold] dana {fmt_date(p.min_date)}")
        if p.min_balance_cents < 0:
            console.print("[bold red]Upozorenje: stanje pada ispod nule![/bold red]")
