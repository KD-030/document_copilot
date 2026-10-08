from functools import lru_cache

from supabase import (
    AsyncClient,
    AsyncClientOptions,
    Client,
    acreate_client,
    create_client,
)

from app.config import settings


async def create_user_scoped_client(access_token: str) -> AsyncClient:
    """Create an async Supabase client whose requests use the user's JWT."""
    return await acreate_client(
        str(settings.supabase_url),
        settings.supabase_anon_key,
        AsyncClientOptions(
            headers={"Authorization": f"Bearer {access_token}"},
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


@lru_cache(maxsize=1)
def get_service_role_client() -> Client:
    """Return the backend-only client for privileged database operations."""
    return create_client(str(settings.supabase_url), settings.supabase_service_role_key)
