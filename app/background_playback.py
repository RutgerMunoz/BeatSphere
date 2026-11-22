"""Background playback controller for Android-style audio behavior.

This class checks whether the app is allowed to keep music playing after the UI
loses focus and returns a safe state object for the player.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AndroidBackgroundPlaybackController:
    """Determines whether the app can continue playback while in background mode."""

    permission_grants: set[str] = field(default_factory=set)

    def evaluate(self) -> dict:
        """Checks whether the required wake and storage permissions are present."""
        required_permissions = {'WAKE_LOCK', 'READ_EXTERNAL_STORAGE'}
        background_audio_enabled = required_permissions.issubset(self.permission_grants)

        return {
            'background_audio_enabled': background_audio_enabled,
            'service_required': True,
            'missing_permissions': sorted(required_permissions - self.permission_grants),
        }

    def prepare_for_background_play(self, track_path: str | None, playback_state: dict | None = None) -> dict:
        """Returns the playback state that tells the UI whether it should keep audio active."""
        state = playback_state or {}
        evaluation = self.evaluate()
        if not track_path:
            return {
                'track_path': None,
                'background_mode': 'disabled',
                'should_keep_playing': False,
                'service_required': evaluation['service_required'],
            }

        should_keep_playing = bool(state.get('state') == 'playing') and evaluation['background_audio_enabled']
        return {
            'track_path': track_path,
            'background_mode': 'enabled' if evaluation['background_audio_enabled'] else 'disabled',
            'should_keep_playing': should_keep_playing,
            'service_required': evaluation['service_required'],
        }
