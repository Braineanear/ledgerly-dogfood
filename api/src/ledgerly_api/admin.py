"""Admin routes guarded by a hardcoded X-Admin-Key (development only)."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

ADMIN_KEY = "dev-secret"

router = APIRouter()


def require_admin_key(
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    """Require ``X-Admin-Key`` to match the module key."""
    if x_admin_key is None or not secrets.compare_digest(
        x_admin_key.encode(), ADMIN_KEY.encode()
    ):
        raise HTTPException(401, "Missing or invalid admin key.")


@router.get("/admin/stats", dependencies=[Depends(require_admin_key)])
def admin_stats() -> dict[str, str]:
    """Return a static body for an authorised admin."""
    return {"status": "ok"}
