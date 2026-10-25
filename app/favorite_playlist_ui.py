from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FavoritePlaylistScreen:
    sections: list[str] = field(default_factory=lambda: ['Favorites', 'Playlists', 'Recently Played'])
    playlists: list[str] = field(default_factory=list)
    favorite_tracks: list[str] = field(default_factory=list)
    recent_tracks: list[str] = field(default_factory=list)
    playlist_tracks: dict[str, list[str]] = field(default_factory=dict)
    playlist_cover_map: dict[str, dict[str, object]] = field(default_factory=dict)
    playlist_cards: list[dict[str, object]] = field(default_factory=list)

    @property
    def favorites_count(self) -> int:
        return len(self.favorite_tracks)

    @staticmethod
    def _default_cover_color(name: str) -> tuple[int, int, int, int]:
        palette = [
            (18, 90, 156, 255),
            (28, 126, 214, 255),
            (99, 180, 255, 255),
            (74, 130, 255, 255),
            (30, 72, 176, 255),
        ]
        value = sum(ord(char) for char in name) % len(palette)
        return palette[value]

    @staticmethod
    def resolve_album_art(track_path: str | None) -> str | None:
        if not track_path:
            return None
        track_file = Path(track_path)
        if not track_file.exists():
            return None

        for extension in ('.png', '.jpg', '.jpeg', '.webp'):
            candidate = track_file.with_suffix(extension)
            if candidate.exists():
                return str(candidate)

        parent = track_file.parent
        for candidate in sorted(parent.glob('cover*')):
            if candidate.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}:
                return str(candidate)
        return None

    def _refresh_playlist_cards(self) -> None:
        cards: list[dict[str, object]] = []
        for playlist_name in self.playlists:
            metadata = self.playlist_cover_map.get(playlist_name, {})
            cover_color = metadata.get('cover_color') or self._default_cover_color(playlist_name)
            cover_path = metadata.get('cover_path') or ''
            if not cover_path:
                tracks = self.playlist_tracks.get(playlist_name, [])
                for track_path in tracks:
                    resolved = self.resolve_album_art(track_path)
                    if resolved:
                        cover_path = resolved
                        break
            cards.append({
                'name': playlist_name,
                'track_count': len(self.playlist_tracks.get(playlist_name, [])),
                'cover_color': cover_color,
                'cover_path': cover_path,
            })
        self.playlist_cards = cards

    def create_playlist(self, name: str, cover_color: tuple[int, int, int, int] | None = None,
                        cover_path: str | None = None) -> bool:
        playlist_name = (name or '').strip()
        if not playlist_name:
            return False
        if playlist_name not in self.playlists:
            self.playlists.append(playlist_name)
            self.playlist_tracks.setdefault(playlist_name, [])
        self.playlist_cover_map[playlist_name] = {
            'cover_color': cover_color or self._default_cover_color(playlist_name),
            'cover_path': cover_path or self.playlist_cover_map.get(playlist_name, {}).get('cover_path', ''),
        }
        self._refresh_playlist_cards()
        return True

    def add_track_to_playlist(self, playlist_name: str, track_path: str) -> bool:
        if not playlist_name or not track_path:
            return False
        if playlist_name not in self.playlists:
            self.create_playlist(playlist_name)
        if track_path not in self.playlist_tracks.setdefault(playlist_name, []):
            self.playlist_tracks[playlist_name].append(track_path)
        self._refresh_playlist_cards()
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
            'playlist_cards': list(self.playlist_cards),
        }
