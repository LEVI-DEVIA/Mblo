"""Parsers for brvm.org HTML pages: quotes, indices, capitalisations, sectors."""

from dataclasses import dataclass
from decimal import Decimal

from bs4 import BeautifulSoup

from mblo.ingest.parsing import clean, parse_decimal, parse_int, parse_pct

BASE = "https://www.brvm.org"
URL_QUOTES = f"{BASE}/fr/cours-actions/0"
URL_INDICES = f"{BASE}/fr/indices/0"
URL_CAPS = f"{BASE}/fr/capitalisations/0"
URL_BULLETINS = f"{BASE}/fr/bulletins-officiels-de-la-cote"
SECTOR_PAGE_IDS = range(194, 201)


def url_sector(page_id: int) -> str:
    return f"{BASE}/fr/cours-actions/{page_id}"


@dataclass(frozen=True)
class QuoteRow:
    ticker: str
    name: str
    volume: int | None
    prev_close: Decimal | None
    open: Decimal | None
    close: Decimal | None
    change_pct: Decimal | None


@dataclass(frozen=True)
class IndexRow:
    name: str
    prev_close: Decimal | None
    close: Decimal | None
    change_pct: Decimal | None
    ytd_pct: Decimal | None


@dataclass(frozen=True)
class CapRow:
    ticker: str
    name: str
    shares: int | None
    price: Decimal | None
    float_cap: int | None
    global_cap: int | None
    weight_pct: Decimal | None


@dataclass(frozen=True)
class MarketActivity:
    transactions_value: int | None
    equity_cap: int | None
    bond_cap: int | None


def _tables(html: str | bytes):
    soup = BeautifulSoup(html, "lxml")
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [clean(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if rows:
            yield rows


def _find_table(html, *header_words: str):
    for rows in _tables(html):
        header = " ".join(rows[0]).lower()
        if all(w.lower() in header for w in header_words):
            return rows
    raise ValueError(f"table with header {header_words} not found")


def parse_quotes(html: str | bytes) -> list[QuoteRow]:
    rows = _find_table(html, "Symbole", "Clôture")
    out = []
    for r in rows[1:]:
        if len(r) < 7 or not r[0]:
            continue
        out.append(
            QuoteRow(
                ticker=r[0].upper(),
                name=r[1],
                volume=parse_int(r[2]),
                prev_close=parse_decimal(r[3]),
                open=parse_decimal(r[4]),
                close=parse_decimal(r[5]),
                change_pct=parse_pct(r[6]),
            )
        )
    return out


def parse_indices(html: str | bytes) -> list[IndexRow]:
    out = []
    for rows in _tables(html):
        header = " ".join(rows[0]).lower()
        if "fermeture précédente" not in header:
            continue
        for r in rows[1:]:
            if len(r) < 5:
                continue
            out.append(
                IndexRow(
                    name=normalize_index_name(r[0]),
                    prev_close=parse_decimal(r[1]),
                    close=parse_decimal(r[2]),
                    change_pct=parse_pct(r[3]),
                    ytd_pct=parse_pct(r[4]),
                )
            )
    if not out:
        raise ValueError("no index table found")
    return out


def normalize_index_name(name: str) -> str:
    """'BRVM - COMPOSITE' / 'BRVM – COMPOSITE TOTAL RETURN' -> 'BRVM COMPOSITE'..."""
    t = clean(name).upper().replace("–", "-").replace("—", "-")
    t = " ".join(p for p in t.replace("-", " ").split())
    return t


def parse_capitalisations(html: str | bytes) -> list[CapRow]:
    rows = _find_table(html, "Nombre de titres", "Capitalisation")
    out = []
    for r in rows[1:]:
        if len(r) < 7 or not r[0]:
            continue
        out.append(
            CapRow(
                ticker=r[0].upper(),
                name=r[1],
                shares=parse_int(r[2]),
                price=parse_decimal(r[3]),
                float_cap=parse_int(r[4]),
                global_cap=parse_int(r[5]),
                weight_pct=parse_pct(r[6]),
            )
        )
    return out


def parse_market_activity(html: str | bytes) -> MarketActivity:
    values: dict[str, int | None] = {}
    for rows in _tables(html):
        if rows[0] and rows[0][0].lower().startswith("activités du marché"):
            for r in rows[1:]:
                if len(r) >= 2:
                    values[r[0].lower()] = parse_int(r[1])
    return MarketActivity(
        transactions_value=values.get("valeur des transactions"),
        equity_cap=values.get("capitalisation actions"),
        bond_cap=values.get("capitalisation des obligations"),
    )


def parse_sector_page(html: str | bytes) -> tuple[str, list[str]]:
    """Returns (sector name, tickers) from a /fr/cours-actions/{id} page."""
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1", class_="page-header")
    sector = clean(h1.get_text()) if h1 else ""
    tickers = [q.ticker for q in parse_quotes(html)]
    return sector, tickers


def parse_bulletin_links(html: str | bytes) -> list[tuple[str, str]]:
    """Returns [(label, pdf_url)] from the bulletins listing page."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/sites/default/files/boc_" in href and href.endswith(".pdf"):
            label = clean(a.find_parent("tr").get_text(" ")) if a.find_parent("tr") else clean(a.get_text())
            out.append((label, href if href.startswith("http") else BASE + href))
    return out


def bulletin_url(day) -> str:
    return f"{BASE}/sites/default/files/boc_{day:%Y%m%d}_2.pdf"
