import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from postgrest.exceptions import APIError
from supabase import AsyncClient
from supabase_auth.errors import AuthApiError, AuthRetryableError

from app.config import settings
from app.database.supabase import create_user_scoped_client, get_service_role_client

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Verified Supabase identity and request-scoped user database client."""

    id: UUID
    email: str
    supabase: AsyncClient


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AsyncIterator[AuthenticatedUser]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    client = await create_user_scoped_client(credentials.credentials)
    try:
        try:
            response = await client.auth.get_user(credentials.credentials)
        except AuthApiError as exc:
            if exc.status in {400, 401, 403}:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired bearer token",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Supabase Auth is unavailable",
            ) from exc
        except (AuthRetryableError, httpx.RequestError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Supabase Auth is unavailable",
            ) from exc

        user = response.user if response else None
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if user.email is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An email address is required",
            )
        email_domain = user.email.rpartition("@")[2].lower()
        if email_domain not in settings.parsed_allowed_email_domains:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This email domain is not authorized",
            )

        try:
            await asyncio.to_thread(
                lambda: (
                    get_service_role_client()
                    .table("users")
                    .upsert(
                        {"id": user.id, "email": user.email},
                        on_conflict="id",
                    )
                    .execute()
                )
            )
        except APIError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to provision authenticated user",
            ) from exc

        yield AuthenticatedUser(
            id=UUID(user.id),
            email=user.email,
            supabase=client,
        )
    finally:
        await client.auth.close()
        await client.postgrest.aclose()


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
