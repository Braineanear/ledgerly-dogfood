"""Feature flags: list them and gate a route behind one."""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from ledgerly_shared.orm import FeatureFlag
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from ledgerly_api.auth import require_token
from ledgerly_api.tenants import Problem, SessionDep

router = APIRouter(prefix="/flags", tags=["flags"])

_PROBLEM_RESPONSE = {
    "model": Problem,
    "content": {"application/problem+json": {}},
}


class FlagRead(BaseModel):
    """A feature flag as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    enabled: bool


@router.get(
    "",
    response_model=list[FlagRead],
    dependencies=[Depends(require_token)],
    responses={401: _PROBLEM_RESPONSE},
)
def list_flags(session: SessionDep):
    return list(session.scalars(select(FeatureFlag).order_by(FeatureFlag.name)))


def require_flag(name: str) -> Callable[..., None]:
    """Return a dependency that passes only if flag ``name`` is enabled.

    The flag is read on every request. A missing row counts as off, and
    an off flag answers 404 so the gated route looks absent. Database
    errors are not caught: they surface as a 5xx.
    """

    def dependency(session: SessionDep) -> None:
        enabled = session.scalar(
            select(FeatureFlag.enabled).where(FeatureFlag.name == name)
        )
        if not enabled:
            raise HTTPException(status_code=404, detail="Not Found")

    return dependency
