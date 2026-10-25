from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AndroidBackgroundPlaybackController:
    permission_grants: set[str] = field(default_factory=set)

    def evaluate(self) -> dict:
        required_permissions = {'WAKE_LOCK', 'READ_EXTERNAL_STORAGE'}
        background_audio_enabled = required_permissions.issubset(self.permission_grants)

        return {
            'background_audio_enabled': background_audio_enabled,
            'service_required': True,
            'missing_permissions': sorted(required_permissions - self.permission_grants),
        }

    def prepare_for_background_play(self, track_path: str | None, playback_state: dict | None = None) -> dict:
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
