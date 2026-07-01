"""Super-admin router group.

All modules here require `require_super_admin()` and write ActivityLog rows
scoped to the target tenant's org_id so tenant admins see admin actions in
their own audit log.
"""
from app.routers.admin import audit_search, impersonate, plans, seats, tenants


__all__ = ["audit_search", "impersonate", "plans", "seats", "tenants"]
