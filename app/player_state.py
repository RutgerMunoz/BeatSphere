"""Playback state container for BeatSphere.

This dataclass keeps track of the active queue, current song index, theme, and
playlist data so the app can react to play, skip, and favorite actions.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

REPEAT_MODES = ['off', 'all', 'one']


@dataclass
class PlayerState:
    """Stores the current app playback state and the user's library context."""

    theme: str = 'dark'
    track_paths: list[str] = field(default_factory=list)
    current_index: int = -1
    playing: bool = False
    background_playing: bool = False
    queue: list[str] = field(default_factory=list)
    recent_history: list[str] = field(default_factory=list)
    playlists: dict[str, list[str]] = field(default_factory=dict)
    shuffle: bool = False
    repeat_mode: str = 'off'
    unshuffled: list[str] = field(default_factory=list)

    def toggle_shuffle(self, rng: random.Random | None = None) -> bool:
        """Shuffles the queue keeping the current song first, or restores the original order."""
        current = self.current_track()
        if self.shuffle:
            self.track_paths = self.unshuffled or self.track_paths
        else:
            self.unshuffled = list(self.track_paths)
            rest = [path for path in self.track_paths if path != current]
            (rng or random).shuffle(rest)
            self.track_paths = ([current] if current else []) + rest
        self.shuffle = not self.shuffle
        self.current_index = self.track_paths.index(current) if current in self.track_paths else (0 if self.track_paths else -1)
        return self.shuffle

    def cycle_repeat(self) -> str:
        """Steps repeat through off → all → one."""
        self.repeat_mode = REPEAT_MODES[(REPEAT_MODES.index(self.repeat_mode) + 1) % len(REPEAT_MODES)]
        return self.repeat_mode

    def advance(self) -> str | None:
        """Picks what plays when a song finishes: same song, next one, or nothing at the end with repeat off."""
        if not self.track_paths:
            return None
        if self.repeat_mode == 'one':
            return self.current_track()
        if self.current_index >= len(self.track_paths) - 1 and self.repeat_mode == 'off':
            return None
        return self.next_track()

    def set_tracks(self, tracks: list[str]) -> None:
        """Loads the available library and resets the queue to the selected songs."""
        self.track_paths = list(tracks)
        self.queue = list(tracks)
        if self.track_paths and self.current_index < 0:
            self.current_index = 0
        elif not self.track_paths:
            self.current_index = -1

    def add_to_playlist(self, playlist_name: str, track_path: str) -> None:
        """Adds a song to a named playlist without duplicating the same track."""
        self.playlists.setdefault(playlist_name, [])
        if track_path not in self.playlists[playlist_name]:
            self.playlists[playlist_name].append(track_path)

    def mark_played(self, track_path: str) -> None:
        """Stores the last played songs for the recently played history panel."""
        if track_path not in self.recent_history:
            self.recent_history.append(track_path)
        if len(self.recent_history) > 10:
            self.recent_history = self.recent_history[-10:]

    def next_track(self) -> str | None:
        """Moves to the next item in the queue and wraps around when needed."""
        if not self.track_paths:
            return None
        if self.current_index >= len(self.track_paths) - 1:
            self.current_index = 0
        else:
            self.current_index += 1
        if self.current_track():
            self.mark_played(self.current_track())
        return self.current_track()

    def previous_track(self) -> str | None:
        """Moves backward in the queue and keeps recent playback history updated."""
        if not self.track_paths:
            return None
        if self.current_index <= 0:
            self.current_index = len(self.track_paths) - 1
        else:
            self.current_index -= 1
        if self.current_track():
            self.mark_played(self.current_track())
        return self.current_track()

    def current_track(self) -> str | None:
        """Returns the currently selected file path or None when nothing is loaded."""
        if not self.track_paths or self.current_index < 0:
            return None
        return self.track_paths[self.current_index]

    def current_track_title(self) -> str:
        """Gets the filename for display in the current song panel."""
        track = self.current_track()
        if not track:
            return 'No track selected'
        return track.split('\\')[-1].split('/')[-1]

    def select_track(self, path: str) -> None:
        """Sets the current song when the user taps a track in the list."""
        if path in self.track_paths:
            self.current_index = self.track_paths.index(path)
            self.playing = False

    def toggle_theme(self) -> None:
        """Switches between dark and light visual themes for the app."""
        self.theme = 'light' if self.theme == 'dark' else 'dark'
