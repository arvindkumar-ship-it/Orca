"""
app/core/exceptions.py

Domain-level exceptions raised by service-layer functions. Routers catch these and translate
them to the correct HTTP status code (see the `_handle()` pattern used in trips.py, incidents.py,
emergency_share.py, notifications.py, admin.py — all of them import exactly these three names).

Confirmed via grep across every copied module:
    from app.core.exceptions import NotFoundError, ValidationError, ForbiddenError
"""


class AppError(Exception):
    """Base class for all domain exceptions. Never raised directly."""


class NotFoundError(AppError):
    """Raised when a requested entity (trip, incident, beach, etc.) does not exist
    or does not belong to the requesting user. Routers map this to HTTP 404."""


class ValidationError(AppError):
    """Raised when input is well-formed but semantically invalid (e.g. OTP expired,
    booking window closed, geometry invalid). Routers map this to HTTP 422."""


class ForbiddenError(AppError):
    """Raised when the actor is authenticated but not authorized for this action
    (e.g. non-admin calling an admin-only risk-rule tuning endpoint). Routers map
    this to HTTP 403."""