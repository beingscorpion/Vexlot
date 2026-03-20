# ── services/ledger_service.py ───────────────────────────────────────────────
from decimal import Decimal

from sqlalchemy.orm import Session, selectinload

from models import Investment, InvestmentPartner, Partner, ReturnEvent
from schemas import (
    CategoryBreakdown,
    LedgerDashboard,
    LedgerEntry,
    LedgerPartnerRow,
    LedgerSummary,
    PartnerLeaderboardEntry,
    ReturnEventResponse,
)


def get_ledger_dashboard(user_id: int, db: Session) -> LedgerDashboard:
    """
    Assemble everything the Ledger page needs in a single DB round-trip.
    """
    investments = (
        db.query(Investment)
        .options(
            selectinload(Investment.partners),
            selectinload(Investment.return_events),
        )
        .filter(Investment.user_id == user_id, Investment.is_active == True)
        .order_by(Investment.deal_date.desc().nullslast(), Investment.created_at.desc())
        .all()
    )

    # ── summary ───────────────────────────────────────────────────────────────
    total_capital   = sum(i.total_amount    for i in investments)
    total_returned  = sum(i.received_amount for i in investments)
    net_pnl         = total_returned - total_capital
    settled_count   = sum(1 for i in investments if i.status == "settled")
    partial_count   = sum(1 for i in investments if i.status == "partial")
    pending_count   = sum(1 for i in investments if i.status == "pending")
    pending_capital = sum(i.total_amount for i in investments if i.status == "pending")

    summary = LedgerSummary(
        total_capital=total_capital,
        total_returned=total_returned,
        net_pnl=net_pnl,
        settled_count=settled_count,
        partial_count=partial_count,
        pending_count=pending_count,
        total_deals=len(investments),
        pending_capital=pending_capital,
    )

    # ── ledger entries ────────────────────────────────────────────────────────
    entries: list[LedgerEntry] = []
    for inv in investments:
        partner_rows = [
            LedgerPartnerRow(
                partner_name=slot.partner_name,
                partner_id=slot.partner_id,
                percentage=slot.percentage,
                capital_amount=(slot.percentage / 100) * inv.total_amount,
                returned_amount=(slot.percentage / 100) * inv.received_amount,
                pnl=((slot.percentage / 100) * inv.received_amount)
                    - ((slot.percentage / 100) * inv.total_amount),
            )
            for slot in sorted(inv.partners, key=lambda p: p.display_order)
        ]
        event_rows = [
            ReturnEventResponse.model_validate(e)
            for e in sorted(inv.return_events, key=lambda e: e.created_at)
        ]
        entries.append(LedgerEntry(
            id=inv.id,
            name=inv.name,
            category=inv.category,
            deal_date=inv.deal_date,
            total_amount=inv.total_amount,
            received_amount=inv.received_amount,
            pnl=inv.pnl,
            status=inv.status,
            created_at=inv.created_at,
            updated_at=inv.updated_at,
            partners=partner_rows,
            return_events=event_rows,
        ))

    # ── partner leaderboard ───────────────────────────────────────────────────
    partner_map: dict[str, dict] = {}
    # fetch registered partner profiles for avatar colours
    profiles = {
        p.name.lower(): p
        for p in db.query(Partner)
                   .filter(Partner.user_id == user_id, Partner.is_active == True)
                   .all()
    }

    for inv in investments:
        for slot in inv.partners:
            key = slot.partner_name.lower()
            if key not in partner_map:
                prof = profiles.get(key)
                partner_map[key] = {
                    "partner_name":   slot.partner_name,
                    "partner_id":     slot.partner_id,
                    "avatar_bg":      prof.avatar_bg   if prof else None,
                    "avatar_text":    prof.avatar_text if prof else None,
                    "total_invested": Decimal("0"),
                    "total_returned": Decimal("0"),
                    "deal_count":     0,
                }
            cap = (slot.percentage / 100) * inv.total_amount
            ret = (slot.percentage / 100) * inv.received_amount
            partner_map[key]["total_invested"] += cap
            partner_map[key]["total_returned"] += ret
            partner_map[key]["deal_count"]     += 1

    leaderboard = sorted(
        [
            PartnerLeaderboardEntry(
                partner_name=v["partner_name"],
                partner_id=v["partner_id"],
                avatar_bg=v["avatar_bg"],
                avatar_text=v["avatar_text"],
                total_invested=v["total_invested"],
                total_returned=v["total_returned"],
                pnl=v["total_returned"] - v["total_invested"],
                deal_count=v["deal_count"],
            )
            for v in partner_map.values()
        ],
        key=lambda x: x.total_invested,
        reverse=True,
    )

    # ── category breakdown ────────────────────────────────────────────────────
    cat_map: dict[str, Decimal] = {}
    for inv in investments:
        cat_map[inv.category] = cat_map.get(inv.category, Decimal("0")) + inv.total_amount

    grand = sum(cat_map.values()) or Decimal("1")   # avoid /0
    cat_breakdown = sorted(
        [
            CategoryBreakdown(
                category=cat,
                total=amt,
                percentage=round((amt / grand) * 100, 2),
            )
            for cat, amt in cat_map.items()
        ],
        key=lambda x: x.total,
        reverse=True,
    )

    # ── recent activity (last 10 return events across all investments) ────────
    all_events = (
        db.query(ReturnEvent)
        .join(Investment, ReturnEvent.investment_id == Investment.id)
        .filter(Investment.user_id == user_id)
        .order_by(ReturnEvent.created_at.desc())
        .limit(10)
        .all()
    )
    recent_events = [ReturnEventResponse.model_validate(e) for e in all_events]

    return LedgerDashboard(
        summary=summary,
        entries=entries,
        partner_leaderboard=leaderboard,
        category_breakdown=cat_breakdown,
        recent_events=recent_events,
    )


def get_return_events(
    user_id: int,
    investment_id: int | None,
    db: Session,
) -> list[ReturnEventResponse]:
    """Return audit events, optionally scoped to one investment."""
    q = (
        db.query(ReturnEvent)
        .join(Investment, ReturnEvent.investment_id == Investment.id)
        .filter(Investment.user_id == user_id)
        .order_by(ReturnEvent.created_at.desc())
    )
    if investment_id:
        q = q.filter(ReturnEvent.investment_id == investment_id)
    return [ReturnEventResponse.model_validate(e) for e in q.limit(200).all()]
