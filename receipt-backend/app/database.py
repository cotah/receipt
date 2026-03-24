import app.utils.patch_supabase_auth  # noqa: F401  — must run before supabase import
from supabase import create_client, Client
from app.config import settings

_service_client: Client | None = None
_anon_client: Client | None = None


def get_service_client() -> Client:
    """Service role client — full access, used by backend only."""
    global _service_client
    if _service_client is None:
        _service_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return _service_client


def get_anon_client() -> Client:
    """Anon client — respects RLS, used for public queries."""
    global _anon_client
    if _anon_client is None:
        _anon_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    return _anon_client


def get_db() -> Client:
    """Default dependency — returns service client."""
    return get_service_client()
