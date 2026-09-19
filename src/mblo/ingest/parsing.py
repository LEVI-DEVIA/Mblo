"""Number and date parsing for French-formatted market pages."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

NBSP = " "
NARROW_NBSP = " "
MISSING = {"", "-", "—", "SP", "NC", "N/A", "n/a", "ND"}

_LONG_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
}
_SHORT_MONTHS = {
    "janv": 1, "févr": 2, "fevr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6, "juil": 7,
    "août": 8, "aout": 8, "sept": 9, "oct": 10, "nov": 11, "déc": 12, "dec": 12,
}


def clean(s: str | None) -> str:
    if s is None:
        return ""
    return " ".join(s.replace(NBSP, " ").replace(NARROW_NBSP, " ").split())


def parse_decimal(s: str | None) -> Decimal | None:
    """'42 190' -> 42190 ; '-1,64' -> -1.64 ; '7,49%' -> 7.49 ; 'SP' -> None."""
    t = clean(s)
    if t in MISSING:
        return None
    t = t.replace("%", "").replace(" ", "").replace(",", ".")
    t = re.sub(r"[^0-9.\-]", "", t)
    if t in {"", "-", ".", "-."}:
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def parse_int(s: str | None) -> int | None:
    d = parse_decimal(s)
    return int(d) if d is not None else None


def parse_pct(s: str | None) -> Decimal | None:
    return parse_decimal(s)


def parse_fr_date(s: str | None) -> date | None:
    """'17/09/2026' -> date."""
    t = clean(s)
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    return date(y, mo, d)


def parse_long_fr_date(s: str | None) -> date | None:
    """'jeudi 17 septembre 2026' -> date."""
    t = clean(s).lower()
    m = re.search(r"(\d{1,2})(?:er)?\s+([a-zéû]+)\s+(\d{4})", t)
    if not m:
        return None
    d, month, y = m.groups()
    mo = _LONG_MONTHS.get(month)
    return date(int(y), mo, int(d)) if mo else None


def parse_short_fr_date(s: str | None) -> date | None:
    """'30-juil.-26' / '6-août-26' / '25-sept.-00' -> date (2-digit year, 1990-2089)."""
    t = clean(s).lower()
    m = re.search(r"(\d{1,2})-([a-zéû]+)\.?-(\d{2})\b", t)
    if not m:
        return None
    d, month, yy = m.groups()
    mo = _SHORT_MONTHS.get(month.rstrip("."))
    if not mo:
        return None
    y = int(yy)
    year = 2000 + y if y < 90 else 1900 + y
    return date(year, mo, int(d))


def parse_iso_datetime(s: str | None) -> datetime | None:
    t = clean(s)
    try:
        return datetime.fromisoformat(t)
    except ValueError:
        return None
