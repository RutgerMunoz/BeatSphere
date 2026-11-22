"""Metadata model for the now-playing panel.

The card stores the active song details displayed in the main dashboard so the UI
can update without re-reading the whole library each time.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NowPlayingCard:
    """Represents the song currently displayed in the hero music card."""

    title: str = 'Track Title'
    artist: str = 'Artist'
    album: str = 'Album'
    duration: str = '0:00'

    def snapshot(self) -> dict:
        """Returns a plain dictionary snapshot of the card for easy UI updates."""
        return {
            'title': self.title,
            'artist': self.artist,
            'album': self.album,
            'duration': self.duration,
        }
