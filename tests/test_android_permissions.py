from app.android_permissions import AndroidPermissionManager, required_android_permissions


def test_required_android_permissions_include_audio_access():
    perms = required_android_permissions()

    assert 'READ_EXTERNAL_STORAGE' in perms
    assert 'WAKE_LOCK' in perms


def test_android_permission_manager_reports_missing_permissions():
    manager = AndroidPermissionManager(granted_permissions=set())

    result = manager.evaluate()

    assert result['platform'] == 'android'
    assert result['can_run_background_audio'] is False
    assert 'READ_EXTERNAL_STORAGE' in result['missing']
