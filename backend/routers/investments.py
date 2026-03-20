"""
Thin wrapper so `backend/main.py` can include investment routes.

Canonical router is in `backend/handles/investments.py`.
"""

from handles.investments import router

__all__ = ["router"]

