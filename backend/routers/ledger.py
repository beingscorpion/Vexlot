"""
Thin wrapper so `backend/main.py` can include ledger routes.

Canonical router is in `backend/handles/ledger.py`.
"""

from handles.ledger import router

__all__ = ["router"]

