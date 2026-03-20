# ── services/investment_service.py ───────────────────────────────────────────
from datetime import timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from models import Investment, InvestmentPartner, Partner, ReturnEvent
from schemas import (
    InvestmentCreateRequest,
    InvestmentUpdateRequest,
    UpdateReceivedRequest,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(db: Session, user_id: int, inv_id: int) -> Investment:
    inv = (
        db.query(Investment)
        .options(selectinload(Investment.partners), selectinload(Investment.return_events))
        .filter(Investment.id == inv_id, Investment.user_id == user_id, Investment.is_active == True)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment not found.")
    return inv


def _resolve_partner_id(db: Session, user_id: int, name: str) -> int | None:
    """Try to find a registered Partner matching the given name (case-insensitive)."""
    p = (
        db.query(Partner)
        .filter(Partner.user_id == user_id, Partner.name.ilike(name), Partner.is_active == True)
        .first()
    )
    return p.id if p else None


def _build_slots(
    db: Session,
    user_id: int,
    partner_inputs,
    investment_id: int,
) -> list[InvestmentPartner]:
    slots = []
    for order, pi in enumerate(partner_inputs):
        resolved_id = pi.partner_id or _resolve_partner_id(db, user_id, pi.partner_name)
        slots.append(InvestmentPartner(
            investment_id=investment_id,
            partner_id=resolved_id,
            partner_name=pi.partner_name,
            percentage=pi.percentage,
            display_order=order,
        ))
    return slots


# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_investment(payload: InvestmentCreateRequest, user_id: int, db: Session) -> Investment:
    inv = Investment(
        user_id=user_id,
        name=payload.name,
        category=payload.category,
        deal_date=payload.deal_date,
        notes=payload.notes,
        total_amount=payload.total_amount,
        received_amount=payload.received_amount,
    )
    db.add(inv)
    db.flush()  # populate inv.id before building slots

    slots = _build_slots(db, user_id, payload.partners, inv.id)
    db.add_all(slots)

    # If initial received_amount > 0, log a return event
    if payload.received_amount > 0:
        db.add(ReturnEvent(
            investment_id=inv.id,
            recorded_by=user_id,
            previous_amount=Decimal("0"),
            new_amount=payload.received_amount,
            delta=payload.received_amount,
            note="Initial amount set on creation.",
            investment_name_snapshot=inv.name,
        ))

    db.commit()
    db.refresh(inv)
    return inv


def list_investments(user_id: int, db: Session) -> list[Investment]:
    return (
        db.query(Investment)
        .options(selectinload(Investment.partners))
        .filter(Investment.user_id == user_id, Investment.is_active == True)
        .order_by(Investment.created_at.desc())
        .all()
    )


def get_investment(inv_id: int, user_id: int, db: Session) -> Investment:
    return _get_or_404(db, user_id, inv_id)


def update_investment(
    inv_id: int,
    user_id: int,
    payload: InvestmentUpdateRequest,
    db: Session,
) -> Investment:
    inv = _get_or_404(db, user_id, inv_id)

    if payload.name        is not None: inv.name        = payload.name
    if payload.category    is not None: inv.category    = payload.category
    if payload.deal_date   is not None: inv.deal_date   = payload.deal_date
    if payload.notes       is not None: inv.notes       = payload.notes
    if payload.total_amount is not None: inv.total_amount = payload.total_amount

    # Replace partner list if supplied
    if payload.partners is not None:
        for slot in list(inv.partners):
            db.delete(slot)
        db.flush()
        slots = _build_slots(db, user_id, payload.partners, inv.id)
        db.add_all(slots)

    db.commit()
    db.refresh(inv)
    return inv


def update_received(
    inv_id: int,
    user_id: int,
    payload: UpdateReceivedRequest,
    db: Session,
) -> Investment:
    inv = _get_or_404(db, user_id, inv_id)
    previous = inv.received_amount

    if previous == payload.received_amount:
        return inv  # nothing to do

    inv.received_amount = payload.received_amount

    # Append immutable audit record
    db.add(ReturnEvent(
        investment_id=inv.id,
        recorded_by=user_id,
        previous_amount=previous,
        new_amount=payload.received_amount,
        delta=payload.received_amount - previous,
        note=payload.note,
        investment_name_snapshot=inv.name,
    ))

    db.commit()
    db.refresh(inv)
    return inv


def delete_investment(inv_id: int, user_id: int, db: Session) -> None:
    inv = _get_or_404(db, user_id, inv_id)
    inv.is_active = False   # soft delete — preserves audit trail
    db.commit()
