# ── models.py ────────────────────────────────────────────────────────────────
# Complete ORM table definitions for the Verdant platform.
#
# Table map
# ─────────────────────────────────────────────────────────────────────────────
#   users               — account + credentials
#   refresh_tokens      — JWT refresh-token store
#   partners            — named partner profiles owned by a user
#   investments         — a capital deployment deal
#   investment_partners — which partners are in a deal + their % share
#   return_events       — immutable audit log for every received_amount change

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# 1.  USER
# ─────────────────────────────────────────────────────────────────────────────
class User(Base):
    """
    Core account record.
    Deleting a user cascades to every owned record (investments, partners, tokens).
    """
    __tablename__ = "users"

    id:         Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name:  Mapped[str] = mapped_column(String(100), nullable=False)
    email:      Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    hashed_password: Mapped[str]  = mapped_column(String(255), nullable=False)
    is_active:       Mapped[bool] = mapped_column(Boolean, default=True,  nullable=False)
    is_verified:     Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    # ── relationships ────────────────────────────────────────────────────────
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True,
    )
    partners: Mapped[list["Partner"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True,
    )
    investments: Mapped[list["Investment"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# 2.  REFRESH TOKEN
# ─────────────────────────────────────────────────────────────────────────────
class RefreshToken(Base):
    """
    Persisted refresh-token store (SHA-256 hash only — raw token never stored).
    """
    __tablename__ = "refresh_tokens"

    id:         Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64),  nullable=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked:    Mapped[bool]     = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    @property
    def is_expired(self) -> bool:
        # SQLite often strips timezone info, returning an offset-naive datetime.
        # Normalize to UTC-aware before comparing.
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= exp

    @property
    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id} user_id={self.user_id} revoked={self.revoked}>"


# ─────────────────────────────────────────────────────────────────────────────
# 3.  PARTNER
# ─────────────────────────────────────────────────────────────────────────────
class Partner(Base):
    """
    A named business-partner profile belonging to one user.

    Partners are optional — an InvestmentPartner row can reference a registered
    Partner (via partner_id FK) or just carry a raw name string for quick entry.
    When a profile is later created its name is matched and partner_id backfilled.

    avatar_bg / avatar_text store the hex colour codes chosen in the UI.
    """
    __tablename__ = "partners"

    id:      Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name:  Mapped[str]        = mapped_column(String(200), nullable=False, index=True)
    role:  Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50),  nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text,        nullable=True)

    avatar_bg:   Mapped[str | None] = mapped_column(String(20), nullable=True, default="#1a4020")
    avatar_text: Mapped[str | None] = mapped_column(String(20), nullable=True, default="#a8d5ad")

    is_active:  Mapped[bool]     = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    # ── relationships ────────────────────────────────────────────────────────
    owner: Mapped["User"] = relationship(back_populates="partners")
    investment_slots: Mapped[list["InvestmentPartner"]] = relationship(
        back_populates="partner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # Same user cannot have two partners with the same name
        UniqueConstraint("user_id", "name", name="uq_partner_user_name"),
    )

    def __repr__(self) -> str:
        return f"<Partner id={self.id} name={self.name!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# 4.  INVESTMENT
# ─────────────────────────────────────────────────────────────────────────────
VALID_CATEGORIES = ("real-estate", "stocks", "business", "commodities", "other")


class Investment(Base):
    """
    A capital-deployment deal.

    total_amount     — total money committed (across all partners)
    received_amount  — total money received back so far  (user-editable)

    Partners and their % shares live in child InvestmentPartner rows.
    Every change to received_amount appends a ReturnEvent for the audit trail.
    """
    __tablename__ = "investments"

    id:      Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name:     Mapped[str]        = mapped_column(String(300), nullable=False)
    category: Mapped[str]        = mapped_column(String(50),  nullable=False, default="other")
    notes:    Mapped[str | None] = mapped_column(Text,        nullable=True)

    # Date the deal was opened (user-supplied, may differ from created_at)
    deal_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Financials — NUMERIC(18,2) for decimal precision
    total_amount:    Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    received_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)

    is_active:  Mapped[bool]     = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    # ── relationships ────────────────────────────────────────────────────────
    owner: Mapped["User"] = relationship(back_populates="investments")

    partners: Mapped[list["InvestmentPartner"]] = relationship(
        back_populates="investment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="InvestmentPartner.display_order",
    )
    return_events: Mapped[list["ReturnEvent"]] = relationship(
        back_populates="investment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ReturnEvent.created_at",
    )

    # ── computed helpers (not persisted) ─────────────────────────────────────
    @property
    def pnl(self) -> Decimal:
        """Net profit / loss = received − invested."""
        return self.received_amount - self.total_amount

    @property
    def status(self) -> str:
        """pending | partial | settled"""
        if self.received_amount <= 0:
            return "pending"
        if self.received_amount >= self.total_amount:
            return "settled"
        return "partial"

    @property
    def partner_pct_total(self) -> Decimal:
        """Sum of all partner percentages (should equal 100)."""
        return sum((p.percentage for p in self.partners), Decimal("0"))

    __table_args__ = (
        CheckConstraint("total_amount    >= 0", name="ck_inv_total_non_neg"),
        CheckConstraint("received_amount >= 0", name="ck_inv_received_non_neg"),
    )

    def __repr__(self) -> str:
        return f"<Investment id={self.id} name={self.name!r} status={self.status!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# 5.  INVESTMENT PARTNER  (junction)
# ─────────────────────────────────────────────────────────────────────────────
class InvestmentPartner(Base):
    """
    Binds a partner (named or profile-linked) to an investment with a % share.

    partner_id    — nullable FK to partners.id  (NULL = unregistered, name-only)
    partner_name  — always populated (denormalised to avoid JOIN for display)
    percentage    — NUMERIC(5,2), e.g. 33.33
    display_order — preserves the order partners were added in the UI
    """
    __tablename__ = "investment_partners"

    id:            Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    investment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("investments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    partner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("partners.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    partner_name:  Mapped[str]     = mapped_column(String(200), nullable=False)
    percentage:    Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    display_order: Mapped[int]     = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    # ── relationships ────────────────────────────────────────────────────────
    investment: Mapped["Investment"]      = relationship(back_populates="partners")
    partner:    Mapped["Partner | None"]  = relationship(back_populates="investment_slots")

    # ── computed helpers ──────────────────────────────────────────────────────
    @property
    def capital_amount(self) -> Decimal:
        """This partner's share of the total capital."""
        if self.investment:
            return (self.percentage / 100) * self.investment.total_amount
        return Decimal("0")

    @property
    def returned_amount(self) -> Decimal:
        """This partner's share of what has been received."""
        if self.investment:
            return (self.percentage / 100) * self.investment.received_amount
        return Decimal("0")

    @property
    def pnl(self) -> Decimal:
        return self.returned_amount - self.capital_amount

    __table_args__ = (
        # A partner name can only appear once per investment
        UniqueConstraint("investment_id", "partner_name", name="uq_inv_partner_name"),
        CheckConstraint("percentage > 0 AND percentage <= 100", name="ck_ip_pct_range"),
    )

    def __repr__(self) -> str:
        return (
            f"<InvestmentPartner inv={self.investment_id} "
            f"partner={self.partner_name!r} pct={self.percentage}>"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 6.  RETURN EVENT  (immutable audit log)
# ─────────────────────────────────────────────────────────────────────────────
class ReturnEvent(Base):
    """
    Immutable record created every time Investment.received_amount changes.
    Rows are INSERT-only — never updated or deleted.
    This table powers the Ledger's audit trail and activity timeline.

    previous_amount           — value before the edit
    new_amount                — value after the edit
    delta                     — new − previous  (positive = more cash received)
    note                      — optional user annotation
    investment_name_snapshot  — denormalised name at the time (survives renames)
    recorded_by               — user_id of whoever made the change
    """
    __tablename__ = "return_events"

    id:            Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    investment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("investments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    recorded_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    previous_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    new_amount:      Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    delta:           Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    note:            Mapped[str | None] = mapped_column(String(500), nullable=True)

    investment_name_snapshot: Mapped[str] = mapped_column(String(300), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True,
    )

    # ── relationships ────────────────────────────────────────────────────────
    investment: Mapped["Investment"] = relationship(back_populates="return_events")
    recorder:   Mapped["User"]       = relationship("User", foreign_keys=[recorded_by])

    def __repr__(self) -> str:
        return (
            f"<ReturnEvent id={self.id} inv={self.investment_id} "
            f"delta={self.delta} at={self.created_at}>"
        )
