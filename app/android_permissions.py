from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_ANDROID_PERMISSIONS = [
    'READ_EXTERNAL_STORAGE',
    'WRITE_EXTERNAL_STORAGE',
    'WAKE_LOCK',
    'INTERNET',
]


def required_android_permissions() -> list[str]:
    return list(DEFAULT_ANDROID_PERMISSIONS)


@dataclass
class AndroidPermissionManager:
    granted_permissions: set[str] = field(default_factory=set)

    def evaluate(self) -> dict:
        required = set(required_android_permissions())
        missing = sorted(required - self.granted_permissions)
        can_run_background_audio = 'WAKE_LOCK' in self.granted_permissions and 'READ_EXTERNAL_STORAGE' in self.granted_permissions

        return {
            'platform': 'android',
            'required': sorted(required),
            'missing': missing,
            'can_run_background_audio': can_run_background_audio,
        }
