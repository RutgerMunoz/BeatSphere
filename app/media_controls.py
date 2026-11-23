"""Media notification and lock-screen controls (Android MediaSession + MediaStyle notification).

The notification shows the cover, title and artist with ◀◀ ❚❚ ▶▶ buttons. Button presses
arrive two ways and both call on_command(command, value):
  * MediaSession callback (Android 13+ notification/lock screen, headphones, Bluetooth) via the
    small Java bridge in java/com/beatsphere/media/SessionCallback.java;
  * broadcast PendingIntents on the notification's own buttons (older Android).
Commands arrive on Android's main thread, not Kivy's; the app decides how to run them.
"""

import os

from app.i18n import tr

ACTIONS = {'com.beatsphere.PREVIOUS': 'previous', 'com.beatsphere.TOGGLE': 'toggle', 'com.beatsphere.NEXT': 'next'}
CHANNEL_ID = 'beatsphere_playback'
NOTIFICATION_ID = 7301


class NoMediaControls:
    """Desktop stand-in: there is no notification panel to update."""

    def update(self, *args, **kwargs):
        pass

    def release(self):
        pass


def create_media_controls(on_command, app_icon_path):
    from kivy.utils import platform

    if platform != 'android':
        return NoMediaControls()
    try:
        return AndroidMediaControls(on_command, app_icon_path)
    except Exception:
        import traceback
        traceback.print_exc()  # never let the notification break playback
        return NoMediaControls()


class AndroidMediaControls:
    def __init__(self, on_command, app_icon_path):
        from android import mActivity
        from jnius import PythonJavaClass, autoclass, cast, java_method

        self._autoclass = autoclass
        self.context = mActivity
        self.on_command = on_command
        self.app_icon_path = os.path.abspath(app_icon_path)
        self.sdk = autoclass('android.os.Build$VERSION').SDK_INT
        context_class = autoclass('android.content.Context')
        self.manager = cast('android.app.NotificationManager',
                            mActivity.getSystemService(context_class.NOTIFICATION_SERVICE))

        manager_class = autoclass('android.app.NotificationManager')
        channel = autoclass('android.app.NotificationChannel')(CHANNEL_ID, 'Now playing',
                                                                manager_class.IMPORTANCE_LOW)
        channel.setShowBadge(False)
        channel.setDescription(tr('Controls for the song that is playing'))
        self.manager.createNotificationChannel(channel)

        class SessionListener(PythonJavaClass):
            __javainterfaces__ = ['com/beatsphere/media/SessionCallback$Listener']
            __javacontext__ = 'app'

            @java_method('(Ljava/lang/String;J)V')
            def onCommand(self, command, value):
                on_command(command, value)

        class ReceiverListener(PythonJavaClass):
            __javainterfaces__ = ['org/kivy/android/GenericBroadcastReceiverCallback']
            __javacontext__ = 'app'

            @java_method('(Landroid/content/Context;Landroid/content/Intent;)V')
            def onReceive(self, context, intent):
                command = ACTIONS.get(intent.getAction())
                if command:
                    on_command(command, 0)

        # keep Python references alive: Java only holds weak handles to these proxies
        self._session_listener = SessionListener()
        self._receiver_listener = ReceiverListener()

        handler = autoclass('android.os.Handler')(autoclass('android.os.Looper').getMainLooper())
        self.session = autoclass('android.media.session.MediaSession')(mActivity, 'BeatSphere')
        self.session.setCallback(autoclass('com.beatsphere.media.SessionCallback')(self._session_listener), handler)
        self.session.setActive(True)

        intent_filter = autoclass('android.content.IntentFilter')()
        for action in ACTIONS:
            intent_filter.addAction(action)
        self.receiver = autoclass('org.kivy.android.GenericBroadcastReceiver')(self._receiver_listener)
        if self.sdk >= 33:
            # Android 14 rejects app-specific receivers without an exported flag; ours only takes our own intents.
            mActivity.registerReceiver(self.receiver, intent_filter, context_class.RECEIVER_NOT_EXPORTED)
        else:
            mActivity.registerReceiver(self.receiver, intent_filter)

        pending = autoclass('android.app.PendingIntent')
        flags = pending.FLAG_IMMUTABLE | pending.FLAG_UPDATE_CURRENT
        self.button_intents = {}
        for code, action in enumerate(ACTIONS):
            intent = autoclass('android.content.Intent')(action)
            intent.setPackage(mActivity.getPackageName())
            self.button_intents[ACTIONS[action]] = pending.getBroadcast(mActivity, 100 + code, intent, flags)
        launch = mActivity.getPackageManager().getLaunchIntentForPackage(mActivity.getPackageName())
        self.open_app_intent = pending.getActivity(mActivity, 0, launch, flags)
        self._bitmap_path = None
        self._bitmap = None

    def _cover_bitmap(self, path):
        path = path if path and os.path.exists(path) else self.app_icon_path
        if path != self._bitmap_path:
            self._bitmap = self._autoclass('android.graphics.BitmapFactory').decodeFile(path)
            self._bitmap_path = path
        return self._bitmap

    def update(self, title, artist, cover, playing, position, length):
        """Publishes the current song to the notification panel, lock screen and media buttons."""
        ac = self._autoclass
        metadata = ac('android.media.MediaMetadata')
        builder = ac('android.media.MediaMetadata$Builder')()
        builder.putString(metadata.METADATA_KEY_TITLE, title)
        builder.putString(metadata.METADATA_KEY_ARTIST, artist)
        builder.putLong(metadata.METADATA_KEY_DURATION, int(length * 1000))
        bitmap = self._cover_bitmap(cover)
        if bitmap is not None:
            builder.putBitmap(metadata.METADATA_KEY_ALBUM_ART, bitmap)
        self.session.setMetadata(builder.build())

        state = ac('android.media.session.PlaybackState')
        actions = (state.ACTION_PLAY | state.ACTION_PAUSE | state.ACTION_PLAY_PAUSE | state.ACTION_SKIP_TO_NEXT
                   | state.ACTION_SKIP_TO_PREVIOUS | state.ACTION_SEEK_TO)
        playback = ac('android.media.session.PlaybackState$Builder')()
        playback.setActions(actions)
        playback.setState(state.STATE_PLAYING if playing else state.STATE_PAUSED, int(position * 1000),
                          1.0 if playing else 0.0)
        self.session.setPlaybackState(playback.build())

        drawable = ac('android.R$drawable')
        icon = ac('android.graphics.drawable.Icon')
        action_builder = ac('android.app.Notification$Action$Builder')

        text = ac('java.lang.String')  # explicit Java strings so pyjnius picks the CharSequence overloads

        def action(res, label, command):
            # system icons live in the "android" package; the (String, int) overload avoids a Context mix-up
            return action_builder(icon.createWithResource('android', res), text(label),
                                  self.button_intents[command]).build()

        notification = ac('android.app.Notification')
        style = ac('android.app.Notification$MediaStyle')()
        style.setMediaSession(self.session.getSessionToken())
        style.setShowActionsInCompactView(0, 1, 2)  # Java varargs: pyjnius builds the int[] from the arguments
        builder = ac('android.app.Notification$Builder')(self.context, CHANNEL_ID)
        builder.setSmallIcon(drawable.ic_media_play)
        builder.setContentTitle(text(title))
        builder.setContentText(text(artist))
        if bitmap is not None:
            builder.setLargeIcon(bitmap)
        builder.setContentIntent(self.open_app_intent)
        builder.setVisibility(notification.VISIBILITY_PUBLIC)  # show controls on the lock screen
        builder.setShowWhen(False)
        builder.setOngoing(playing)  # can't be swiped away while music plays
        builder.addAction(action(drawable.ic_media_previous, tr('Previous'), 'previous'))
        builder.addAction(action(drawable.ic_media_pause if playing else drawable.ic_media_play,
                                 tr('Pause') if playing else tr('Play'), 'toggle'))
        builder.addAction(action(drawable.ic_media_next, tr('Next'), 'next'))
        builder.setStyle(style)
        built = builder.build()
        self.manager.notify(NOTIFICATION_ID, built)
        service = ac('com.beatsphere.media.PlaybackService')
        try:
            if playing:
                service.startPlaying(self.context, built)  # keeps the app alive while music plays
            else:
                service.stopPlaying()  # paused: notification stays, Android may stop the app later
        except Exception:
            import traceback
            traceback.print_exc()  # e.g. Android refusing a background start: music still plays meanwhile

    def release(self):
        try:
            self._autoclass('com.beatsphere.media.PlaybackService').stopPlaying()
            self.manager.cancel(NOTIFICATION_ID)
            self.session.setActive(False)
            self.session.release()
            self.context.unregisterReceiver(self.receiver)
        except Exception:
            pass
