from datetime import date
from decimal import Decimal

import pytest

from mblo.ingest.brvm_boc import parse_boc


@pytest.fixture(scope="module")
def report():
    from pathlib import Path

    return parse_boc((Path(__file__).parent / "fixtures" / "boc_20260917.pdf").read_bytes())


def test_session_date(report):
    assert report.session_date == date(2026, 9, 17)


def test_row_count_and_tickers(report):
    tickers = {r.ticker for r in report.rows}
    assert len(report.rows) == 47
    for t in ("SNTS", "ETIT", "LNBB", "SEMC", "UNLC", "CBIBF", "NSBC", "SDCC"):
        assert t in tickers


def test_simple_row(report):
    ntlc = next(r for r in report.rows if r.ticker == "NTLC")
    assert ntlc.sector_code == "CB"
    assert ntlc.name == "NESTLE CI"
    assert (ntlc.prev_close, ntlc.open, ntlc.close) == (Decimal("16400"), Decimal("16400"), Decimal("16355"))
    assert ntlc.change_pct == Decimal("-0.27")
    assert ntlc.volume == 392
    assert ntlc.value_fcfa == 6_429_550
    assert ntlc.ref_price == Decimal("16355")
    assert ntlc.ytd_pct == Decimal("53.57")
    assert ntlc.dividend_net == Decimal("369.6")
    assert ntlc.ex_dividend_date == date(2026, 9, 7)
    assert ntlc.yield_pct == Decimal("2.26")
    assert ntlc.per == Decimal("19.59")


def test_wrapped_name_and_sector_on_next_line(report):
    lnbb = next(r for r in report.rows if r.ticker == "LNBB")
    assert lnbb.sector_code == "CD"
    assert lnbb.name == "LOTERIE NATIONALE DU BENIN"
    assert lnbb.close == Decimal("4095")
    ttls = next(r for r in report.rows if r.ticker == "TTLS")
    assert ttls.sector_code == "ENE"
    assert ttls.name == "TOTALENERGIES MARKETING SN"


def test_wrapped_volume(report):
    etit = next(r for r in report.rows if r.ticker == "ETIT")
    assert etit.close == Decimal("70")
    assert etit.volume == 14_762_000
    assert etit.value_fcfa == 984_311_898
    assert etit.dividend_net == Decimal("0.92")


def test_suspended(report):
    sicc = next(r for r in report.rows if r.ticker == "SICC")
    assert sicc.is_suspended
    assert sicc.open is None and sicc.volume is None
    assert sicc.close == Decimal("8400")
    assert sicc.ytd_pct == Decimal("154.55")


def test_flag_and_missing_yield(report):
    smbc = next(r for r in report.rows if r.ticker == "SMBC")
    assert "V" in smbc.flags
    assert smbc.close == Decimal("17000")
    unlc = next(r for r in report.rows if r.ticker == "UNLC")
    assert unlc.dividend_net == Decimal("1233")
    assert unlc.ex_dividend_date == date(2012, 7, 9)
    assert unlc.yield_pct is None
    assert unlc.per == Decimal("755.80")


def test_summary(report):
    assert report.indices["BRVM COMPOSITE"]["value"] == Decimal("548.07")
    assert report.indices["BRVM COMPOSITE"]["change_pct"] == Decimal("-0.27")
    assert report.indices["BRVM 30"]["value"] == Decimal("265.31")
    names = {s.name for s in report.sector_indices}
    assert "BRVM TELECOMMUNICATIONS" in names
    tel = next(s for s in report.sector_indices if s.name == "BRVM TELECOMMUNICATIONS")
    assert tel.per_avg == Decimal("14.27") and tel.companies == 3
    assert report.market["advancers"] == 13 and report.market["decliners"] == 29
    assert report.market["market_per"] == Decimal("17.90")
    assert report.market["volume"] == 15_012_903


def test_footer_date_is_not_glued_to_last_title():
    from mblo.ingest.brvm_boc import parse_stock_pages

    page = (
        "         NSBC         NSIA BANQUE COTE                             24 500     24 500      24 505          0,02 %           2 228      54 610 195           24 505             114,11 %            675,98      4-août-26         2,76 %      14,89\n"
        " FIN                  D'IVOIRE\n"
        "                                                                                                                                      3\n"
        "                                                                                                   vendredi 18 septembre 2026\n"
        " FIN     ECOC         ECOBANK COTE D''IVOIRE                       17 005     16 950      17 100          0,56 %           2 804      47 764 745           17 100                6,88 %            781,44     26-mai-26         4,57 %      14,83\n"
    )
    rows = parse_stock_pages([page])
    assert [r.ticker for r in rows] == ["NSBC", "ECOC"]
    assert rows[0].name == "NSIA BANQUE COTE D'IVOIRE"
    assert rows[0].sector_code == "FIN"
    assert rows[1].name == "ECOBANK COTE D'IVOIRE"
