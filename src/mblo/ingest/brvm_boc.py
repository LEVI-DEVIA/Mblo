"""Parser for the Bulletin Officiel de la Cote (daily PDF from brvm.org).

Uses pypdf layout extraction: columns are separated by 2+ spaces, thousands by
a single space. Long titles wrap onto a continuation line that may also carry
the sector code and, rarely, the tail of a number (ETIT volume "14 762" / "000").
"""

import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pypdf import PdfReader

from mblo.ingest.parsing import parse_decimal, parse_int, parse_long_fr_date, parse_pct, parse_short_fr_date

SECTOR_CODES = {"TEL", "FIN", "CD", "CB", "IND", "ENE", "SPU"}
SECTOR_NAMES = {
    "TEL": "Télécommunications",
    "FIN": "Services financiers",
    "CD": "Consommation discrétionnaire",
    "CB": "Consommation de base",
    "IND": "Industriels",
    "ENE": "Énergie",
    "SPU": "Services publics",
}

_TOKEN = re.compile(r"\S+(?: \S+)*")
_TICKER = re.compile(r"^[A-Z][A-Z0-9]{2,5}$")
_FLAG = re.compile(r"^\([A-Za-z]\)$")
_NUM = re.compile(r"^-?\d{1,3}(?: \d{3})*(?:,\d+)?$|^,\d+$")
_PCT = re.compile(r"^-?[\d ]+,\d+\s*%$|^-?\d+,\d+$")
_DATE = re.compile(r"^\d{1,2}-[a-zéû]+\.?-\d{2}$")
_ONLY_DIGITS = re.compile(r"^\d{3}$")


@dataclass
class BocRow:
    ticker: str
    name: str
    sector_code: str | None
    prev_close: Decimal | None
    open: Decimal | None
    close: Decimal | None
    change_pct: Decimal | None
    volume: int | None
    value_fcfa: int | None
    ref_price: Decimal | None
    ytd_pct: Decimal | None
    dividend_net: Decimal | None
    ex_dividend_date: date | None
    yield_pct: Decimal | None
    per: Decimal | None
    is_suspended: bool = False
    flags: list[str] = field(default_factory=list)


@dataclass
class BocSectorIndex:
    name: str
    companies: int | None
    value: Decimal | None
    change_pct: Decimal | None
    ytd_pct: Decimal | None
    volume: int | None
    value_fcfa: int | None
    per_avg: Decimal | None


@dataclass
class BocReport:
    session_date: date
    rows: list[BocRow]
    indices: dict[str, dict]  # name -> {value, change_pct, ytd_pct}
    sector_indices: list[BocSectorIndex]
    market: dict  # market-wide stats


# ------------------------------------------------------------------ helpers


def _tokens(line: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group()) for m in _TOKEN.finditer(line)]


def _is_data_line(toks: list[tuple[int, int, str]]) -> bool:
    texts = [t for _, _, t in toks]
    if not texts:
        return False
    i = 1 if texts[0] in SECTOR_CODES else 0
    if len(texts) < i + 5:
        return False
    if not _TICKER.match(texts[i]) or texts[i] in {"TOTAL"}:
        return False
    # skip title words and flags like "(V)", then need prev/open/close/change
    j = i + 1
    while j < len(texts) and not (_NUM.match(texts[j]) or texts[j] == "SP"):
        j += 1
    return j > i + 1 and len(texts) - j >= 4


def _parse_data_line(toks: list[tuple[int, int, str]]) -> tuple[BocRow, list[tuple[int, int, str]], int]:
    texts = [t for _, _, t in toks]
    sector = None
    i = 0
    if texts[0] in SECTOR_CODES:
        sector = texts[0]
        i = 1
    ticker = texts[i]
    i += 1
    name_parts, flags = [], []
    while i < len(texts) and not (_NUM.match(texts[i]) or texts[i] == "SP"):
        if _FLAG.match(texts[i]):
            flags.append(texts[i].strip("()"))
        else:
            name_parts.append(texts[i])
        i += 1
    rest = texts[i:]
    rest_toks = toks[i:]

    def num(s):
        return None if s == "SP" else parse_decimal(s)

    prev_close, open_, close = num(rest[0]), num(rest[1]), num(rest[2])
    suspended = rest[1] == "SP" or rest[2] == "SP"
    change = parse_pct(rest[3])
    j = 4
    volume = value = None
    if not suspended and j + 1 < len(rest) and _NUM.match(rest[j]) and _NUM.match(rest[j + 1]) and "%" not in rest[j + 1]:
        volume, value = parse_int(rest[j]), parse_int(rest[j + 1])
        j += 2
    ref = parse_decimal(rest[j]) if j < len(rest) else None
    j += 1
    ytd = parse_pct(rest[j]) if j < len(rest) and "%" in rest[j] else None
    if j < len(rest) and "%" in rest[j]:
        j += 1
    dividend = ex_date = yld = per = None
    for tok in rest[j:]:
        if _DATE.match(tok):
            ex_date = parse_short_fr_date(tok)
        elif "%" in tok:
            yld = parse_pct(tok)
        elif dividend is None and ex_date is None:
            dividend = parse_decimal(tok)
        else:
            per = parse_decimal(tok)
    row = BocRow(
        ticker=ticker,
        name=" ".join(name_parts).replace("''", "'"),
        sector_code=sector,
        prev_close=prev_close,
        open=open_,
        close=close if close is not None else prev_close,
        change_pct=change,
        volume=volume,
        value_fcfa=value,
        ref_price=ref,
        ytd_pct=ytd,
        dividend_net=dividend,
        ex_dividend_date=ex_date,
        yield_pct=yld,
        per=per,
        is_suspended=suspended,
        flags=flags,
    )
    return row, rest_toks, toks[1 if sector else 0][0]  # title column starts at the ticker


_FOOTER = re.compile(r"^(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}\s+[a-zéû]+\s+\d{4}$|^\d{1,2}$")


def _apply_continuation(row: BocRow, data_toks: list[tuple[int, int, str]], cont: list[tuple[int, int, str]], name_start: int) -> None:
    """Continuation line: sector code, wrapped title words, or a wrapped '000'.
    Title words are accepted only when they sit under the title column."""
    texts = [t for _, _, t in cont]
    if texts and texts[0] in SECTOR_CODES and row.sector_code is None:
        row.sector_code = texts[0]
        cont = cont[1:]
    # title column spans from the ticker token to the first numeric token
    name_end = data_toks[0][0] if data_toks else 10**6
    for s, e, t in cont:
        if _FOOTER.match(t.strip().lower()):
            continue
        if _ONLY_DIGITS.match(t):
            # find the numeric column of the data line that this fragment sits under
            for ds, de, dt in data_toks:
                if s < de + 2 and e > ds - 2 and _NUM.match(dt) and "%" not in dt:
                    merged = parse_int(dt + " " + t)
                    if row.volume is not None and parse_int(dt) == row.volume:
                        row.volume = merged
                    elif row.value_fcfa is not None and parse_int(dt) == row.value_fcfa:
                        row.value_fcfa = merged
                    break
        elif not _NUM.match(t) and not _PCT.match(t) and not _DATE.match(t) and s >= name_start and s < name_end:
            row.name = (row.name + " " + t).strip().replace("''", "'")


def parse_stock_pages(pages_text: list[str]) -> list[BocRow]:
    rows: list[BocRow] = []
    current: BocRow | None = None
    current_toks: list[tuple[int, int, str]] = []
    name_start = 0
    pending_sector: str | None = None
    for text in pages_text:
        for line in text.splitlines():
            if not line.strip():
                continue
            toks = _tokens(line)
            texts = [t for _, _, t in toks]
            if texts[0].startswith("TOTAL") or texts[0].startswith("COMPARTIMENT"):
                current = None
                continue
            if _is_data_line(toks):
                current, current_toks, name_start = _parse_data_line(toks)
                if current.sector_code is None and pending_sector:
                    current.sector_code = pending_sector
                pending_sector = None
                rows.append(current)
            elif len(texts) == 1 and texts[0] in SECTOR_CODES:
                if current is not None and current.sector_code is None:
                    current.sector_code = texts[0]
                else:
                    pending_sector = texts[0]
            elif current is not None:
                _apply_continuation(current, current_toks, toks, name_start)
    return rows


_SECTOR_LINE = re.compile(
    r"^(BRVM\s*[-–]\s*[A-ZÉÈÀ' ]+?)\s+(?:\(\*\*\)\s+)?(\d+)\s+([\d ]+,\d{2})\s+(-?\d+,\d{2})\s*%\s+(-?\d+,\d{2})\s*%\s+([\d ]+?)\s{2,}([\d ]+?)\s+(\d+,\d{2})\s*$"
)


def parse_summary_page(text: str) -> tuple[dict, list[BocSectorIndex], dict]:
    indices: dict[str, dict] = {}
    sectors: list[BocSectorIndex] = []
    market: dict = {}
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    for k, line in enumerate(lines):
        m = re.match(r"^(BRVM COMPOSITE|BRVM PRESTIGE|BRVM 30)\s+([\d ]+,\d{2})$", line.strip())
        if m:
            name = m.group(1)
            entry = {"value": parse_decimal(m.group(2)), "change_pct": None, "ytd_pct": None}
            for nxt in lines[k + 1 : k + 3]:
                mm = re.match(r"^Variation (Jour|annuelle)\s+(-?\d+,\d{2})\s*%", nxt.strip())
                if mm:
                    entry["change_pct" if mm.group(1) == "Jour" else "ytd_pct"] = parse_pct(mm.group(2))
            indices[name] = entry
            continue
        m = _SECTOR_LINE.match(line.strip())
        if m:
            sectors.append(
                BocSectorIndex(
                    name=" ".join(m.group(1).replace("–", "-").replace("-", " ").split()),
                    companies=parse_int(m.group(2)),
                    value=parse_decimal(m.group(3)),
                    change_pct=parse_pct(m.group(4)),
                    ytd_pct=parse_pct(m.group(5)),
                    volume=parse_int(m.group(6)),
                    value_fcfa=parse_int(m.group(7)),
                    per_avg=parse_decimal(m.group(8)),
                )
            )
            continue
        for key, pat in (
            ("market_cap", r"^Capitalisation boursière \(FCFA\)\(Actions & Droits\)\s+([\d ]+)\s+-?\d+,\d{2}"),
            ("volume", r"^Volume échangé \(Actions & Droits\)\s+([\d ]+)\s+-?\d+,\d{2}"),
            ("value_fcfa", r"^Valeur transigée \(FCFA\) \(Actions & Droits\)\s+([\d ]+)\s+-?\d+,\d{2}"),
            ("advancers", r"^Nombre de titres en hausse\s+(\d+)\s+-?\d+,\d{2}"),
            ("decliners", r"^Nombre de titres en baisse\s+(\d+)\s+-?\d+,\d{2}"),
            ("unchanged", r"^Nombre de titres inchangés\s+(\d+)\s+-?\d+,\d{2}"),
            ("market_per", r"^PER moyen du marché\s+(?:\(\*\*\)\s+)?(\d+,\d{2})"),
            ("market_yield", r"^Taux de rendement moyen du marché\s+(\d+,\d{2})"),
        ):
            if key in market:
                continue
            mm = re.match(pat, line.strip())
            if mm:
                market[key] = parse_decimal(mm.group(1)) if key in ("market_per", "market_yield") else parse_int(mm.group(1))
    return indices, sectors, market


def parse_boc(pdf_bytes: bytes) -> BocReport:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    plain = [p.extract_text() or "" for p in reader.pages]
    session_date = None
    for text in plain:
        m = re.search(r"(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}\s+[a-zéû]+\s+\d{4}", text.lower())
        d = parse_long_fr_date(m.group(0)) if m else None
        if d:
            session_date = d
            break
    if session_date is None:
        raise ValueError("session date not found in bulletin")

    indices, sectors, market = parse_summary_page(plain[0])

    # stock pages: those whose plain text contains sector-coded lines and no bond section
    layout_pages = []
    for i, text in enumerate(plain):
        if "OBLIGATIONS" in text[:200] or "OBLIGATIONS CLASSIQUES" in text:
            break
        if i == 0:
            continue
        if re.search(r"^(CB|CD|ENE|FIN|IND|SPU|TEL)\s", text, re.M):
            layout_pages.append(reader.pages[i].extract_text(extraction_mode="layout") or "")
    rows = parse_stock_pages(layout_pages)
    if not rows:
        raise ValueError("no stock rows parsed from bulletin")
    return BocReport(session_date=session_date, rows=rows, indices=indices, sector_indices=sectors, market=market)
