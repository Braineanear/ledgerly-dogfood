"""Users and per-tenant memberships. Part of Ledgerly.

The admin-key routes provision users and bootstrap tenant admins. The tenant
routes use ``require_role`` and the per-user ``X-User-Token`` credential.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from ledgerly_shared.orm import AppUser, Tenant, TenantMembership
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledgerly_api.admin import require_admin_key
from ledgerly_api.auth import require_token
from ledgerly_api.db import get_session
from ledgerly_api.problems import problem_response
from ledgerly_api.roles import (
    FORBIDDEN_RESPONSE,
    hash_token,
    new_token,
    require_role,
    require_user,
)
from ledgerly_api.tenants import Problem

SessionDep = Annotated[Session, Depends(get_session)]

Role = Literal["admin", "member"]

NOT_FOUND_RESPONSE = {
    404: {
        "model": Problem,
        "content": {"application/problem+json": {}},
    }
}

admin_router = APIRouter(
    prefix="/admin", dependencies=[Depends(require_admin_key)]
)
router = APIRouter(dependencies=[Depends(require_token)])


class UserCreate(BaseModel):
    """Request body for creating a user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)


class UserCreated(BaseModel):
    """A new user; ``token`` is shown once and only its hash is stored."""

    id: int
    name: str
    token: str


class MemberSet(BaseModel):
    """Request body for setting a member's role."""

    role: Role


class MemberRead(BaseModel):
    """A tenant membership as returned by the API."""

    user_id: int
    name: str
    role: str


def _not_found(request: Request, what: str, key: int):
    return problem_response(
        request, 404, f"{what} {key} was not found.", title="Not Found"
    )


def _upsert(
    session: Session, tenant_id: int, user: AppUser, role: str
) -> MemberRead:
    """Create or update the membership; retry once on a racing insert."""
    for attempt in range(2):
        membership = session.scalar(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user.id,
            )
        )
        if membership is None:
            membership = TenantMembership(
                tenant_id=tenant_id, user_id=user.id, role=role
            )
            session.add(membership)
        else:
            membership.role = role
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            if attempt:
                raise
            continue
        break
    return MemberRead(user_id=user.id, name=user.name, role=role)


def require_tenant(tenant_id: int, session: SessionDep) -> None:
    """404 for an unknown tenant, before the role check can answer 403."""
    if session.get(Tenant, tenant_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Tenant {tenant_id} was not found."
        )


@admin_router.post("/users", status_code=201, response_model=UserCreated)
def create_user(body: UserCreate, session: SessionDep) -> UserCreated:
    """Create a user and return its token exactly once."""
    token = new_token()
    user = AppUser(name=body.name, token_hash=hash_token(token))
    session.add(user)
    session.commit()
    return UserCreated(id=user.id, name=user.name, token=token)


@admin_router.put(
    "/tenants/{tenant_id}/members/{user_id}",
    response_model=MemberRead,
    responses=NOT_FOUND_RESPONSE,
)
def admin_set_member(
    request: Request,
    tenant_id: int,
    user_id: int,
    body: MemberSet,
    session: SessionDep,
):
    """Upsert a membership; the bootstrap path for tenant admins."""
    if session.get(Tenant, tenant_id) is None:
        return _not_found(request, "Tenant", tenant_id)
    user = session.get(AppUser, user_id)
    if user is None:
        return _not_found(request, "User", user_id)
    return _upsert(session, tenant_id, user, body.role)


@router.get(
    "/tenants/{tenant_id}/members",
    response_model=list[MemberRead],
    responses={**FORBIDDEN_RESPONSE, **NOT_FOUND_RESPONSE},
    dependencies=[
        Depends(require_user),
        Depends(require_tenant),
        Depends(require_role("admin", "member")),
    ],
)
def list_members(tenant_id: int, session: SessionDep) -> list[MemberRead]:
    """List the tenant's members; allowed for admin and member."""
    rows = session.execute(
        select(TenantMembership.user_id, AppUser.name, TenantMembership.role)
        .join(AppUser, AppUser.id == TenantMembership.user_id)
        .where(TenantMembership.tenant_id == tenant_id)
        .order_by(TenantMembership.user_id)
    )
    return [
        MemberRead(user_id=uid, name=name, role=role)
        for uid, name, role in rows
    ]


@router.put(
    "/tenants/{tenant_id}/members/{user_id}",
    response_model=MemberRead,
    responses={**FORBIDDEN_RESPONSE, **NOT_FOUND_RESPONSE},
    dependencies=[
        Depends(require_user),
        Depends(require_tenant),
        Depends(require_role("admin")),
    ],
)
def set_member(
    request: Request,
    tenant_id: int,
    user_id: int,
    body: MemberSet,
    session: SessionDep,
):
    """Upsert a membership; admin only."""
    user = session.get(AppUser, user_id)
    if user is None:
        return _not_found(request, "User", user_id)
    return _upsert(session, tenant_id, user, body.role)
