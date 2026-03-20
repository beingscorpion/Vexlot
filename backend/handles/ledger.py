# ── routers/ledger.py ────────────────────────────────────────────────────────
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_active_user
from models import User
from schemas import LedgerDashboard, ReturnEventResponse
from services import ledger_service

router = APIRouter(prefix="/ledger", tags=["Ledger"])


# ── GET /ledger ───────────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=LedgerDashboard,
    summary="Full ledger dashboard — all data the Ledger page needs",
)
def get_ledger(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Returns in one call:
    - `summary`              — 5 aggregate stat-card values
    - `entries`              — all investments with per-partner P&L breakdown + return events
    - `partner_leaderboard`  — partners ranked by total capital deployed
    - `category_breakdown`   — capital split by category with % shares
    - `recent_events`        — last 10 return events across all investments
    """
    return ledger_service.get_ledger_dashboard(current_user.id, db)


# ── GET /ledger/events ────────────────────────────────────────────────────────
@router.get(
    "/events",
    response_model=List[ReturnEventResponse],
    summary="Return-event audit trail (optionally filtered by investment)",
)
def get_events(
    investment_id: Optional[int] = Query(None, description="Filter to one investment"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Immutable audit log of every time a received_amount was edited.
    Pass `?investment_id=<id>` to scope to a single deal.
    """
    return ledger_service.get_return_events(current_user.id, investment_id, db)
