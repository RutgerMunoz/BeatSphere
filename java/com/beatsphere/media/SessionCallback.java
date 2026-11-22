package com.beatsphere.media;

import android.media.session.MediaSession;

/**
 * Forwards media-button commands (notification, lock screen, headphones) to Python.
 * MediaSession.Callback is an abstract class, which pyjnius cannot subclass from Python,
 * so this thin bridge calls a Python-implemented interface instead.
 */
public class SessionCallback extends MediaSession.Callback {
    public interface Listener {
        void onCommand(String command, long value);
    }

    private final Listener listener;

    public SessionCallback(Listener listener) {
        this.listener = listener;
    }

    @Override public void onPlay() { listener.onCommand("play", 0); }
    @Override public void onPause() { listener.onCommand("pause", 0); }
    @Override public void onStop() { listener.onCommand("pause", 0); }
    @Override public void onSkipToNext() { listener.onCommand("next", 0); }
    @Override public void onSkipToPrevious() { listener.onCommand("previous", 0); }
    @Override public void onSeekTo(long positionMs) { listener.onCommand("seek", positionMs); }
}
