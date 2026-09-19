from datetime import date
from decimal import Decimal

from mblo.ingest.sika import (
    parse_aaz,
    parse_communiques,
    parse_company,
    parse_company_profile,
    parse_history,
    parse_news,
    parse_upcoming_dividends,
)


def test_aaz(fixture):
    rows = parse_aaz(fixture("sika_aaz.html"))
    assert len(rows) >= 45
    snts = next(r for r in rows if r.ticker == "SNTS")
    assert snts.sika_id == "SNTS.sn"
    assert snts.name == "SONATEL"
    assert snts.last == Decimal("42190")
    boab = next(r for r in rows if r.ticker == "BOAB")
    assert boab.sika_id == "BOAB.bj"


def test_news(fixture):
    items = parse_news(fixture("sika_actualites.html"))
    assert len(items) >= 5
    first = items[0]
    assert first.url.startswith("https://www.sikafinance.com/marches/")
    assert first.published_at is not None and first.published_at.year == 2026
    assert any("Sonatel" in i.title for i in items)
    assert any(i.is_premium for i in items)


def test_communiques(fixture):
    items = parse_communiques(fixture("sika_communiques.html"))
    assert len(items) >= 20
    assert items[0].published_on == date(2026, 9, 17)
    assert "SONATEL" in items[0].text


def test_company_fundamentals(fixture):
    rows = parse_company(fixture("sika_societe_SNTS.html"))
    years = {r.fiscal_year for r in rows}
    assert years == {2021, 2022, 2023, 2024, 2025}
    y25 = next(r for r in rows if r.fiscal_year == 2025)
    assert y25.eps == Decimal("4136.00")
    assert y25.per == Decimal("10.20")
    assert y25.dividend == Decimal("1740.00")
    assert y25.revenue == Decimal("1923122")
    assert y25.net_income_growth == Decimal("5.06")


def test_company_profile(fixture):
    p = parse_company_profile(fixture("sika_societe_SNTS.html"))
    assert p["shares_outstanding"] == 100_000_000
    assert p["float_pct"] == Decimal("22.47")


def test_history(fixture):
    rows = parse_history(fixture("sika_historiques_SNTS.html"))
    assert len(rows) >= 60
    assert rows[0].session_date == date(2026, 9, 18)
    assert rows[0].close == Decimal("42190")
    assert rows[0].volume == 65452
    assert rows[1].session_date == date(2026, 9, 17)
    assert rows[1].close == Decimal("39250")


def test_upcoming_dividends(fixture):
    rows = parse_upcoming_dividends(fixture("sika_dividendes.html"))
    assert any(r.name == "SODECI" and r.amount == Decimal("525.00") for r in rows)
    assert rows[0].ex_date == date(2026, 9, 15)
