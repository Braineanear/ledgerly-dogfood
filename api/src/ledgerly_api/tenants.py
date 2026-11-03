"""Tenant routes: create a tenant and fetch one by id."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from ledgerly_shared.orm import Tenant
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ledgerly_api.db import get_session

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


class TenantCreate(BaseModel):
    """Request body for creating a tenant."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)


class TenantCreated(BaseModel):
    """Response body returned after a tenant is created."""

    id: int


class TenantRead(BaseModel):
    """A tenant as returned by the API."""

    id: int
    name: str


class Problem(BaseModel):
    """An RFC 9457 problem details body."""

    type: str
    title: str
    status: int
    detail: str


@router.post("/tenants", status_code=201, response_model=TenantCreated)
def create_tenant(body: TenantCreate, session: SessionDep) -> TenantCreated:
    tenant = Tenant(name=body.name)
    session.add(tenant)
    session.commit()
    return TenantCreated(id=tenant.id)


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantRead,
    responses={
        404: {
            "model": Problem,
            "content": {"application/problem+json": {}},
        }
    },
)
def get_tenant(tenant_id: int, session: SessionDep):
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        problem = Problem(
            type="about:blank",
            title="Not Found",
            status=404,
            detail=f"Tenant {tenant_id} was not found.",
        )
        return JSONResponse(
            status_code=404,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )
    return TenantRead(id=tenant.id, name=tenant.name)
