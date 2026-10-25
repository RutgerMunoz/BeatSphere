from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FavoritePlaylistScreen:
    sections: list[str] = field(default_factory=lambda: ['Favorites', 'Playlists', 'Recently Played'])
    playlists: list[str] = field(default_factory=list)
    favorite_tracks: list[str] = field(default_factory=list)
    recent_tracks: list[str] = field(default_factory=list)

    @property
    def favorites_count(self) -> int:
        return len(self.favorite_tracks)

    def snapshot(self) -> dict:
        return {
            'sections': list(self.sections),
            'playlists': list(self.playlists),
            'favorites_count': self.favorites_count,
            'recent_tracks': list(self.recent_tracks),
        }
