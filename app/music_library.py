"""Music discovery utilities for BeatSphere.

This module scans the device's music folders, keeps only supported audio files,
and turns each file into a lightweight Track object with a clean display name.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Supported audio formats used by the app. The list keeps scanning lightweight and
# avoids adding unsupported files like text documents or images.
supported_extensions = {'.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.opus'}


@dataclass
class Track:
    """Represents one local audio file and the metadata used by the UI."""

    path: str
    title: str
    artist: str = "Unknown Artist"
    duration: float = 0.0

    @property
    def display_name(self) -> str:
        """Returns the user-facing name used in the playlist and library list."""
        return self.title


def _normalize_title(file_path: Path) -> str:
    """Cleans a filename so it looks like a readable song title."""
    title = file_path.stem.replace('_', ' ').replace('-', ' ')
    return ' '.join(title.split())


def tracks_from_index(paths: Iterable[str]) -> list[Track]:
    """Tracks from Android's MediaStore paths, without touching each file (storage calls are slow on phones)."""
    unique = dict.fromkeys(p for p in paths if Path(p).suffix.lower() in supported_extensions)
    return sorted((Track(path=p, title=_normalize_title(Path(p))) for p in unique), key=lambda t: t.title.lower())


def scan_music_files(search_roots: Iterable[str | Path]) -> list[Track]:
    """Walks local folders and returns audio files as Track objects.

    The function is the bridge between the filesystem and the player UI. It finds
    music files, ignores unsupported items, and sorts the list alphabetically.
    """
    discovered: dict[str, Track] = {}
    candidates = [path for root in search_roots if Path(root).is_dir() for path in Path(root).rglob('*')]

    for candidate in candidates:
        if candidate.suffix.lower() not in supported_extensions or not candidate.is_file():
            continue

        file_key = str(candidate.resolve())
        if file_key in discovered:
            continue

        title = _normalize_title(candidate)
        discovered[file_key] = Track(path=file_key, title=title)

    return sorted(discovered.values(), key=lambda item: item.title.lower())


def _read_tags(path: str, image: bool = False):
    """tinytag's view of a file (MIT licensed, unlike GPL mutagen); None when it can't be read."""
    try:
        from tinytag import TinyTag

        return TinyTag.get(path, image=image)
    except Exception:
        return None


def read_metadata(path: str) -> dict:
    """Returns artist, album and duration (seconds) from the file's tags; blanks when missing or unreadable."""
    tags = _read_tags(path)
    if tags is None:
        return {'artist': '', 'album': '', 'duration': 0.0}
    return {'artist': tags.artist or '', 'album': tags.album or '', 'duration': float(tags.duration or 0)}


def extract_cover(path: str, cache_dir: str | Path) -> str | None:
    """Saves the embedded album art (MP3, M4A, FLAC, OGG, Opus pictures) to cache_dir and returns its path."""
    tags = _read_tags(path, image=True)
    picture = tags.images.any if tags is not None else None
    data = picture.data if picture is not None else None
    if not data:
        return None
    suffix = '.png' if data[:4] == b'\x89PNG' else '.jpg'
    out = Path(cache_dir) / (hashlib.md5(path.encode('utf-8')).hexdigest() + suffix)
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        partial = out.with_name(out.name + '.part')
        partial.write_bytes(data)
        os.replace(partial, out)  # another reader never sees a half-written picture
    return str(out)
