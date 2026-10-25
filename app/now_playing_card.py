from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NowPlayingCard:
    title: str = 'Track Title'
    artist: str = 'Artist'
    album: str = 'Album'
    duration: str = '0:00'

    def snapshot(self) -> dict:
        return {
            'title': self.title,
            'artist': self.artist,
            'album': self.album,
            'duration': self.duration,
        }
