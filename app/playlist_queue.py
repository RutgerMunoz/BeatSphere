"""Queue and playlist manager for beatsphere playback flow.

This class keeps track of the active song order, the recent history, and the user
playlists so the app can advance tracks without losing context.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class PlaylistQueue:
    """Stores the current playback queue and playlist membership for songs."""

    queue: deque[str] = field(default_factory=deque)
    recent_history: deque[str] = field(default_factory=deque)
    playlists: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def add_track(self, track_path: str) -> None:
        """Appends a new song to the queue if it is not already present."""
        if track_path not in self.queue:
            self.queue.append(track_path)

    def current_track(self) -> str | None:
        """Returns the song currently at the head of the queue."""
        if not self.queue:
            return None
        return self.queue[0]

    def play_next(self) -> str | None:
        """Moves to the next track and records it in the recent history list."""
        if not self.queue:
            return None
        current = self.queue.popleft()
        self.recent_history.append(current)
        if len(self.recent_history) > 10:
            self.recent_history.popleft()
        if self.queue:
            return self.queue[0]
        return current

    def mark_played(self, track_path: str) -> None:
        """Adds a song to recently played while limiting the stored length."""
        if track_path not in self.recent_history:
            self.recent_history.append(track_path)
        if len(self.recent_history) > 10:
            self.recent_history.popleft()

    def add_to_playlist(self, playlist_name: str, track_path: str) -> None:
        """Adds a song into a given playlist, creating the playlist if needed."""
        self.playlists.setdefault(playlist_name, [])
        if track_path not in self.playlists[playlist_name]:
            self.playlists[playlist_name].append(track_path)

    def get_playlist(self, playlist_name: str) -> list[str]:
        """Returns the saved song list for a playlist name."""
        return list(self.playlists.get(playlist_name, []))
