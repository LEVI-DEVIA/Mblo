from decimal import Decimal

from mblo.ingest.brvm_quotes import (
    parse_bulletin_links,
    parse_capitalisations,
    parse_indices,
    parse_market_activity,
    parse_quotes,
    parse_sector_page,
)


def test_quotes_table(fixture):
    rows = parse_quotes(fixture("brvm_cours_actions.html"))
    assert len(rows) == 47
    by = {r.ticker: r for r in rows}
    abjc = by["ABJC"]
    assert abjc.name.startswith("SERVAIR")
    assert abjc.volume == 2242
    assert abjc.prev_close == Decimal("3810")
    assert abjc.open == Decimal("4005")
    assert abjc.close == Decimal("3850")
    assert abjc.change_pct == Decimal("-4.94")
    assert by["SNTS"].close == Decimal("42190")


def test_indices(fixture):
    rows = parse_indices(fixture("brvm_indices.html"))
    names = {r.name for r in rows}
    assert "BRVM 30" in names
    assert "BRVM COMPOSITE" in names
    assert "BRVM CONSOMMATION DE BASE" in names
    comp = next(r for r in rows if r.name == "BRVM COMPOSITE")
    assert comp.prev_close == Decimal("548.07")
    assert comp.close == Decimal("554.18")
    assert comp.change_pct == Decimal("1.11")


def test_capitalisations(fixture):
    rows = parse_capitalisations(fixture("brvm_capitalisations.html"))
    assert len(rows) == 47
    abjc = next(r for r in rows if r.ticker == "ABJC")
    assert abjc.shares == 10_912_000
    assert abjc.global_cap == 42_011_200_000
    assert abjc.weight_pct == Decimal("0.20")


def test_market_activity(fixture):
    act = parse_market_activity(fixture("brvm_cours_actions.html"))
    assert act.transactions_value == 4_229_749_702
    assert act.equity_cap == 21_370_018_398_817


def test_sector_page(fixture):
    sector, tickers = parse_sector_page(fixture("brvm_cours_actions_194.html"))
    assert sector == "Consommation de Base"
    assert "NTLC" in tickers and "PALC" in tickers


def test_bulletin_links(fixture):
    links = parse_bulletin_links(fixture("brvm_bulletins.html"))
    urls = [u for _, u in links]
    assert "https://www.brvm.org/sites/default/files/boc_20260917_2.pdf" in urls
    assert all(u.endswith(".pdf") for u in urls)
