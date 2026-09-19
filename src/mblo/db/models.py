from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def now_col() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------- market


class Company(Base):
    __tablename__ = "company"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    sika_id: Mapped[str | None] = mapped_column(String(16))
    sector_code: Mapped[str | None] = mapped_column(String(8))
    sector_name: Mapped[str | None] = mapped_column(String(80))
    country: Mapped[str | None] = mapped_column(String(2))
    shares_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    float_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    quotes: Mapped[list["DailyQuote"]] = relationship(back_populates="company")


class DailyQuote(Base):
    __tablename__ = "daily_quote"
    __table_args__ = (UniqueConstraint("company_id", "session_date", name="uq_quote_company_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    session_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    high: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    low: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    close: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    value_fcfa: Mapped[int | None] = mapped_column(BigInteger)
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    source: Mapped[str] = mapped_column(String(20))
    adjusted_factor: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(1), server_default=text("1"))

    company: Mapped[Company] = relationship(back_populates="quotes")


class DailyOfficial(Base):
    """One row per title per session, from the Bulletin Officiel de la Cote."""

    __tablename__ = "daily_official"
    __table_args__ = (UniqueConstraint("company_id", "session_date", name="uq_official_company_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    session_date: Mapped[date] = mapped_column(Date, index=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    ref_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    per: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    dividend_net: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    ex_dividend_date: Mapped[date | None] = mapped_column(Date)
    yield_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    ytd_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class Indicator(Base):
    __tablename__ = "indicator"
    __table_args__ = (UniqueConstraint("company_id", "session_date", name="uq_indicator_company_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    session_date: Mapped[date] = mapped_column(Date, index=True)
    ma20: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    ma50: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    rsi14: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    high_52w: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    low_52w: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    avg_volume_20: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    volume_ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    per: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    yield_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    sector_per_avg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))


class Fundamental(Base):
    __tablename__ = "fundamental"
    __table_args__ = (UniqueConstraint("company_id", "fiscal_year", name="uq_fundamental_company_year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))  # millions FCFA
    revenue_growth: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    net_income: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    net_income_growth: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    eps: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    per: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    dividend: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))


class IndexQuote(Base):
    __tablename__ = "index_quote"
    __table_args__ = (UniqueConstraint("index_name", "session_date", name="uq_index_name_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    index_name: Mapped[str] = mapped_column(String(80), index=True)
    session_date: Mapped[date] = mapped_column(Date, index=True)
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    close: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    ytd_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    per_avg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))


class MarketDay(Base):
    """Market-wide figures for one session, used by the digest."""

    __tablename__ = "market_day"

    session_date: Mapped[date] = mapped_column(Date, primary_key=True)
    market_cap: Mapped[int | None] = mapped_column(BigInteger)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    value_fcfa: Mapped[int | None] = mapped_column(BigInteger)
    advancers: Mapped[int | None] = mapped_column(Integer)
    decliners: Mapped[int | None] = mapped_column(Integer)
    unchanged: Mapped[int | None] = mapped_column(Integer)
    market_per: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    market_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))


class DividendEvent(Base):
    __tablename__ = "dividend_event"
    __table_args__ = (UniqueConstraint("company_id", "ex_date", name="uq_dividend_company_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    ex_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    yield_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    source: Mapped[str] = mapped_column(String(20))


class News(Base):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(primary_key=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(500), unique=True)
    source: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20))  # article | communique
    company_id: Mapped[int | None] = mapped_column(ForeignKey("company.id"), index=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class CorporateAction(Base):
    __tablename__ = "corporate_action"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    effective_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(20))
    factor: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    note: Mapped[str | None] = mapped_column(Text)


class IngestRun(Base):
    __tablename__ = "ingest_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(String(30), index=True)
    started_at: Mapped[datetime] = now_col()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")
    rows: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------- users & credits


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(80))
    language: Mapped[str] = mapped_column(String(5), default="fr", server_default="fr")
    goal: Mapped[str | None] = mapped_column(String(20))  # revenus | long_terme | speculation
    horizon: Mapped[str | None] = mapped_column(String(20))
    capital_range: Mapped[str | None] = mapped_column(String(20))
    sgi_name: Mapped[str | None] = mapped_column(String(80))
    digest_subscribed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    onboarding_step: Mapped[str] = mapped_column(String(20), default="start", server_default="start")
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = now_col()
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreditLedger(Base):
    __tablename__ = "credit_ledger"
    __table_args__ = (
        Index("ix_ledger_user_created", "user_id", "created_at"),
        Index(
            "uq_ledger_recharge_reference",
            "reference",
            unique=True,
            postgresql_where=text("kind = 'recharge'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = now_col()
    kind: Mapped[str] = mapped_column(String(20))  # welcome | debit | recharge | adjustment
    amount: Mapped[int] = mapped_column(Integer)  # signed
    balance_after: Mapped[int] = mapped_column(Integer)
    action: Mapped[str | None] = mapped_column(String(30))
    reference: Mapped[str | None] = mapped_column(String(80))
    meta: Mapped[dict | None] = mapped_column(JSON)


class Tariff(Base):
    __tablename__ = "tariff"

    action: Mapped[str] = mapped_column(String(30), primary_key=True)
    credits: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class Payment(Base):
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_ref: Mapped[str] = mapped_column(String(80), unique=True)
    amount_fcfa: Mapped[int] = mapped_column(Integer)
    credits: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = now_col()
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict | None] = mapped_column(JSON)


class Watchlist(Base):
    __tablename__ = "watchlist"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    added_at: Mapped[datetime] = now_col()


class Position(Base):
    __tablename__ = "position"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer)
    avg_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------- conversation


class Message(Base):
    __tablename__ = "message"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    direction: Mapped[str] = mapped_column(String(3))  # in | out
    channel_msg_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    text: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = now_col()
    credits_charged: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    trace_id: Mapped[str | None] = mapped_column(String(80))


class Advice(Base):
    __tablename__ = "advice"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    created_at: Mapped[datetime] = now_col()
    verdict: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[str] = mapped_column(String(10))
    price_at_advice: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    summary: Mapped[str] = mapped_column(Text)
    full: Mapped[dict | None] = mapped_column(JSON)


class UserMemory(Base):
    __tablename__ = "user_memory"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # digest | alert | system
    text: Mapped[str] = mapped_column(Text)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    dedupe_key: Mapped[str] = mapped_column(String(80), unique=True)


class Digest(Base):
    __tablename__ = "digest"

    session_date: Mapped[date] = mapped_column(Date, primary_key=True)
    market_text: Mapped[str] = mapped_column(Text)
    built_at: Mapped[datetime] = now_col()
