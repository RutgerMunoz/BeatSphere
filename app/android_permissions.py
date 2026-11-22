"""Android permission checks used by BeatSphere.

This module tells the app which Android permissions are required for local music
access and wake-lock behavior while background audio is active.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Android permission list required for local playback and wake behavior. The app
# checks if these permissions are currently granted before allowing background tasks.
DEFAULT_ANDROID_PERMISSIONS = [
    'READ_EXTERNAL_STORAGE',
    'WRITE_EXTERNAL_STORAGE',
    'WAKE_LOCK',
    'INTERNET',
]


def required_android_permissions() -> list[str]:
    """Returns the app's minimum required Android permission list."""
    return list(DEFAULT_ANDROID_PERMISSIONS)


@dataclass
class AndroidPermissionManager:
    """Validates whether Android is ready to play music in the current environment."""

    granted_permissions: set[str] = field(default_factory=set)

    def evaluate(self) -> dict:
        """Compares required permissions against what the OS has granted."""
        required = set(required_android_permissions())
        missing = sorted(required - self.granted_permissions)
        can_run_background_audio = 'WAKE_LOCK' in self.granted_permissions and 'READ_EXTERNAL_STORAGE' in self.granted_permissions

        return {
            'platform': 'android',
            'required': sorted(required),
            'missing': missing,
            'can_run_background_audio': can_run_background_audio,
        }
