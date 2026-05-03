"""Async Supabase client — supports dual instances for geo-routing."""
from __future__ import annotations

from typing import Optional

from .config import settings


class SupabaseClientManager:
    """Manages connections to both cloud and self-hosted Supabase instances.

    - Primary (international): settings.supabase_url
    - Russia (self-hosted): settings.supabase_russia_url

    Usage:
        client = get_supabase_client("russia")
        result = await client.table("users").select("*").execute()
    """

    def __init__(self) -> None:
        self._primary: Optional[object] = None
        self._russia: Optional[object] = None

    def _create_client(self, url: str, key: str) -> Optional[object]:
        """Create Supabase client (async if available, sync fallback)."""
        if not url:
            return None
        try:
            from supabase import create_async_client
            return create_async_client(url, key)
        except ImportError:
            try:
                from supabase import create_client
                return create_client(url, key)
            except ImportError:
                return None

    def primary(self) -> Optional[object]:
        """Get primary (cloud) Supabase client."""
        if self._primary is None and settings.supabase_url:
            self._primary = self._create_client(
                str(settings.supabase_url),
                str(settings.supabase_service_key),
            )
        return self._primary

    def russia(self) -> Optional[object]:
        """Get Russia self-hosted Supabase client."""
        if self._russia is None and settings.supabase_russia_url:
            self._russia = self._create_client(
                str(settings.supabase_russia_url),
                str(settings.supabase_russia_service_key),
            )
        return self._russia

    def get(self, region: str = "primary") -> Optional[object]:
        """Get client by region: 'primary' or 'russia'."""
        if region == "russia":
            return self.russia()
        return self.primary()

    def default(self) -> Optional[object]:
        """Get whichever client is configured (russia preferred if available)."""
        # Prefer self-hosted Russia when available
        return self.russia() or self.primary()


# Global manager
_manager = SupabaseClientManager()

# Backwards-compatible global client
supabase_client = _manager.default()

# Convenience functions
def get_supabase_client(region: str = "default"):
    """Fetch Supabase client by region.

    region='default' → russia (if configured) else primary
    region='russia'  → self-hosted in Russia
    region='primary' → cloud Supabase (international)
    """
    if region == "default":
        return _manager.default()
    return _manager.get(region)


def is_russia_available() -> bool:
    """Check if self-hosted Russia instance is connected."""
    return _manager.russia() is not None
