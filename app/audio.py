"""Audio playback backends.

Kivy's SDL2 audio (what SoundLoader gives on Android and desktop) can't report the
playback position or seek, so on Android BeatSphere plays through the native
android.media.MediaPlayer via pyjnius. On the desktop it falls back to SoundLoader
and tracks the position with a timer (seeking isn't possible there).
"""

import time


def _completion_listener(callback):
    """Java OnCompletionListener that calls back into Python when a song ends."""
    from jnius import PythonJavaClass, java_method

    class CompletionListener(PythonJavaClass):
        __javainterfaces__ = ['android/media/MediaPlayer$OnCompletionListener']
        __javacontext__ = 'app'

        @java_method('(Landroid/media/MediaPlayer;)V')
        def onCompletion(self, media_player):
            callback()

    return CompletionListener()


class AndroidPlayer:
    """android.media.MediaPlayer: real position, seek, pause/resume."""

    def __init__(self, on_complete=None):
        from jnius import autoclass

        self.on_complete = on_complete  # called on Android's thread when a song ends (works while backgrounded)
        self._media_player_class = autoclass('android.media.MediaPlayer')
        self._mp = None
        self._completed = False
        # Polling isPlaying() misfires on slow phones right after start(); Android's own end-of-song event doesn't.
        self._listener = _completion_listener(self._on_completion)  # keep a reference so it isn't garbage collected

    def _on_completion(self):
        self._completed = True
        if self.on_complete is not None:
            self.on_complete()

    def load(self, path):
        self.unload()
        try:
            mp = self._media_player_class()
            mp.setDataSource(path)
            mp.prepare()
            mp.setOnCompletionListener(self._listener)
        except Exception:
            return False
        self._mp = mp
        self._completed = False
        return True

    def play(self):
        if self._mp is not None:
            self._completed = False
            self._mp.start()

    def pause(self):
        if self._mp is not None and self._mp.isPlaying():
            self._mp.pause()

    def seek(self, seconds):
        if self._mp is not None:
            self._mp.seekTo(int(seconds * 1000))

    def position(self):
        return self._mp.getCurrentPosition() / 1000 if self._mp is not None else 0

    def length(self):
        return max(self._mp.getDuration(), 0) / 1000 if self._mp is not None else 0

    def finished(self):
        """True once Android reported the song played to its end (or it clearly sits at the very end)."""
        if self._mp is None:
            return False
        length = self.length()
        at_end = length > 1 and self.position() >= length - 0.3 and not self._mp.isPlaying()
        return self._completed or at_end

    def unload(self):
        if self._mp is not None:
            self._mp.release()
            self._mp = None


class KivyPlayer:
    """SoundLoader fallback; position comes from a timer because SDL2 audio reports 0."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._sound = None
        self._offset = 0.0
        self._resumed_at = None

    def load(self, path):
        from kivy.core.audio import SoundLoader

        self.unload()
        self._sound = SoundLoader.load(path)
        self._offset, self._resumed_at = 0.0, None
        return self._sound is not None

    def play(self):
        if self._sound is not None:
            self._sound.play()  # shortcut: SDL2 restarts from 0, so resume-after-pause restarts the song on desktop
            self._offset, self._resumed_at = 0.0, self._clock()

    def pause(self):
        if self._sound is not None and self._resumed_at is not None:
            self._offset += self._clock() - self._resumed_at
            self._resumed_at = None
            self._sound.stop()

    def seek(self, seconds):
        pass  # SDL2 chunks can't seek

    def position(self):
        running = self._clock() - self._resumed_at if self._resumed_at is not None else 0
        return min(self._offset + running, self.length() or float('inf'))

    def length(self):
        return self._sound.length if self._sound is not None else 0

    def finished(self):
        return self._sound is not None and self._resumed_at is not None and self._sound.state == 'stop'

    def unload(self):
        if self._sound is not None:
            self._sound.stop()
            self._sound.unload()
            self._sound = None


def create_player(on_complete=None):
    from kivy.utils import platform

    return AndroidPlayer(on_complete) if platform == 'android' else KivyPlayer()
