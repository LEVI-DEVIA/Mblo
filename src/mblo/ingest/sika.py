"""Parsers for SikaFinance pages: A-to-Z quotes, news, official publications,
company fundamentals, price history, dividends."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from bs4 import BeautifulSoup

from mblo.ingest.parsing import (
    clean,
    parse_decimal,
    parse_fr_date,
    parse_int,
    parse_iso_datetime,
    parse_pct,
)

BASE = "https://www.sikafinance.com"
URL_AAZ = f"{BASE}/marches/aaz"
URL_NEWS = f"{BASE}/marches/actualites_bourse_brvm"
URL_COMMUNIQUES = f"{BASE}/marches/communiques_brvm"
URL_DIVIDENDS = f"{BASE}/marches/dividendes"


def url_company(sika_id: str) -> str:
    return f"{BASE}/marches/societe/{sika_id}"


def url_history(sika_id: str) -> str:
    return f"{BASE}/marches/historiques/{sika_id}"


def url_quote(sika_id: str) -> str:
    return f"{BASE}/marches/cotation_{sika_id}"


@dataclass(frozen=True)
class AazRow:
    sika_id: str  # e.g. SNTS.sn
    ticker: str  # e.g. SNTS
    name: str
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    volume: int | None
    value_fcfa: int | None
    last: Decimal | None
    change_pct: Decimal | None


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    summary: str | None
    published_at: datetime | None
    is_premium: bool


@dataclass(frozen=True)
class Communique:
    published_on: date | None
    text: str


@dataclass(frozen=True)
class FundamentalRow:
    fiscal_year: int
    revenue: Decimal | None
    revenue_growth: Decimal | None
    net_income: Decimal | None
    net_income_growth: Decimal | None
    eps: Decimal | None
    per: Decimal | None
    dividend: Decimal | None


@dataclass(frozen=True)
class HistoryRow:
    session_date: date
    close: Decimal | None
    low: Decimal | None
    high: Decimal | None
    open: Decimal | None
    volume: int | None
    value_fcfa: int | None
    change_pct: Decimal | None


@dataclass(frozen=True)
class UpcomingDividend:
    ex_date: date | None
    name: str
    amount: Decimal | None
    yield_pct: Decimal | None


def _soup(html: str | bytes) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _rows(table) -> list[list[str]]:
    out = []
    for tr in table.find_all("tr"):
        cells = [clean(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
        if cells:
            out.append(cells)
    return out


def parse_aaz(html: str | bytes) -> list[AazRow]:
    soup = _soup(html)
    out = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = clean(rows[0].get_text(" ")).lower()
        if "volume (titres)" not in header:
            continue
        for tr in rows[1:]:
            tds = tr.find_all("td")
            if len(tds) < 8:
                continue
            a = tds[0].find("a", href=True)
            m = re.search(r"cotation_([A-Z0-9]+\.[a-z]{2})", a["href"]) if a else None
            if not m:
                continue
            sika_id = m.group(1)
            vals = [clean(td.get_text(" ")) for td in tds]
            out.append(
                AazRow(
                    sika_id=sika_id,
                    ticker=sika_id.split(".")[0],
                    name=vals[0],
                    open=parse_decimal(vals[1]),
                    high=parse_decimal(vals[2]),
                    low=parse_decimal(vals[3]),
                    volume=parse_int(vals[4]),
                    value_fcfa=parse_int(vals[5]),
                    last=parse_decimal(vals[6]),
                    change_pct=parse_pct(vals[7]),
                )
            )
    if not out:
        raise ValueError("A-to-Z table not found")
    return out


def parse_news(html: str | bytes) -> list[NewsItem]:
    soup = _soup(html)
    out = []
    for li in soup.select("li.news-item"):
        a = li.select_one("a.news-title") or li.select_one("a.news-thumb")
        if not a or not a.get("href"):
            continue
        title = clean(a.get_text()) or clean(a.get("aria-label", ""))
        chapeau = li.select_one(".news-chapeau")
        t = li.select_one("time.news-date")
        published = parse_iso_datetime(t.get("datetime")) if t and t.get("datetime") else None
        premium = "(P)" in clean(li.get_text(" "))
        href = a["href"]
        out.append(
            NewsItem(
                title=title,
                url=href if href.startswith("http") else BASE + href,
                summary=clean(chapeau.get_text(" ")) if chapeau else None,
                published_at=published,
                is_premium=premium,
            )
        )
    return out


def parse_communiques(html: str | bytes) -> list[Communique]:
    soup = _soup(html)
    out = []
    for table in soup.find_all("table"):
        rows = _rows(table)
        if not rows or "publication" not in " ".join(rows[0]).lower():
            continue
        for r in rows[1:]:
            if len(r) >= 2 and r[1]:
                out.append(Communique(published_on=parse_fr_date(r[0]), text=r[1]))
    return out


def parse_company(html: str | bytes) -> list[FundamentalRow]:
    soup = _soup(html)
    for table in soup.find_all("table"):
        rows = _rows(table)
        if not rows or len(rows) < 3:
            continue
        header = rows[0]
        years = [parse_int(h) for h in header[1:]]
        if not years or any(y is None or y < 1990 for y in years):
            continue
        by_label = {r[0].lower(): r[1:] for r in rows[1:] if r}
        if "bnpa" not in by_label and "per" not in by_label:
            continue

        def col(label: str, i: int):
            vals = by_label.get(label)
            return parse_decimal(vals[i]) if vals and i < len(vals) else None

        return [
            FundamentalRow(
                fiscal_year=y,
                revenue=col("chiffre d'affaires", i),
                revenue_growth=col("croissance ca", i),
                net_income=col("résultat net", i),
                net_income_growth=col("croissance rn", i),
                eps=col("bnpa", i),
                per=col("per", i),
                dividend=col("dividende", i),
            )
            for i, y in enumerate(years)
        ]
    raise ValueError("fundamentals table not found")


def parse_company_profile(html: str | bytes) -> dict:
    """Shares outstanding and float from the profile text."""
    text = clean(_soup(html).get_text(" "))
    out: dict = {}
    m = re.search(r"Nombre de titres\s*:\s*([\d ]+)", text)
    if m:
        out["shares_outstanding"] = parse_int(m.group(1))
    m = re.search(r"Flottant\s*:\s*([\d,\.]+)\s*%", text)
    if m:
        out["float_pct"] = parse_decimal(m.group(1))
    return out


def parse_history(html: str | bytes) -> list[HistoryRow]:
    soup = _soup(html)
    for table in soup.find_all("table"):
        rows = _rows(table)
        if not rows or "clôture" not in " ".join(rows[0]).lower() or "date" not in rows[0][0].lower():
            continue
        out = []
        for r in rows[1:]:
            d = parse_fr_date(r[0]) if r else None
            if not d or len(r) < 8:
                continue
            out.append(
                HistoryRow(
                    session_date=d,
                    close=parse_decimal(r[1]),
                    low=parse_decimal(r[2]),
                    high=parse_decimal(r[3]),
                    open=parse_decimal(r[4]),
                    volume=parse_int(r[5]),
                    value_fcfa=parse_int(r[6]),
                    change_pct=parse_pct(r[7]),
                )
            )
        return out
    raise ValueError("history table not found")


def parse_upcoming_dividends(html: str | bytes) -> list[UpcomingDividend]:
    soup = _soup(html)
    for table in soup.find_all("table"):
        rows = _rows(table)
        if not rows or "détachement" not in " ".join(rows[0]).lower():
            continue
        return [
            UpcomingDividend(
                ex_date=parse_fr_date(r[0]),
                name=r[1],
                amount=parse_decimal(r[2]),
                yield_pct=parse_pct(r[3]),
            )
            for r in rows[1:]
            if len(r) >= 4
        ]
    return []
