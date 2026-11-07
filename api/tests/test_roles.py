"""Tests for per-tenant roles, using an in-memory SQLite database."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from ledgerly_shared.orm import AppUser, Base, Tenant, TenantMembership
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from alembic import command
from ledgerly_api.auth import get_settings
from ledgerly_api.db import get_session
from ledgerly_api.main import create_app
from ledgerly_api.members import _upsert

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "shared" / "alembic.ini"

ADMIN_KEY = "test-admin-key"
ADMIN = {"X-Admin-Key": ADMIN_KEY}


@dataclass
class Env:
    client: TestClient
    engine: Engine


@pytest.fixture(params=["create_all", "alembic"])
def env(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[Env]:
    """Run every test on both a metadata schema and one built by Alembic."""
    monkeypatch.setenv("API_TOKEN", "test-token")
    monkeypatch.setenv("ADMIN_KEY", ADMIN_KEY)
    get_settings.cache_clear()
    if request.param == "alembic":
        engine = create_engine(
            f"sqlite:///{tmp_path / 'roles.db'}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        config = Config(str(ALEMBIC_INI))
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
        assert version >= "0010"
    else:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)

    def override_session() -> Iterator[Session]:
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()

    application = create_app()
    application.dependency_overrides[get_session] = override_session
    with TestClient(
        application, headers={"Authorization": "Bearer test-token"}
    ) as test_client:
        yield Env(test_client, engine)
    engine.dispose()
    get_settings.cache_clear()


def make_user(env: Env, name: str = "ann") -> dict:
    response = env.client.post("/admin/users", json={"name": name}, headers=ADMIN)
    assert response.status_code == 201
    return response.json()


def make_tenant(env: Env, name: str = "Acme") -> int:
    response = env.client.post("/tenants", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def bootstrap(env: Env, tenant_id: int, user: dict, role: str) -> None:
    response = env.client.put(
        f"/admin/tenants/{tenant_id}/members/{user['id']}",
        json={"role": role},
        headers=ADMIN,
    )
    assert response.status_code == 200


def token(user: dict) -> dict:
    return {"X-User-Token": user["token"]}


def test_member_put_is_forbidden_problem_json(env: Env) -> None:
    tenant = make_tenant(env)
    member = make_user(env, "mia")
    target = make_user(env, "tom")
    bootstrap(env, tenant, member, "member")

    response = env.client.put(
        f"/tenants/{tenant}/members/{target['id']}",
        json={"role": "member"},
        headers=token(member),
    )

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == 403
    assert body["title"] == "Forbidden"


def test_non_member_is_forbidden(env: Env) -> None:
    tenant = make_tenant(env)
    outsider = make_user(env, "olga")

    listed = env.client.get(
        f"/tenants/{tenant}/members", headers=token(outsider)
    )
    put = env.client.put(
        f"/tenants/{tenant}/members/{outsider['id']}",
        json={"role": "admin"},
        headers=token(outsider),
    )

    assert listed.status_code == 403
    assert put.status_code == 403


def test_missing_user_token_is_unauthorized(env: Env) -> None:
    tenant = make_tenant(env)

    response = env.client.get(f"/tenants/{tenant}/members")

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"


def test_invalid_user_token_is_unauthorized(env: Env) -> None:
    tenant = make_tenant(env)

    response = env.client.get(
        f"/tenants/{tenant}/members", headers={"X-User-Token": "nope"}
    )

    assert response.status_code == 401


def test_empty_user_token_on_tenant_create_is_unauthorized(env: Env) -> None:
    response = env.client.post(
        "/tenants", json={"name": "Ghost"}, headers={"X-User-Token": ""}
    )

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    with Session(env.engine) as session:
        assert session.scalar(select(func.count()).select_from(Tenant)) == 0


def test_user_token_without_bearer_is_unauthorized(env: Env) -> None:
    tenant = make_tenant(env)
    admin = make_user(env)
    bootstrap(env, tenant, admin, "admin")
    del env.client.headers["Authorization"]

    response = env.client.get(
        f"/tenants/{tenant}/members", headers=token(admin)
    )

    assert response.status_code == 401


def test_extra_user_id_header_cannot_escalate(env: Env) -> None:
    tenant = make_tenant(env)
    admin = make_user(env, "root")
    member = make_user(env, "mia")
    bootstrap(env, tenant, admin, "admin")
    bootstrap(env, tenant, member, "member")

    response = env.client.put(
        f"/tenants/{tenant}/members/{member['id']}",
        json={"role": "admin"},
        headers={
            **token(member),
            "X-User-Id": str(admin["id"]),
            "X-User": admin["name"],
        },
    )

    assert response.status_code == 403


def test_admin_put_succeeds_and_role_is_persisted(env: Env) -> None:
    tenant = make_tenant(env)
    admin = make_user(env, "root")
    target = make_user(env, "tom")
    bootstrap(env, tenant, admin, "admin")

    response = env.client.put(
        f"/tenants/{tenant}/members/{target['id']}",
        json={"role": "member"},
        headers=token(admin),
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": target["id"],
        "name": "tom",
        "role": "member",
    }
    with Session(env.engine) as session:
        stored = session.scalar(
            select(TenantMembership.role).where(
                TenantMembership.tenant_id == tenant,
                TenantMembership.user_id == target["id"],
            )
        )
    assert stored == "member"


@pytest.mark.parametrize("role", ["admin", "member"])
def test_both_roles_can_list_members(env: Env, role: str) -> None:
    tenant = make_tenant(env)
    user = make_user(env)
    bootstrap(env, tenant, user, role)

    response = env.client.get(
        f"/tenants/{tenant}/members", headers=token(user)
    )

    assert response.status_code == 200
    assert response.json() == [
        {"user_id": user["id"], "name": "ann", "role": role}
    ]


def test_invalid_role_is_rejected(env: Env) -> None:
    tenant = make_tenant(env)
    admin = make_user(env)
    bootstrap(env, tenant, admin, "admin")

    via_admin = env.client.put(
        f"/tenants/{tenant}/members/{admin['id']}",
        json={"role": "owner"},
        headers=token(admin),
    )
    via_key = env.client.put(
        f"/admin/tenants/{tenant}/members/{admin['id']}",
        json={"role": "owner"},
        headers=ADMIN,
    )

    assert via_admin.status_code == 422
    assert via_key.status_code == 422


def test_unknown_tenant_is_not_found(env: Env) -> None:
    user = make_user(env)

    listed = env.client.get("/tenants/999/members", headers=token(user))
    put = env.client.put(
        f"/tenants/999/members/{user['id']}",
        json={"role": "member"},
        headers=token(user),
    )
    boot = env.client.put(
        f"/admin/tenants/999/members/{user['id']}",
        json={"role": "member"},
        headers=ADMIN,
    )

    for response in (listed, put, boot):
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"


def test_unknown_user_is_not_found(env: Env) -> None:
    tenant = make_tenant(env)
    admin = make_user(env)
    bootstrap(env, tenant, admin, "admin")

    response = env.client.put(
        f"/tenants/{tenant}/members/999",
        json={"role": "member"},
        headers=token(admin),
    )

    assert response.status_code == 404


def test_admin_key_bootstrap_requires_key(env: Env) -> None:
    tenant = make_tenant(env)
    user = make_user(env)

    missing = env.client.put(
        f"/admin/tenants/{tenant}/members/{user['id']}",
        json={"role": "admin"},
    )
    no_key_user = env.client.post("/admin/users", json={"name": "x"})

    assert missing.status_code == 401
    assert no_key_user.status_code == 401
    bootstrap(env, tenant, user, "admin")
    listed = env.client.get(f"/tenants/{tenant}/members", headers=token(user))
    assert listed.status_code == 200


def test_tenant_creation_with_token_makes_user_admin(env: Env) -> None:
    user = make_user(env)

    response = env.client.post(
        "/tenants", json={"name": "Owned"}, headers=token(user)
    )

    assert response.status_code == 201
    tenant = response.json()["id"]
    listed = env.client.get(f"/tenants/{tenant}/members", headers=token(user))
    assert listed.json() == [
        {"user_id": user["id"], "name": "ann", "role": "admin"}
    ]


def test_tenant_creation_with_invalid_token_creates_nothing(env: Env) -> None:
    response = env.client.post(
        "/tenants", json={"name": "Ghost"}, headers={"X-User-Token": "bad"}
    )

    assert response.status_code == 401
    assert env.client.get("/tenants/1").status_code == 404


def test_role_in_one_tenant_grants_nothing_in_another(env: Env) -> None:
    tenant_a = make_tenant(env, "A")
    tenant_b = make_tenant(env, "B")
    admin = make_user(env)
    bootstrap(env, tenant_a, admin, "admin")

    allowed = env.client.get(
        f"/tenants/{tenant_a}/members", headers=token(admin)
    )
    denied = env.client.get(
        f"/tenants/{tenant_b}/members", headers=token(admin)
    )
    denied_put = env.client.put(
        f"/tenants/{tenant_b}/members/{admin['id']}",
        json={"role": "admin"},
        headers=token(admin),
    )

    assert allowed.status_code == 200
    assert denied.status_code == 403
    assert denied_put.status_code == 403


def test_stored_token_is_hashed(env: Env) -> None:
    user = make_user(env)

    with Session(env.engine) as session:
        stored = session.scalar(
            select(AppUser.token_hash).where(AppUser.id == user["id"])
        )
    assert stored != user["token"]
    assert len(stored) == 64
    assert user["token"] not in stored


def test_upsert_retries_after_racing_insert(env: Env) -> None:
    """A competing insert lands between the lookup and the commit."""
    tenant = make_tenant(env)
    user = make_user(env)
    with Session(env.engine) as session:
        app_user = session.get(AppUser, user["id"])
        real_scalar = session.scalar
        lookups = []

        def racing_scalar(*args, **kwargs):
            lookups.append(1)
            if len(lookups) == 1:
                # The rival commits its membership after we saw nothing.
                with Session(env.engine) as rival:
                    rival.add(
                        TenantMembership(
                            tenant_id=tenant, user_id=user["id"], role="member"
                        )
                    )
                    rival.commit()
                return None
            return real_scalar(*args, **kwargs)

        session.scalar = racing_scalar
        result = _upsert(session, tenant, app_user, "admin")

    assert len(lookups) == 2
    assert result.role == "admin"
    with Session(env.engine) as session:
        roles = session.scalars(
            select(TenantMembership.role).where(
                TenantMembership.tenant_id == tenant,
                TenantMembership.user_id == user["id"],
            )
        ).all()
    assert roles == ["admin"]
