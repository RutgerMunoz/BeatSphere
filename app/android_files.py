"""Deleting music files from the device, scoped-storage aware.

Android 11+ won't let an app delete audio files it didn't create with a plain
file delete. The allowed way is MediaStore.createDeleteRequest, which shows the
system's own "Allow BeatSphere to delete this audio file?" prompt; the result
comes back through onActivityResult.
"""

import os

DELETE_REQUEST_CODE = 4721
RESULT_OK = -1  # android.app.Activity.RESULT_OK


def delete_audio_file(path, on_done):
    """Deletes `path`, then calls on_done(deleted: bool) — possibly later, after the system prompt."""
    try:
        os.remove(path)
        on_done(True)
        return
    except OSError:
        pass
    try:
        from kivy.utils import platform

        if platform == 'android' and _request_system_delete(path, on_done):
            return
    except Exception:
        pass
    on_done(False)


def _request_system_delete(path, on_done):
    """Asks Android (11+) to delete the file through MediaStore. Returns False if that isn't possible."""
    from android import activity, mActivity
    from jnius import autoclass

    if autoclass('android.os.Build$VERSION').SDK_INT < 30:
        return False
    media = autoclass('android.provider.MediaStore$Audio$Media')
    resolver = mActivity.getContentResolver()
    cursor = resolver.query(media.EXTERNAL_CONTENT_URI, ['_id'], '_data=?', [path], None)
    if cursor is None:
        return False
    try:
        if not cursor.moveToFirst():
            return False
        media_id = cursor.getLong(0)
    finally:
        cursor.close()
    uri = autoclass('android.content.ContentUris').withAppendedId(media.EXTERNAL_CONTENT_URI, media_id)
    request = autoclass('android.provider.MediaStore').createDeleteRequest(
        resolver, autoclass('java.util.Collections').singletonList(uri))

    def on_result(request_code, result_code, intent):
        if request_code == DELETE_REQUEST_CODE:
            activity.unbind(on_activity_result=on_result)
            on_done(result_code == RESULT_OK and not os.path.exists(path))

    activity.bind(on_activity_result=on_result)
    mActivity.startIntentSenderForResult(request.getIntentSender(), DELETE_REQUEST_CODE, None, 0, 0, 0)
    return True
