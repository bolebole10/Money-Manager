import pytest
from typer.testing import CliRunner

from financije.cli import app

runner = CliRunner()


@pytest.fixture
def run(tmp_path):
    db = str(tmp_path / "cli.db")

    def _run(*args):
        return runner.invoke(app, ["--db", db, *args], env={"COLUMNS": "150"})
    return _run


def test_add_list_and_negative_amount(run):
    r = run("stavka", "dodaj", "Najam", "-400", "--pravilo", "monthly_day:5", "--pomak", "next",
            "--kategorija", "Stanovanje", "--prepoznaj", "NAJAM")
    assert r.exit_code == 0, r.output
    assert "-400,00 €" in r.output
    r = run("stavka", "popis")
    assert r.exit_code == 0, r.output
    assert "Najam" in r.output and "svakog 5. u mjesecu" in r.output and "Stanovanje" in r.output


def test_decimal_negative_amount(run):
    r = run("stavka", "dodaj", "Netflix", "-11,99", "--pravilo", "monthly_day:15")
    assert r.exit_code == 0, r.output
    assert "-11,99 €" in r.output


def test_edit_and_delete(run):
    run("stavka", "dodaj", "Netflix", "-11,99", "--pravilo", "monthly_day:15")
    r = run("stavka", "uredi", "1", "--iznos", "-13,99", "--neaktivna")
    assert r.exit_code == 0, r.output
    assert "Netflix" not in run("stavka", "popis").output          # neaktivne se ne prikazuju
    r = run("stavka", "popis", "--sve")
    assert "-13,99 €" in r.output
    assert run("stavka", "obrisi", "1").exit_code == 0
    assert "Netflix" not in run("stavka", "popis", "--sve").output


def test_schedule_shows_shifted_dates(run):
    run("stavka", "dodaj", "Najam", "-400", "--pravilo", "monthly_day:5", "--pomak", "next")
    r = run("raspored", "--od", "2026-12-01", "--mjeseci", "1")
    assert r.exit_code == 0, r.output
    assert "07.12.2026." in r.output and "očekivano 05.12." in r.output


def test_transactions(run):
    r = run("transakcija", "dodaj", "20.12.2026.", "-120", "Poklon [mama]")
    assert r.exit_code == 0, r.output
    r = run("transakcija", "popis")
    assert "Poklon [mama]" in r.output and "-120,00 €" in r.output


def test_balance_show_and_set(run):
    assert "Nema" in run("stanje").output
    r = run("stanje", "1.240,00", "--datum", "27.11.2026.")
    assert r.exit_code == 0, r.output
    assert "1.240,00 €" in r.output and "27.11.2026." in r.output
    assert "1.240,00 €" in run("stanje").output


def test_projection_from_explicit_balance(run):
    run("stavka", "dodaj", "Plaća", "1500", "--pravilo", "last_workday")
    run("stavka", "dodaj", "Najam", "-400", "--pravilo", "monthly_day:5", "--pomak", "next")
    run("transakcija", "dodaj", "20.12.2026.", "-120", "Poklon")
    r = run("projekcija", "--stanje", "500", "--od", "2026-11-27", "--mjeseci", "2")
    assert r.exit_code == 0, r.output
    assert "studeni 2026." in r.output and "2.000,00 €" in r.output   # kraj studenog
    assert "Poklon" in r.output
    assert "Najniže stanje" in r.output
    assert "ispod nule" not in r.output


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
    (("stavka", "dodaj", "X", "10", "--pravilo", "monthly_day:40"), "Neispravno pravilo"),
    (("stavka", "dodaj", "X", "10", "--pravilo", "last_workday", "--pomak", "gore"), "pomak"),
    (("stavka", "dodaj", "X", "10", "--pravilo", "last_workday", "--kategorija", "Nepostoji"), "Nepostoji"),
    (("stavka", "obrisi", "99"), "#99"),
    (("stavka", "uredi", "99", "--iznos", "5"), "#99"),
    (("transakcija", "dodaj", "32.12.2026", "-5", "X"), "Neispravan datum"),
    (("projekcija", "--stanje", "100", "--mjeseci", "0"), "mjeseci"),
])
def test_errors_are_friendly(run, args, msg):
    r = run(*args)
    assert r.exit_code == 1, r.output
    assert msg.lower() in r.output.lower()
    assert "Traceback" not in r.output
