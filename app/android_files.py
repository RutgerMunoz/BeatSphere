"""Deleting music files from the device, scoped-storage aware.

Android 11+ won't let an app delete audio files it didn't create with a plain
file delete. The allowed way is MediaStore.createDeleteRequest, which shows the
system's own "Allow BeatSphere to delete this audio file?" prompt; the result
comes back through onActivityResult.
"""

import os
import time

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


def android_cover(path, out_file):
    """Android's own cover for a song, saved as a JPEG; None if there is none or this isn't Android.

    Android reads the art a music app can't: besides embedded pictures it uses the album-art files next to
    the songs (AlbumArt*.jpg, cover.jpg...), which it indexes as non-media and hides from other apps.
    Call from a worker thread (it can take a moment per song); jnius needs detach() when that thread ends.
    """
    from kivy.utils import platform

    if platform != 'android':
        return None
    from android import mActivity
    from jnius import autoclass

    media = autoclass('android.provider.MediaStore$Audio$Media')
    resolver = mActivity.getContentResolver()
    cursor = resolver.query(media.EXTERNAL_CONTENT_URI, ['_id'], '_data=?', [path], None)
    if cursor is None:
        return None
    try:
        if not cursor.moveToFirst():
            return None
        media_id = cursor.getLong(0)
    finally:
        cursor.close()
    uri = autoclass('android.content.ContentUris').withAppendedId(media.EXTERNAL_CONTENT_URI, media_id)
    try:
        bitmap = resolver.loadThumbnail(uri, autoclass('android.util.Size')(512, 512), None)
    except Exception:  # FileNotFoundException: Android has no art for this song either
        return None
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    partial = out_file + '.part'
    stream = autoclass('java.io.FileOutputStream')(partial)
    try:
        bitmap.compress(autoclass('android.graphics.Bitmap$CompressFormat').JPEG, 90, stream)
    finally:
        stream.close()
    os.replace(partial, out_file)  # rows never see a half-written picture
    return out_file


def media_store_audio_paths():
    """Every song Android has indexed (any folder, SD card), skipping ringtones and notification sounds."""
    from kivy.utils import platform

    if platform != 'android':
        return []
    from android import mActivity
    from jnius import autoclass

    media = autoclass('android.provider.MediaStore$Audio$Media')
    # IS NOT 0 (not != 0): freshly added songs have is_music NULL until Android finishes scanning them
    cursor = mActivity.getContentResolver().query(media.EXTERNAL_CONTENT_URI, ['_data'], 'is_music IS NOT 0',
                                                  None, None)
    paths = []
    if cursor is not None:
        try:
            while cursor.moveToNext():
                path = cursor.getString(0)
                if path:
                    paths.append(path)
        finally:
            cursor.close()
    return paths


PICK_IMAGE_REQUEST_CODE = 4722


def pick_image_from_system(folder, on_done):
    """Opens Android's picker (Google Photos, Drive, Gallery, Files...); calls on_done(path or None).

    The picked item is copied into `folder` so it keeps working after the original is moved or deleted.
    on_done runs on Android's thread; callers hop back to Kivy themselves.
    """
    from android import activity, mActivity
    from jnius import autoclass

    intent_class = autoclass('android.content.Intent')
    intent = intent_class(intent_class.ACTION_GET_CONTENT)
    intent.setType('image/*')
    intent.addCategory(intent_class.CATEGORY_OPENABLE)
    chooser = intent_class.createChooser(intent, autoclass('java.lang.String')('Choose a picture'))

    def on_result(request_code, result_code, data):
        if request_code != PICK_IMAGE_REQUEST_CODE:
            return
        activity.unbind(on_activity_result=on_result)
        if result_code != RESULT_OK or data is None or data.getData() is None:
            on_done(None)
            return
        os.makedirs(folder, exist_ok=True)
        # Kivy chooses an image decoder by file extension, so keep the picture's real type
        mime = mActivity.getContentResolver().getType(data.getData()) or ''
        suffix = {'image/png': '.png', 'image/webp': '.webp'}.get(mime, '.jpg')
        target = os.path.join(folder, f'picked_{int(time.time() * 1000)}{suffix}')
        copied = autoclass('com.beatsphere.media.UriFiles').copy(mActivity, data.getData(), target)
        on_done(target if copied else None)

    activity.bind(on_activity_result=on_result)
    mActivity.startActivityForResult(chooser, PICK_IMAGE_REQUEST_CODE)
