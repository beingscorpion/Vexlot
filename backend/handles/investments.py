# ── routers/investments.py ───────────────────────────────────────────────────
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_active_user
from models import User
from schemas import (
    InvestmentCreateRequest,
    InvestmentListItem,
    InvestmentResponse,
    InvestmentUpdateRequest,
    InvestmentPartnerResponse,
    MessageResponse,
    UpdateReceivedRequest,
)
from services import investment_service

router = APIRouter(prefix="/investments", tags=["Investments"])


def _to_response(inv) -> InvestmentResponse:
    """Convert ORM Investment to response schema, populating computed fields."""
    partner_responses = []
    for slot in sorted(inv.partners, key=lambda p: p.display_order):
        cap = (slot.percentage / 100) * inv.total_amount
        ret = (slot.percentage / 100) * inv.received_amount
        partner_responses.append(InvestmentPartnerResponse(
            id=slot.id,
            partner_id=slot.partner_id,
            partner_name=slot.partner_name,
            percentage=slot.percentage,
            display_order=slot.display_order,
            capital_amount=cap,
            returned_amount=ret,
            pnl=ret - cap,
        ))
    return InvestmentResponse(
        id=inv.id,
        name=inv.name,
        category=inv.category,
        deal_date=inv.deal_date,
        notes=inv.notes,
        total_amount=inv.total_amount,
        received_amount=inv.received_amount,
        pnl=inv.pnl,
        status=inv.status,
        is_active=inv.is_active,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        partners=partner_responses,
    )


# ── POST /investments ─────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=InvestmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new investment deal",
)
def create_investment(
    payload: InvestmentCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    inv = investment_service.create_investment(payload, current_user.id, db)
    return _to_response(inv)


# ── GET /investments ──────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=List[InvestmentListItem],
    summary="List all active investments",
)
def list_investments(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    investments = investment_service.list_investments(current_user.id, db)
    return [
        InvestmentListItem(
            id=inv.id,
            name=inv.name,
            category=inv.category,
            deal_date=inv.deal_date,
            total_amount=inv.total_amount,
            received_amount=inv.received_amount,
            pnl=inv.pnl,
            status=inv.status,
            partner_count=len(inv.partners),
            created_at=inv.created_at,
        )
        for inv in investments
    ]


# ── GET /investments/{id} ─────────────────────────────────────────────────────
@router.get(
    "/{inv_id}",
    response_model=InvestmentResponse,
    summary="Get a single investment with full partner breakdown",
)
def get_investment(
    inv_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    inv = investment_service.get_investment(inv_id, current_user.id, db)
    return _to_response(inv)


# ── PATCH /investments/{id} ───────────────────────────────────────────────────
@router.patch(
    "/{inv_id}",
    response_model=InvestmentResponse,
    summary="Update investment details and/or partner list",
)
def update_investment(
    inv_id: int,
    payload: InvestmentUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    inv = investment_service.update_investment(inv_id, current_user.id, payload, db)
    return _to_response(inv)


# ── PATCH /investments/{id}/received ─────────────────────────────────────────
@router.patch(
    "/{inv_id}/received",
    response_model=InvestmentResponse,
    summary="Update the received amount (logs a return event)",
)
def update_received(
    inv_id: int,
    payload: UpdateReceivedRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Updates `received_amount` on the investment and appends an immutable
    ReturnEvent record to the audit trail.
    """
    inv = investment_service.update_received(inv_id, current_user.id, payload, db)
    return _to_response(inv)


# ── DELETE /investments/{id} ──────────────────────────────────────────────────
@router.delete(
    "/{inv_id}",
    response_model=MessageResponse,
    summary="Soft-delete an investment",
)
def delete_investment(
    inv_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Soft-deletes the investment (sets is_active=False). Audit trail preserved."""
    investment_service.delete_investment(inv_id, current_user.id, db)
    return MessageResponse(message="Investment deleted.")
