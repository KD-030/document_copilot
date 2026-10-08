import asyncio
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from supabase_auth.errors import AuthApiError

from app.auth import dependencies


class FakeAuth:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.token = None
        self.closed = False

    async def get_user(self, token):
        self.token = token
        if self.error:
            raise self.error
        return self.response

    async def close(self):
        self.closed = True


class FakeQuery:
    def __init__(self):
        self.values = None
        self.conflict = None

    def upsert(self, values, on_conflict):
        self.values = values
        self.conflict = on_conflict
        return self

    def execute(self):
        return None


class FakeServiceClient:
    def __init__(self):
        self.query = FakeQuery()

    def table(self, table_name):
        assert table_name == "users"
        return self.query


class FakeUserClient:
    def __init__(self, response=None, error=None):
        self.auth = FakeAuth(response=response, error=error)
        self.postgrest = SimpleNamespace(aclose=self._close_postgrest)
        self.postgrest_closed = False

    async def _close_postgrest(self):
        self.postgrest_closed = True


def consume_dependency(credentials):
    async def consume():
        dependency = dependencies.get_current_user(credentials)
        try:
            return await anext(dependency)
        finally:
            await dependency.aclose()

    return asyncio.run(consume())


def test_get_current_user_verifies_and_provisions_user(monkeypatch):
    user_id = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
    response = SimpleNamespace(
        user=SimpleNamespace(id=user_id, email="analyst@gmail.com")
    )
    user_client = FakeUserClient(response=response)
    service_client = FakeServiceClient()
    monkeypatch.setattr(
        dependencies,
        "create_user_scoped_client",
        lambda token: _return_client(user_client, token),
    )
    monkeypatch.setattr(dependencies, "get_service_role_client", lambda: service_client)

    user = consume_dependency(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")
    )

    assert user.id == UUID(user_id)
    assert user.email == "analyst@gmail.com"
    assert user.supabase is user_client
    assert user_client.auth.token == "valid-token"
    assert service_client.query.values == {
        "id": user_id,
        "email": "analyst@gmail.com",
    }
    assert service_client.query.conflict == "id"
    assert user_client.auth.closed
    assert user_client.postgrest_closed


def test_get_current_user_rejects_unapproved_email_domain(monkeypatch):
    user_client = FakeUserClient(
        response=SimpleNamespace(
            user=SimpleNamespace(
                id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                email="analyst@external.example",
            )
        )
    )
    monkeypatch.setattr(
        dependencies,
        "create_user_scoped_client",
        lambda token: _return_client(user_client, token),
    )

    with pytest.raises(HTTPException) as error:
        consume_dependency(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")
        )

    assert error.value.status_code == 403
    assert user_client.auth.closed
    assert user_client.postgrest_closed


def test_get_current_user_rejects_invalid_token(monkeypatch):
    user_client = FakeUserClient(
        error=AuthApiError("invalid token", status=401, code="bad_jwt")
    )
    monkeypatch.setattr(
        dependencies,
        "create_user_scoped_client",
        lambda token: _return_client(user_client, token),
    )

    with pytest.raises(HTTPException) as error:
        consume_dependency(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")
        )

    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}
    assert user_client.auth.closed
    assert user_client.postgrest_closed


def test_get_current_user_requires_bearer_token():
    with pytest.raises(HTTPException) as error:
        consume_dependency(None)

    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


async def _return_client(client, token):
    assert token
    return client
