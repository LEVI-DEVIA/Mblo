"""Ingestion jobs. Usage: mblo-ingest daily | boc [--date YYYY-MM-DD] | fundamentals"""

import argparse
import hashlib
import logging
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from mblo.config import get_settings
from mblo.db import models as m
from mblo.db.session import new_session
from mblo.ingest import brvm_boc, brvm_quotes, sika
from mblo.ingest.http import Fetcher, RawStore
from mblo.ingest.store import ensure_companies, upsert

log = logging.getLogger("mblo.ingest")


def _fetcher() -> Fetcher:
    return Fetcher(store=RawStore(get_settings().raw_dir))


def _run(job: str, fn) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    session = new_session()
    run = m.IngestRun(job=job)
    session.add(run)
    session.commit()
    try:
        rows = fn(session)
        run.status, run.rows = "ok", rows
        run.finished_at = datetime.now(timezone.utc)
        session.commit()
        log.info("%s done: %s rows", job, rows)
        return 0
    except Exception as e:  # noqa: BLE001
        session.rollback()
        run.status, run.detail = "error", f"{type(e).__name__}: {e}"[:2000]
        run.finished_at = datetime.now(timezone.utc)
        session.commit()
        log.exception("%s failed", job)
        return 1
    finally:
        session.close()


# ------------------------------------------------------------------ daily


def job_daily(session) -> int:
    f = _fetcher()
    try:
        quotes = brvm_quotes.parse_quotes(f.get(brvm_quotes.URL_QUOTES))
        indices = brvm_quotes.parse_indices(f.get(brvm_quotes.URL_INDICES))
        aaz = sika.parse_aaz(f.get(sika.URL_AAZ))
        news = sika.parse_news(f.get(sika.URL_NEWS))
        communiques = sika.parse_communiques(f.get(sika.URL_COMMUNIQUES))
        # session date is read from a dated source, never from the clock
        hist = sika.parse_history(f.get(sika.url_history("SNTS.sn")))
    finally:
        f.close()
    session_date = hist[0].session_date
    log.info("session date %s, %s quotes", session_date, len(quotes))

    aaz_by_ticker = {r.ticker: r for r in aaz}
    ids = ensure_companies(
        session,
        [{"ticker": q.ticker, "name": q.name, "sika_id": aaz_by_ticker[q.ticker].sika_id if q.ticker in aaz_by_ticker else None}
         for q in quotes],
        exclude_update=["name"],  # the bulletin's shorter names win once set
    )
    n = 0
    quote_rows = []
    for q in quotes:
        if q.close is None:
            continue
        a = aaz_by_ticker.get(q.ticker)
        quote_rows.append(
            {
                "company_id": ids[q.ticker],
                "session_date": session_date,
                "open": q.open,
                "high": a.high if a else None,
                "low": a.low if a else None,
                "close": q.close,
                "prev_close": q.prev_close,
                "volume": q.volume,
                "value_fcfa": a.value_fcfa if a else None,
                "change_pct": q.change_pct,
                "source": "brvm",
            }
        )
    n += upsert(session, m.DailyQuote, quote_rows, conflict=["company_id", "session_date"], exclude_update=["adjusted_factor"])
    n += upsert(
        session,
        m.IndexQuote,
        [
            {"index_name": i.name, "session_date": session_date, "prev_close": i.prev_close, "close": i.close,
             "change_pct": i.change_pct, "ytd_pct": i.ytd_pct}
            for i in indices if i.close is not None
        ],
        conflict=["index_name", "session_date"],
        exclude_update=["per_avg"],
    )
    n += upsert(
        session,
        m.News,
        [
            {"published_at": it.published_at, "title": it.title, "summary": it.summary, "url": it.url,
             "source": "sikafinance", "kind": "article", "is_premium": it.is_premium}
            for it in news if it.published_at
        ],
        conflict=["url"],
    )
    n += upsert(
        session,
        m.News,
        [
            {
                "published_at": datetime.combine(c.published_on, datetime.min.time(), tzinfo=timezone.utc),
                "title": c.text,
                "summary": None,
                "url": "sika:communique:" + hashlib.sha1(f"{c.published_on}|{c.text}".encode()).hexdigest()[:24],
                "source": "sikafinance",
                "kind": "communique",
                "is_premium": False,
            }
            for c in communiques if c.published_on
        ],
        conflict=["url"],
    )
    session.commit()
    return n


# ------------------------------------------------------------------ bulletin


def job_boc(session, day: date | None) -> int:
    if day is None:
        latest = session.execute(select(func.max(m.DailyQuote.session_date))).scalar()
        day = latest or (date.today() - timedelta(days=1))
    f = _fetcher()
    try:
        pdf = f.get(brvm_quotes.bulletin_url(day))
    finally:
        f.close()
    report = brvm_boc.parse_boc(pdf)
    if report.session_date != day:
        log.warning("bulletin dated %s, expected %s; using bulletin date", report.session_date, day)
    d = report.session_date

    ids = ensure_companies(
        session,
        [
            {"ticker": r.ticker, "name": r.name, "sector_code": r.sector_code,
             "sector_name": brvm_boc.SECTOR_NAMES.get(r.sector_code or ""), "is_suspended": r.is_suspended}
            for r in report.rows
        ],
    )
    n = upsert(
        session,
        m.DailyOfficial,
        [
            {"company_id": ids[r.ticker], "session_date": d, "close": r.close, "ref_price": r.ref_price, "per": r.per,
             "dividend_net": r.dividend_net, "ex_dividend_date": r.ex_dividend_date, "yield_pct": r.yield_pct,
             "ytd_pct": r.ytd_pct, "is_suspended": r.is_suspended}
            for r in report.rows
        ],
        conflict=["company_id", "session_date"],
    )
    # the bulletin is authoritative: fill or correct the day's quotes
    n += upsert(
        session,
        m.DailyQuote,
        [
            {"company_id": ids[r.ticker], "session_date": d, "open": r.open, "close": r.close, "prev_close": r.prev_close,
             "volume": r.volume, "value_fcfa": r.value_fcfa, "change_pct": r.change_pct, "source": "boc"}
            for r in report.rows if r.close is not None
        ],
        conflict=["company_id", "session_date"],
        exclude_update=["adjusted_factor", "high", "low"],
    )
    # one row per index name; compartment rows (with PER) win over the headline block
    idx: dict[str, dict] = {}
    for name, v in report.indices.items():
        if v.get("value") is not None:
            idx[name] = {"index_name": name, "session_date": d, "close": v["value"], "change_pct": v["change_pct"],
                         "ytd_pct": v["ytd_pct"], "per_avg": None}
    for s in report.sector_indices:
        if s.value is not None:
            idx[s.name] = {"index_name": s.name, "session_date": d, "close": s.value, "change_pct": s.change_pct,
                           "ytd_pct": s.ytd_pct, "per_avg": s.per_avg}
    n += upsert(session, m.IndexQuote, list(idx.values()), conflict=["index_name", "session_date"], exclude_update=["prev_close"])
    if report.market:
        n += upsert(session, m.MarketDay, [{"session_date": d, **report.market}], conflict=["session_date"])
    n += upsert(
        session,
        m.DividendEvent,
        [
            {"company_id": ids[r.ticker], "ex_date": r.ex_dividend_date, "amount": r.dividend_net, "yield_pct": r.yield_pct,
             "source": "boc"}
            for r in report.rows if r.ex_dividend_date and r.dividend_net is not None
        ],
        conflict=["company_id", "ex_date"],
    )
    session.commit()
    return n


# ------------------------------------------------------------------ fundamentals (monthly)


def job_fundamentals(session) -> int:
    companies = session.execute(select(m.Company).where(m.Company.sika_id.is_not(None))).scalars().all()
    f = _fetcher()
    n = 0
    try:
        for c in companies:
            try:
                html = f.get(sika.url_company(c.sika_id))
                rows = sika.parse_company(html)
                profile = sika.parse_company_profile(html)
            except Exception as e:  # noqa: BLE001
                log.warning("fundamentals %s: %s", c.ticker, e)
                continue
            n += upsert(
                session,
                m.Fundamental,
                [{"company_id": c.id, **r.__dict__} for r in rows],
                conflict=["company_id", "fiscal_year"],
            )
            for k, v in profile.items():
                setattr(c, k, v)
            session.commit()
    finally:
        f.close()
    return n


# ------------------------------------------------------------------ cli


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mblo-ingest")
    sub = p.add_subparsers(dest="job", required=True)
    sub.add_parser("daily", help="quotes, indices, news (after close)")
    b = sub.add_parser("boc", help="official bulletin PDF for a session")
    b.add_argument("--date", type=date.fromisoformat, default=None)
    sub.add_parser("fundamentals", help="5-year fundamentals from SikaFinance")
    args = p.parse_args(argv)
    if args.job == "daily":
        return _run("daily", job_daily)
    if args.job == "boc":
        return _run("boc", lambda s: job_boc(s, args.date))
    if args.job == "fundamentals":
        return _run("fundamentals", job_fundamentals)
    return 2


if __name__ == "__main__":
    sys.exit(main())
