from app.background_playback import AndroidBackgroundPlaybackController


def test_android_bg_playback_requires_audio_permissions():
    controller = AndroidBackgroundPlaybackController(
        permission_grants={'WAKE_LOCK', 'READ_EXTERNAL_STORAGE'}
    )

    result = controller.evaluate()

    assert result['background_audio_enabled'] is True
    assert result['service_required'] is True


def test_android_bg_playback_prepares_track_for_background_mode():
    controller = AndroidBackgroundPlaybackController(
        permission_grants={'WAKE_LOCK', 'READ_EXTERNAL_STORAGE'}
    )

    prepared = controller.prepare_for_background_play('/storage/music/track.mp3', {'state': 'playing'})

    assert prepared['track_path'] == '/storage/music/track.mp3'
    assert prepared['background_mode'] == 'enabled'
    assert prepared['should_keep_playing'] is True
