package com.beatsphere.media;

import android.app.Notification;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

/**
 * Foreground "media playback" service. While music plays it holds BeatSphere's media notification,
 * which tells Android the app is playing audio, so it isn't stopped in the background or with the
 * screen off. On pause it steps back: the notification stays (dismissable) and Android may stop it.
 * It runs in the app's own process, next to the player.
 */
public class PlaybackService extends Service {
    public static final int NOTIFICATION_ID = 7301;  // same id as the notification posted from Python
    private static Notification notification;
    private static PlaybackService running;

    /** Called while music plays: shows/refreshes the notification and keeps the app alive. */
    public static void startPlaying(Context context, Notification current) {
        notification = current;
        if (running != null) {
            running.promote();
            return;
        }
        Intent intent = new Intent(context, PlaybackService.class);
        if (Build.VERSION.SDK_INT >= 26) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    /** Called on pause/stop: keeps the notification on screen but lets Android stop the service. */
    public static void stopPlaying() {
        if (running != null) {
            running.stopForeground(STOP_FOREGROUND_DETACH);
            running.stopSelf();
        }
    }

    private void promote() {
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        running = this;
        if (notification == null) {  // nothing to show (e.g. restarted by the system): don't linger
            stopSelf();
            return START_NOT_STICKY;
        }
        promote();
        return START_NOT_STICKY;
    }

    @Override
    public void onDestroy() {
        running = null;
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
