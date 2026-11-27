import pytest

from financije.core.money import format_amount, parse_amount


@pytest.mark.parametrize("text,cents", [
    ("1.234,56", 123456), ("-35,50", -3550), ("12", 1200), ("1.234,56 €", 123456),
    ("1234.56", 123456), ("-0,99", -99), ("1.234", 123400), ("+1500", 150000),
    (" 11,99 EUR ", 1199), ("1.000.000,00", 100000000), ("12,5", 1250),
])
def test_parse_amount(text, cents):
    assert parse_amount(text) == cents


@pytest.mark.parametrize("bad", ["", "abc", "1,2,3", "12,345", "--5", "1.23.4", "€"])
def test_parse_amount_rejects(bad):
    with pytest.raises(ValueError, match="Neispravan iznos"):
        parse_amount(bad)


@pytest.mark.parametrize("cents,text", [
    (123456, "1.234,56 €"), (-3550, "-35,50 €"), (0, "0,00 €"), (-99, "-0,99 €"),
    (100000000, "1.000.000,00 €"),
])
def test_format_amount(cents, text):
    assert format_amount(cents) == text
