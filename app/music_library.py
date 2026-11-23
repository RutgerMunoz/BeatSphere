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


def read_metadata(path: str) -> dict:
    """Returns artist, album and duration (seconds) from the file's tags; blanks when missing or unreadable."""
    meta = {'artist': '', 'album': '', 'duration': 0.0}
    try:
        from mutagen import File as MutagenFile

        audio = MutagenFile(path, easy=True)
    except Exception:
        audio = None
    if audio is not None:
        tags = audio.tags or {}
        meta['artist'] = (tags.get('artist') or [''])[0]
        meta['album'] = (tags.get('album') or [''])[0]
        meta['duration'] = float(getattr(audio.info, 'length', 0) or 0)
        return meta
    id3 = _read_id3(path)  # tagged file whose audio frames mutagen can't parse
    if id3 is not None:
        meta['artist'] = str(id3.get('TPE1', ''))
        meta['album'] = str(id3.get('TALB', ''))
    return meta


def extract_cover(path: str, cache_dir: str | Path) -> str | None:
    """Saves the embedded album art (MP3 APIC, MP4 covr, FLAC/OGG pictures) to cache_dir and returns its path."""
    data = None
    try:
        from mutagen import File as MutagenFile

        audio = MutagenFile(path)
    except Exception:
        audio = None
    tags = audio.tags if audio is not None else _read_id3(path)
    if tags is not None:
        apic = [key for key in tags.keys() if key.startswith('APIC')]
        if apic:
            data = tags[apic[0]].data
        elif 'covr' in tags:
            data = bytes(tags['covr'][0])
    if data is None and getattr(audio, 'pictures', None):
        data = audio.pictures[0].data
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


def _read_id3(path: str):
    try:
        from mutagen.id3 import ID3

        return ID3(path)
    except Exception:
        return None
