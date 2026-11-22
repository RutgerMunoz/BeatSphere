"""Library screen model for BeatSphere favorites, playlists, and recent views.

This data object acts as the bridge between the UI and the music data: it keeps
favorite tracks, playlist names, and album-art metadata arranged for display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FavoritePlaylistScreen:
    """Stores the visible sections, playlists, favorites, and cover metadata."""

    sections: list[str] = field(default_factory=lambda: ['Favorites', 'Playlists', 'Recently Played'])
    playlists: list[str] = field(default_factory=list)
    favorite_tracks: list[str] = field(default_factory=list)
    recent_tracks: list[str] = field(default_factory=list)
    playlist_tracks: dict[str, list[str]] = field(default_factory=dict)
    playlist_cover_map: dict[str, dict[str, object]] = field(default_factory=dict)
    playlist_cards: list[dict[str, object]] = field(default_factory=list)

    @property
    def favorites_count(self) -> int:
        """Returns the number of songs currently marked as favorites."""
        return len(self.favorite_tracks)

    @staticmethod
    def _default_cover_color(name: str) -> tuple[int, int, int, int]:
        """Generates a consistent fallback color for a playlist when no cover image exists."""
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
        """Looks for album art next to a track file or in the same folder."""
        if not track_path:
            return None
        track_file = Path(track_path)
        if not track_file.exists():
            return None

        for extension in ('.png', '.jpg', '.jpeg', '.webp'):
            candidate = track_file.with_suffix(extension)
            if candidate.exists():
                return str(candidate)

        # Only the standard album-folder names: a loose 'cover*' match put random pictures from Download on songs.
        for candidate in sorted(track_file.parent.iterdir()):
            if candidate.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'} \
                    and candidate.stem.lower() in {'cover', 'folder', 'front', 'album', 'albumart'}:
                return str(candidate)
        return None

    def _refresh_playlist_cards(self) -> None:
        """Rebuilds the card metadata used by the playlist grid."""
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
        """Creates a playlist with optional cover metadata and refreshes the card list."""
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
        """Adds one song to a playlist and updates the visual cards immediately."""
        if not playlist_name or not track_path:
            return False
        if playlist_name not in self.playlists:
            self.create_playlist(playlist_name)
        if track_path not in self.playlist_tracks.setdefault(playlist_name, []):
            self.playlist_tracks[playlist_name].append(track_path)
        self._refresh_playlist_cards()
        return True

    def rename_playlist(self, old_name: str, new_name: str) -> bool:
        """Renames a playlist in place, keeping its songs, cover and position; refuses blanks and duplicates."""
        new_name = (new_name or '').strip()
        if old_name not in self.playlists or not new_name or new_name in self.playlists:
            return False
        self.playlists[self.playlists.index(old_name)] = new_name
        self.playlist_tracks[new_name] = self.playlist_tracks.pop(old_name, [])
        if old_name in self.playlist_cover_map:
            self.playlist_cover_map[new_name] = self.playlist_cover_map.pop(old_name)
        self._refresh_playlist_cards()
        return True

    def set_playlist_order(self, names: list[str]) -> bool:
        """Applies a drag-reordered list of playlist names (must be the same playlists)."""
        if sorted(names) != sorted(self.playlists):
            return False
        self.playlists = list(names)
        self._refresh_playlist_cards()
        return True

    def toggle_favorite(self, track_path: str) -> bool:
        """Adds or removes a track from favorites and returns the resulting state."""
        if not track_path:
            return False
        if track_path in self.favorite_tracks:
            self.favorite_tracks.remove(track_path)
            return False
        self.favorite_tracks.append(track_path)
        return True

    def add_recent_track(self, track_path: str) -> None:
        """Adds the current song to recent history while keeping the list short."""
        if not track_path:
            return
        if track_path in self.recent_tracks:
            self.recent_tracks.remove(track_path)
        self.recent_tracks.insert(0, track_path)
        if len(self.recent_tracks) > 10:
            self.recent_tracks = self.recent_tracks[:10]

    def snapshot(self) -> dict:
        """Returns a plain dictionary summary of the library screen for display and tests."""
        return {
            'sections': list(self.sections),
            'playlists': list(self.playlists),
            'favorites_count': self.favorites_count,
            'recent_tracks': list(self.recent_tracks),
            'favorite_tracks': list(self.favorite_tracks),
            'playlist_tracks': {name: list(tracks) for name, tracks in self.playlist_tracks.items()},
            'playlist_cards': list(self.playlist_cards),
        }
