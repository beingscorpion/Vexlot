"""
Thin wrapper so `backend/main.py` can include partner routes.

Canonical router is in `backend/handles/partners.py`.
"""

from handles.partners import router

__all__ = ["router"]

