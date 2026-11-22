"""Android runtime compatibility helper.

This small utility exposes the app's current permission readiness in one place so
other modules can decide whether Android audio features are available.
"""

from __future__ import annotations

from app.android_permissions import AndroidPermissionManager


def get_android_runtime_status(granted_permissions: set[str] | None = None) -> dict:
    """Returns a summary of Android permission readiness for the current runtime."""
    manager = AndroidPermissionManager(granted_permissions or set())
    return manager.evaluate()
