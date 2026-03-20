# ── services/partner_service.py ──────────────────────────────────────────────
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from models import Investment, InvestmentPartner, Partner
from schemas import (
    PartnerCreateRequest,
    PartnerDealRow,
    PartnerDetail,
    PartnerUpdateRequest,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(db: Session, user_id: int, partner_id: int) -> Partner:
    p = (
        db.query(Partner)
        .filter(Partner.id == partner_id, Partner.user_id == user_id, Partner.is_active == True)
        .first()
    )
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found.")
    return p


# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_partner(payload: PartnerCreateRequest, user_id: int, db: Session) -> Partner:
    # Duplicate name check
    exists = (
        db.query(Partner)
        .filter(Partner.user_id == user_id, Partner.name.ilike(payload.name), Partner.is_active == True)
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A partner named '{payload.name}' already exists.",
        )

    partner = Partner(
        user_id=user_id,
        name=payload.name,
        role=payload.role,
        phone=payload.phone,
        email=str(payload.email) if payload.email else None,
        notes=payload.notes,
        avatar_bg=payload.avatar_bg or "#1a4020",
        avatar_text=payload.avatar_text or "#a8d5ad",
    )
    db.add(partner)
    db.commit()
    db.refresh(partner)

    # Backfill partner_id on any existing investment_partner rows with matching name
    _backfill_partner_id(db, user_id, partner)

    return partner


def _backfill_partner_id(db: Session, user_id: int, partner: Partner) -> None:
    """
    When a new partner profile is registered, link it to any existing
    InvestmentPartner slots that have the same name (case-insensitive).
    This handles the common flow of adding investments first, then later
    formalising the partner entry.
    """
    slots = (
        db.query(InvestmentPartner)
        .join(Investment, InvestmentPartner.investment_id == Investment.id)
        .filter(
            Investment.user_id == user_id,
            InvestmentPartner.partner_name.ilike(partner.name),
            InvestmentPartner.partner_id == None,  # noqa: E711
        )
        .all()
    )
    for slot in slots:
        slot.partner_id = partner.id
    if slots:
        db.commit()


def list_partners(user_id: int, db: Session) -> list[Partner]:
    return (
        db.query(Partner)
        .filter(Partner.user_id == user_id, Partner.is_active == True)
        .order_by(Partner.name)
        .all()
    )


def get_partner(partner_id: int, user_id: int, db: Session) -> Partner:
    return _get_or_404(db, user_id, partner_id)


def update_partner(
    partner_id: int,
    user_id: int,
    payload: PartnerUpdateRequest,
    db: Session,
) -> Partner:
    partner = _get_or_404(db, user_id, partner_id)

    if payload.name is not None:
        # Check name conflict (excluding self)
        conflict = (
            db.query(Partner)
            .filter(
                Partner.user_id == user_id,
                Partner.name.ilike(payload.name),
                Partner.id != partner_id,
                Partner.is_active == True,
            )
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another partner named '{payload.name}' already exists.",
            )
        partner.name = payload.name.strip()

    if payload.role        is not None: partner.role        = payload.role
    if payload.phone       is not None: partner.phone       = payload.phone
    if payload.email       is not None: partner.email       = str(payload.email)
    if payload.notes       is not None: partner.notes       = payload.notes
    if payload.avatar_bg   is not None: partner.avatar_bg   = payload.avatar_bg
    if payload.avatar_text is not None: partner.avatar_text = payload.avatar_text

    db.commit()
    db.refresh(partner)
    return partner


def delete_partner(partner_id: int, user_id: int, db: Session) -> None:
    partner = _get_or_404(db, user_id, partner_id)
    partner.is_active = False   # soft delete
    db.commit()


# ── Partner detail with investment stats ──────────────────────────────────────

def get_partner_detail(partner_id: int, user_id: int, db: Session) -> PartnerDetail:
    """Return full partner card including aggregated investment stats."""
    partner = _get_or_404(db, user_id, partner_id)

    slots = (
        db.query(InvestmentPartner)
        .join(Investment, InvestmentPartner.investment_id == Investment.id)
        .options(selectinload(InvestmentPartner.investment))
        .filter(
            Investment.user_id == user_id,
            InvestmentPartner.partner_name.ilike(partner.name),
            Investment.is_active == True,
        )
        .all()
    )

    deals: list[PartnerDealRow] = []
    total_invested = Decimal("0")
    total_returned = Decimal("0")

    for slot in slots:
        inv = slot.investment
        cap = (slot.percentage / 100) * inv.total_amount
        ret = (slot.percentage / 100) * inv.received_amount if inv.received_amount else Decimal("0")
        total_invested += cap
        total_returned += ret
        deals.append(PartnerDealRow(
            investment_id=inv.id,
            investment_name=inv.name,
            percentage=slot.percentage,
            capital_amount=cap,
            returned_amount=ret,
            pnl=ret - cap,
            status=inv.status,
        ))

    return PartnerDetail(
        id=partner.id,
        name=partner.name,
        role=partner.role,
        phone=partner.phone,
        email=partner.email,
        notes=partner.notes,
        avatar_bg=partner.avatar_bg,
        avatar_text=partner.avatar_text,
        is_active=partner.is_active,
        created_at=partner.created_at,
        updated_at=partner.updated_at,
        total_invested=total_invested,
        total_returned=total_returned,
        pnl=total_returned - total_invested,
        deal_count=len(deals),
        deals=deals,
    )
