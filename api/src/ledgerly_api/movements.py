"""Stock movement routes: record a movement, optionally idempotently."""

import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from ledgerly_shared.orm import IdempotencyKey, Tenant
from ledgerly_shared.stock import append_stock_movement
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledgerly_api.auth import require_token
from ledgerly_api.problems import problem_response
from ledgerly_api.tenants import Problem, SessionDep

router = APIRouter(dependencies=[Depends(require_token)])

MAX_ID = 2**63 - 1
# StockMovement.delta is a 32-bit Integer column.
MAX_QUANTITY = 2**31 - 1

_PROBLEM_RESPONSE = {
    "model": Problem,
    "content": {"application/problem+json": {}},
}


class MovementCreate(BaseModel):
    """Request body for recording a stock movement."""

    model_config = ConfigDict(str_strip_whitespace=True)

    product_id: int = Field(ge=1, le=MAX_ID)
    warehouse: str = Field(min_length=1, max_length=64)
    # A negative quantity is an outbound movement.
    quantity: int = Field(ge=-MAX_QUANTITY, le=MAX_QUANTITY)

    @field_validator("quantity")
    @classmethod
    def _non_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("quantity must not be zero")
        return value


class MovementRead(BaseModel):
    """A stock movement as returned by the API."""

    id: int
    product_id: int
    warehouse: str
    quantity: int


def _problem(request: Request, status: int, title: str, detail: str) -> JSONResponse:
    return problem_response(request, status, detail, title=title)


def _request_hash(body: MovementCreate) -> str:
    canonical = json.dumps(body.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _replay_or_conflict(
    request: Request, row: IdempotencyKey, request_hash: str
) -> JSONResponse:
    """Replay the stored response, or 409 if the key was used for another body."""
    if row.request_hash != request_hash:
        return _problem(
            request,
            409,
            "Conflict",
            "The Idempotency-Key was already used with a different request body.",
        )
    return JSONResponse(status_code=row.response_status, content=row.response_body)


def _find_key(session: Session, tenant_id: int, key: str) -> IdempotencyKey | None:
    return session.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.tenant_id == tenant_id,
            IdempotencyKey.key == key,
        )
    )


@router.post(
    "/tenants/{tenant_id}/movements",
    status_code=201,
    response_model=MovementRead,
    responses={
        401: _PROBLEM_RESPONSE,
        404: _PROBLEM_RESPONSE,
        409: _PROBLEM_RESPONSE,
        422: _PROBLEM_RESPONSE,
    },
)
def create_movement(
    request: Request,
    tenant_id: int,
    body: MovementCreate,
    session: SessionDep,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=1, max_length=255),
    ] = None,
):
    if session.get(Tenant, tenant_id) is None:
        return _problem(request, 404, "Not Found", f"Tenant {tenant_id} was not found.")

    request_hash = _request_hash(body)
    if idempotency_key is not None:
        existing = _find_key(session, tenant_id, idempotency_key)
        if existing is not None:
            return _replay_or_conflict(request, existing, request_hash)

    try:
        movement = append_stock_movement(
            session,
            tenant_id,
            body.product_id,
            body.warehouse,
            body.quantity,
        )
    except ValueError:
        session.rollback()
        return _problem(
            request,
            404,
            "Not Found",
            f"Product {body.product_id} was not found.",
        )
    # Build the response before the commit expires the instance.
    payload = MovementRead(
        id=movement.id,
        product_id=movement.product_id,
        warehouse=movement.warehouse,
        quantity=movement.delta,
    )
    if idempotency_key is None:
        session.commit()
        return payload

    session.add(
        IdempotencyKey(
            tenant_id=tenant_id,
            key=idempotency_key,
            request_hash=request_hash,
            response_status=201,
            response_body=payload.model_dump(),
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = _find_key(session, tenant_id, idempotency_key)
        if existing is None:
            # Not a duplicate key, so do not report it as one.
            raise
        return _replay_or_conflict(request, existing, request_hash)
    return payload
