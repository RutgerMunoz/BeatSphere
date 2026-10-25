from __future__ import annotations

from app.android_permissions import AndroidPermissionManager


def get_android_runtime_status(granted_permissions: set[str] | None = None) -> dict:
    manager = AndroidPermissionManager(granted_permissions or set())
    return manager.evaluate()
