# ── schemas.py ───────────────────────────────────────────────────────────────
# Pydantic v2 request/response schemas for all Verdant resources.
# Rule: request schemas validate user input; response schemas shape API output.
# Business logic stays in services — nothing DB-touching here.

import re
from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


# ═════════════════════════════════════════════════════════════════════════════
# SHARED / UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

class MessageResponse(BaseModel):
    message: str


_PASSWORD_MIN = 8

def _validate_password(v: str) -> str:
    if len(v) < _PASSWORD_MIN:
        raise ValueError(f"Password must be at least {_PASSWORD_MIN} characters.")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[0-9]", v):
        raise ValueError("Password must contain at least one digit.")
    return v


# ═════════════════════════════════════════════════════════════════════════════
# AUTH
# ═════════════════════════════════════════════════════════════════════════════

class RegisterRequest(BaseModel):
    first_name: str      = Field(..., min_length=1, max_length=100)
    last_name:  str      = Field(..., min_length=1, max_length=100)
    email:      EmailStr
    password:   str      = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password:     str

    @field_validator("new_password")
    @classmethod
    def strong_new(cls, v: str) -> str:
        return _validate_password(v)


class UserUpdateRequest(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name:  Optional[str] = Field(None, min_length=1, max_length=100)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:          int
    first_name:  str
    last_name:   str
    email:       str
    is_active:   bool
    is_verified: bool
    created_at:  datetime


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int


class RegisterResponse(BaseModel):
    message: str = "Registration successful."
    user:    UserResponse


class LoginResponse(BaseModel):
    message: str = "Login successful."
    user:    UserResponse
    tokens:  TokenResponse


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully."


class SessionInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:         int
    user_agent: Optional[str]
    ip_address: Optional[str]
    created_at: datetime
    expires_at: datetime
    revoked:    bool


# ═════════════════════════════════════════════════════════════════════════════
# PARTNER
# ═════════════════════════════════════════════════════════════════════════════

class PartnerCreateRequest(BaseModel):
    name:        str            = Field(..., min_length=1, max_length=200)
    role:        Optional[str]  = Field(None, max_length=150)
    phone:       Optional[str]  = Field(None, max_length=50)
    email:       Optional[EmailStr] = None
    notes:       Optional[str]  = None
    avatar_bg:   Optional[str]  = Field(None, max_length=20, examples=["#1a4020"])
    avatar_text: Optional[str]  = Field(None, max_length=20, examples=["#a8d5ad"])

    @field_validator("name")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class PartnerUpdateRequest(BaseModel):
    name:        Optional[str]      = Field(None, min_length=1, max_length=200)
    role:        Optional[str]      = Field(None, max_length=150)
    phone:       Optional[str]      = Field(None, max_length=50)
    email:       Optional[EmailStr] = None
    notes:       Optional[str]      = None
    avatar_bg:   Optional[str]      = Field(None, max_length=20)
    avatar_text: Optional[str]      = Field(None, max_length=20)


class PartnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:          int
    name:        str
    role:        Optional[str]
    phone:       Optional[str]
    email:       Optional[str]
    notes:       Optional[str]
    avatar_bg:   Optional[str]
    avatar_text: Optional[str]
    is_active:   bool
    created_at:  datetime
    updated_at:  datetime


class PartnerSummary(BaseModel):
    """Lightweight partner reference embedded inside investment responses."""
    model_config = ConfigDict(from_attributes=True)
    id:          int
    name:        str
    avatar_bg:   Optional[str]
    avatar_text: Optional[str]


# ═════════════════════════════════════════════════════════════════════════════
# INVESTMENT PARTNER  (slot inside an investment)
# ═════════════════════════════════════════════════════════════════════════════

class InvestmentPartnerInput(BaseModel):
    """
    Used when creating or updating an investment.
    Either partner_id (registered) or partner_name (ad-hoc) must be given.
    """
    partner_name: str     = Field(..., min_length=1, max_length=200)
    partner_id:   Optional[int]     = None
    percentage:   Decimal = Field(..., gt=0, le=100, decimal_places=2)

    @field_validator("partner_name")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class InvestmentPartnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:            int
    partner_id:    Optional[int]
    partner_name:  str
    percentage:    Decimal
    display_order: int
    # computed (set by service, not ORM column)
    capital_amount:  Optional[Decimal] = None
    returned_amount: Optional[Decimal] = None
    pnl:             Optional[Decimal] = None


# ═════════════════════════════════════════════════════════════════════════════
# INVESTMENT
# ═════════════════════════════════════════════════════════════════════════════

VALID_CATEGORIES = Literal["real-estate", "stocks", "business", "commodities", "other"]


class InvestmentCreateRequest(BaseModel):
    name:       str                   = Field(..., min_length=1, max_length=300)
    category:   VALID_CATEGORIES      = "other"
    deal_date:  Optional[datetime]    = None
    notes:      Optional[str]         = None
    total_amount: Decimal             = Field(..., gt=0, decimal_places=2)
    received_amount: Decimal          = Field(Decimal("0"), ge=0, decimal_places=2)
    partners:   List[InvestmentPartnerInput] = Field(..., min_length=1)

    @field_validator("name")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def partners_sum_to_100(self) -> "InvestmentCreateRequest":
        total = sum(p.percentage for p in self.partners)
        if abs(total - Decimal("100")) > Decimal("0.01"):
            raise ValueError(
                f"Partner percentages must sum to 100 (got {total})."
            )
        # Check unique names
        names = [p.partner_name.lower() for p in self.partners]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate partner names in the same investment.")
        return self


class InvestmentUpdateRequest(BaseModel):
    """
    All fields optional — PATCH semantics.
    If partners is supplied it replaces the entire partner list.
    """
    name:            Optional[str]             = Field(None, min_length=1, max_length=300)
    category:        Optional[VALID_CATEGORIES] = None
    deal_date:       Optional[datetime]         = None
    notes:           Optional[str]              = None
    total_amount:    Optional[Decimal]          = Field(None, gt=0)
    partners:        Optional[List[InvestmentPartnerInput]] = None

    @model_validator(mode="after")
    def partners_sum_to_100(self) -> "InvestmentUpdateRequest":
        if self.partners is not None:
            total = sum(p.percentage for p in self.partners)
            if abs(total - Decimal("100")) > Decimal("0.01"):
                raise ValueError(
                    f"Partner percentages must sum to 100 (got {total})."
                )
            names = [p.partner_name.lower() for p in self.partners]
            if len(names) != len(set(names)):
                raise ValueError("Duplicate partner names in the same investment.")
        return self


class UpdateReceivedRequest(BaseModel):
    """Used by the 'Edit received amount' button in the dashboard."""
    received_amount: Decimal = Field(..., ge=0, decimal_places=2)
    note:            Optional[str] = Field(None, max_length=500)


class InvestmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:              int
    name:            str
    category:        str
    deal_date:       Optional[datetime]
    notes:           Optional[str]
    total_amount:    Decimal
    received_amount: Decimal
    pnl:             Decimal
    status:          str                        # pending | partial | settled
    is_active:       bool
    created_at:      datetime
    updated_at:      datetime
    # Use a factory to avoid shared mutable defaults across requests.
    partners:        List[InvestmentPartnerResponse] = Field(default_factory=list)


class InvestmentListItem(BaseModel):
    """Lighter response used in list endpoints (no partner breakdown)."""
    model_config = ConfigDict(from_attributes=True)
    id:              int
    name:            str
    category:        str
    deal_date:       Optional[datetime]
    total_amount:    Decimal
    received_amount: Decimal
    pnl:             Decimal
    status:          str
    partner_count:   int
    created_at:      datetime


# ═════════════════════════════════════════════════════════════════════════════
# RETURN EVENT
# ═════════════════════════════════════════════════════════════════════════════

class ReturnEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:                       int
    investment_id:            int
    investment_name_snapshot: str
    previous_amount:          Decimal
    new_amount:               Decimal
    delta:                    Decimal
    note:                     Optional[str]
    recorded_by:              int
    created_at:               datetime


# ═════════════════════════════════════════════════════════════════════════════
# LEDGER  (read-only aggregated views)
# ═════════════════════════════════════════════════════════════════════════════

class LedgerPartnerRow(BaseModel):
    """Per-partner breakdown row inside a ledger investment entry."""
    partner_name:    str
    partner_id:      Optional[int]
    percentage:      Decimal
    capital_amount:  Decimal
    returned_amount: Decimal
    pnl:             Decimal


class LedgerEntry(BaseModel):
    """One row in the main ledger table — one investment + its partner breakdown."""
    model_config = ConfigDict(from_attributes=True)
    id:              int
    name:            str
    category:        str
    deal_date:       Optional[datetime]
    total_amount:    Decimal
    received_amount: Decimal
    pnl:             Decimal
    status:          str
    created_at:      datetime
    updated_at:      datetime
    partners:        List[LedgerPartnerRow]
    return_events:   List[ReturnEventResponse]


class LedgerSummary(BaseModel):
    """Aggregate numbers shown in the ledger stat cards."""
    total_capital:    Decimal
    total_returned:   Decimal
    net_pnl:          Decimal
    settled_count:    int
    partial_count:    int
    pending_count:    int
    total_deals:      int
    pending_capital:  Decimal  # capital in deals with no returns yet


class PartnerLeaderboardEntry(BaseModel):
    partner_name:    str
    partner_id:      Optional[int]
    avatar_bg:       Optional[str]
    avatar_text:     Optional[str]
    total_invested:  Decimal
    total_returned:  Decimal
    pnl:             Decimal
    deal_count:      int


class CategoryBreakdown(BaseModel):
    category:    str
    total:       Decimal
    percentage:  Decimal   # share of grand total


class LedgerDashboard(BaseModel):
    """All data the ledger page needs in one response."""
    summary:             LedgerSummary
    entries:             List[LedgerEntry]
    partner_leaderboard: List[PartnerLeaderboardEntry]
    category_breakdown:  List[CategoryBreakdown]
    recent_events:       List[ReturnEventResponse]


# ═════════════════════════════════════════════════════════════════════════════
# PARTNER STATS  (used on the Partners page)
# ═════════════════════════════════════════════════════════════════════════════

class PartnerDealRow(BaseModel):
    investment_id:   int
    investment_name: str
    percentage:      Decimal
    capital_amount:  Decimal
    returned_amount: Decimal
    pnl:             Decimal
    status:          str


class PartnerDetail(BaseModel):
    """Full partner card with all linked investment stats."""
    model_config = ConfigDict(from_attributes=True)
    id:             int
    name:           str
    role:           Optional[str]
    phone:          Optional[str]
    email:          Optional[str]
    notes:          Optional[str]
    avatar_bg:      Optional[str]
    avatar_text:    Optional[str]
    is_active:      bool
    created_at:     datetime
    updated_at:     datetime
    total_invested: Decimal
    total_returned: Decimal
    pnl:            Decimal
    deal_count:     int
    deals:          List[PartnerDealRow]


class PartnerDirectorySummary(BaseModel):
    """Aggregate stats for the Partners page header cards."""
    total_partners:   int
    total_invested:   Decimal
    total_returned:   Decimal
    avg_deal_share:   Optional[Decimal]
