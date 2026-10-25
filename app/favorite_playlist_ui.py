from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FavoritePlaylistScreen:
    sections: list[str] = field(default_factory=lambda: ['Favorites', 'Playlists', 'Recently Played'])
    playlists: list[str] = field(default_factory=list)
    favorite_tracks: list[str] = field(default_factory=list)
    recent_tracks: list[str] = field(default_factory=list)
    playlist_tracks: dict[str, list[str]] = field(default_factory=dict)

    @property
    def favorites_count(self) -> int:
        return len(self.favorite_tracks)

    def create_playlist(self, name: str) -> bool:
        playlist_name = (name or '').strip()
        if not playlist_name:
            return False
        if playlist_name not in self.playlists:
            self.playlists.append(playlist_name)
            self.playlist_tracks.setdefault(playlist_name, [])
        return True

    def add_track_to_playlist(self, playlist_name: str, track_path: str) -> bool:
        if not playlist_name or not track_path:
            return False
        if playlist_name not in self.playlists:
            self.create_playlist(playlist_name)
        if track_path not in self.playlist_tracks.setdefault(playlist_name, []):
            self.playlist_tracks[playlist_name].append(track_path)
        return True

    def toggle_favorite(self, track_path: str) -> bool:
        if not track_path:
            return False
        if track_path in self.favorite_tracks:
            self.favorite_tracks.remove(track_path)
            return False
        self.favorite_tracks.append(track_path)
        return True

    def add_recent_track(self, track_path: str) -> None:
        if not track_path:
            return
        if track_path in self.recent_tracks:
            self.recent_tracks.remove(track_path)
        self.recent_tracks.insert(0, track_path)
        if len(self.recent_tracks) > 10:
            self.recent_tracks = self.recent_tracks[:10]

    def snapshot(self) -> dict:
        return {
            'sections': list(self.sections),
            'playlists': list(self.playlists),
            'favorites_count': self.favorites_count,
            'recent_tracks': list(self.recent_tracks),
            'favorite_tracks': list(self.favorite_tracks),
            'playlist_tracks': {name: list(tracks) for name, tracks in self.playlist_tracks.items()},
        }
