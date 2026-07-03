"""Regression test for the staff ``GET /auth/me`` endpoint.

The admin frontend calls ``GET /api/v1/auth/me`` right after login to load the
current user's profile. When that route was missing the backend returned 404
and the sign-in screen showed "Not Found". This test guards the route so the
endpoint can't silently disappear again. It is unit-level: it inspects the
router definition and requires no DB session.
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x/x")
os.environ.setdefault("JWT_SECRET", "test-secret-please-ignore-32-bytes-min")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-admin-pw")

from app.routers.auth import router  # noqa: E402
from app.schemas.auth import CurrentUserOut  # noqa: E402


def _get_route(path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route
    return None


def test_auth_me_route_registered():
    route = _get_route("/auth/me", "GET")
    assert route is not None, "GET /auth/me must be registered on the auth router"
    assert route.response_model is CurrentUserOut


def test_current_user_schema_fields():
    # The response shape the frontend's CurrentUser interface depends on.
    expected = {
        "id",
        "email",
        "first_name",
        "last_name",
        "roles",
        "is_super_admin",
        "mfa_enrolled",
        "org_id",
    }
    assert expected <= set(CurrentUserOut.model_fields)
