"""Async Supabase client — lazy init (works without Supabase URL)."""
from .config import settings

# If Supabase URL is configured, create real async client
supabase_client = None
if settings.supabase_url:
    from supabase import create_client
    supabase_client = create_client(str(settings.supabase_url), str(settings.supabase_service_key))
