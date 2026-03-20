# ── routers/partners.py ──────────────────────────────────────────────────────
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_active_user
from models import User
from schemas import (
    MessageResponse,
    PartnerCreateRequest,
    PartnerDetail,
    PartnerDirectorySummary,
    PartnerResponse,
    PartnerUpdateRequest,
)
from services import partner_service, investment_service
from decimal import Decimal

router = APIRouter(prefix="/partners", tags=["Partners"])


# ── POST /partners ────────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=PartnerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new partner profile",
)
def create_partner(
    payload: PartnerCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    partner = partner_service.create_partner(payload, current_user.id, db)
    return PartnerResponse.model_validate(partner)


# ── GET /partners ─────────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=List[PartnerResponse],
    summary="List all registered partner profiles",
)
def list_partners(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    partners = partner_service.list_partners(current_user.id, db)
    return [PartnerResponse.model_validate(p) for p in partners]


# ── GET /partners/summary ─────────────────────────────────────────────────────
@router.get(
    "/summary",
    response_model=PartnerDirectorySummary,
    summary="Aggregate stats for the Partners page header cards",
)
def get_directory_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Returns total partner count, combined invested/returned, and avg deal share.
    Includes both registered partners and ad-hoc names from investments.
    """
    investments = investment_service.list_investments(current_user.id, db)

    all_names: set[str] = set()
    total_invested  = Decimal("0")
    total_returned  = Decimal("0")
    pct_values: list[Decimal] = []

    for inv in investments:
        for slot in inv.partners:
            all_names.add(slot.partner_name.lower())
            cap = (slot.percentage / 100) * inv.total_amount
            ret = (slot.percentage / 100) * inv.received_amount
            total_invested += cap
            total_returned += ret
            pct_values.append(slot.percentage)

    # Also count registered partners with no investments yet
    registered = partner_service.list_partners(current_user.id, db)
    for p in registered:
        all_names.add(p.name.lower())

    avg = (sum(pct_values) / len(pct_values)) if pct_values else None

    return PartnerDirectorySummary(
        total_partners=len(all_names),
        total_invested=total_invested,
        total_returned=total_returned,
        avg_deal_share=avg,
    )


# ── GET /partners/{id} ────────────────────────────────────────────────────────
@router.get(
    "/{partner_id}",
    response_model=PartnerDetail,
    summary="Full partner card with linked investment stats",
)
def get_partner(
    partner_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return partner_service.get_partner_detail(partner_id, current_user.id, db)


# ── PATCH /partners/{id} ──────────────────────────────────────────────────────
@router.patch(
    "/{partner_id}",
    response_model=PartnerResponse,
    summary="Update a partner profile",
)
def update_partner(
    partner_id: int,
    payload: PartnerUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    partner = partner_service.update_partner(partner_id, current_user.id, payload, db)
    return PartnerResponse.model_validate(partner)


# ── DELETE /partners/{id} ─────────────────────────────────────────────────────
@router.delete(
    "/{partner_id}",
    response_model=MessageResponse,
    summary="Soft-delete a partner profile",
)
def delete_partner(
    partner_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    partner_service.delete_partner(partner_id, current_user.id, db)
    return MessageResponse(message="Partner removed.")
