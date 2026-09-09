"""
app/core/rate_limit.py

Shared rate limiter for public, unauthenticated routes. Confirmed consumer:
    app/api/beach.py -> "from app.core.rate_limit import limiter" (Module 19 — public
    beach/risk/forecast/alerts endpoints, no auth required, so must be rate-limited to
    prevent abuse per that file's own header comment).

Requires: pip install slowapi (add to backend/requirements.txt — not present in the
original merged list, genuinely missing dependency, flagging it here rather than silently
adding to A4 without you seeing it).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])