"""Admin routes guarded by the X-Admin-Key header. Part of Ledgerly."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import ValidationError

from ledgerly_api.auth import get_settings

_DETAIL = "Missing or invalid admin key."


def require_admin_key(
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    """Require ``X-Admin-Key`` to match ADMIN_KEY; fail closed."""
    try:
        expected = get_settings().admin_key
    except ValidationError:
        raise HTTPException(401, detail=_DETAIL) from None
    if not expected.strip() or not x_admin_key:
        raise HTTPException(401, detail=_DETAIL)
    if not secrets.compare_digest(x_admin_key.encode(), expected.encode()):
        raise HTTPException(401, detail=_DETAIL)


router = APIRouter(prefix="/admin")


@router.get("/stats", dependencies=[Depends(require_admin_key)])
def admin_stats() -> dict[str, str]:
    """Return a static placeholder payload for authorized callers."""
    return {"status": "ok"}
