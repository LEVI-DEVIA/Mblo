from datetime import date
from decimal import Decimal

from mblo.ingest.parsing import (
    parse_decimal,
    parse_fr_date,
    parse_int,
    parse_long_fr_date,
    parse_pct,
    parse_short_fr_date,
)


def test_numbers_with_french_formatting():
    assert parse_int("42 190") == 42190
    assert parse_int("2 761 419 880") == 2761419880
    assert parse_decimal("-1,64") == Decimal("-1.64")
    assert parse_pct("7,49%") == Decimal("7.49")
    assert parse_pct(" -7,45 % ") == Decimal("-7.45")
    assert parse_decimal("1740,00") == Decimal("1740.00")


def test_missing_values():
    for v in ("", "-", "SP", "NC", None, "  "):
        assert parse_decimal(v) is None
        assert parse_int(v) is None


def test_dates():
    assert parse_fr_date("17/09/2026") == date(2026, 9, 17)
    assert parse_fr_date("18/09/2026 11:03") == date(2026, 9, 18)
    assert parse_long_fr_date("jeudi 17 septembre 2026") == date(2026, 9, 17)
    assert parse_long_fr_date("1er août 2026") == date(2026, 8, 1)
    assert parse_short_fr_date("30-juil.-26") == date(2026, 7, 30)
    assert parse_short_fr_date("6-août-26") == date(2026, 8, 6)
    assert parse_short_fr_date("25-sept.-00") == date(2000, 9, 25)
    assert parse_short_fr_date("14-févr.-27") == date(2027, 2, 14)
    assert parse_short_fr_date("garbage") is None
