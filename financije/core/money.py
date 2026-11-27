"""Iznosi u centima: parsiranje hrvatskog zapisa i formatiranje za prikaz.

Svi iznosi u aplikaciji su cijeli brojevi centi (int), da se izbjegnu
pogreške zaokruživanja s float brojevima. Prihodi su pozitivni, troškovi negativni.
"""

import re

_INT_GROUPED = r"\d{1,3}(?:\.\d{3})+"   # 1.234 ili 1.000.000
_INT_PLAIN = r"\d+"


def parse_amount(text: str) -> int:
    """Pretvara zapis poput '1.234,56 €', '-35,50' ili '1234.56' u cente.

    Pravila:
    - zarez je decimalni separator (najviše 2 znamenke), točke su tisućice;
    - bez zareza: točka iza koje su 1-2 znamenke je decimalna, inače su točke tisućice;
    - dopušten je jedan predznak (+/-) i oznaka valute (€, EUR).
    """
    original = text
    s = text.strip().upper().replace("EUR", "").replace("€", "").replace(" ", "")
    sign = 1
    if s[:1] in "+-" and s:
        sign = -1 if s[0] == "-" else 1
        s = s[1:]

    whole: str
    frac = ""
    if "," in s:
        if s.count(",") != 1:
            raise _invalid(original)
        whole, frac = s.split(",")
        if not 1 <= len(frac) <= 2 or not frac.isdigit():
            raise _invalid(original)
    else:
        m = re.fullmatch(r"(\d+)\.(\d{1,2})", s)
        if m:
            whole, frac = m.groups()
        else:
            whole = s

    if re.fullmatch(_INT_GROUPED, whole):
        whole = whole.replace(".", "")
    elif not re.fullmatch(_INT_PLAIN, whole):
        raise _invalid(original)

    return sign * (int(whole) * 100 + int(frac.ljust(2, "0") or "0"))


def format_amount(cents: int) -> str:
    """Formatira cente za prikaz: 123456 -> '1.234,56 €', -3550 -> '-35,50 €'."""
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    grouped = f"{whole:,}".replace(",", ".")
    return f"{sign}{grouped},{frac:02d} €"


def _invalid(text: str) -> ValueError:
    return ValueError(f"Neispravan iznos: '{text}'")
