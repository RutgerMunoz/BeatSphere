"""Pure helpers behind the Songs, Folders and Mix tabs.

They take Track objects from music_library and return sorted, filtered or grouped
lists, so the Kivy screens stay thin and this logic can be unit-tested.
"""

from __future__ import annotations

import random
import re
import unicodedata
from pathlib import Path

LETTERS = ['All', '#'] + [chr(code) for code in range(ord('A'), ord('Z') + 1)]


def letter_of(title: str) -> str:
    """Returns the A–Z index letter for a title; digits, symbols and other scripts go under '#'."""
    stripped = unicodedata.normalize('NFKD', (title or '').strip())
    first = stripped[:1].upper()
    return first if 'A' <= first <= 'Z' else '#'


def _natural_key(title: str) -> list:
    """Sorts 'Track 2' before 'Track 10' and 'Éxitos' with the E's (accents stripped, digit runs as numbers)."""
    plain = ''.join(c for c in unicodedata.normalize('NFKD', title.lower()) if not unicodedata.combining(c))
    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', plain)]


def sort_tracks(tracks: list) -> list:
    """Whole library order: the '#' group (numbers/symbols) first, then A to Z."""
    return sorted(tracks, key=lambda track: (letter_of(track.title) != '#', _natural_key(track.title)))


def filter_tracks(tracks: list, letter: str = 'All', query: str = '') -> list:
    """Keeps tracks under the chosen index letter whose title contains the search text."""
    query = query.strip().lower()
    return [
        track for track in tracks
        if (letter == 'All' or letter_of(track.title) == letter) and query in track.title.lower()
    ]


def group_by_folder(tracks: list) -> dict[str, list]:
    """Maps each folder path to its tracks, folders ordered by name."""
    groups: dict[str, list] = {}
    for track in tracks:
        groups.setdefault(str(Path(track.path).parent), []).append(track)
    return {folder: sort_tracks(groups[folder]) for folder in sorted(groups, key=lambda f: Path(f).name.lower())}


def fmt_time(seconds: float) -> str:
    """Formats seconds as m:ss, or h:mm:ss for long tracks."""
    total = max(int(seconds or 0), 0)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f'{hours}:{minutes:02d}:{secs:02d}' if hours else f'{minutes}:{secs:02d}'


def make_mix(paths: list[str], seed: int | None = None) -> list[str]:
    """Returns a shuffled copy of the given track paths."""
    mixed = list(paths)
    random.Random(seed).shuffle(mixed)
    return mixed


IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def find_images(roots, limit=60, scan_cap=600):
    """Newest pictures first from the given folders (hidden folders skipped)."""
    found = []
    for root in roots:
        if not Path(root).is_dir():
            continue
        for path in Path(root).rglob('*'):
            if path.suffix.lower() in IMAGE_EXTENSIONS and '/.' not in path.as_posix():
                found.append(path)
                if len(found) >= scan_cap:
                    break
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p) for p in found[:limit]]


def move_item(items: list, old: int, new: int) -> list:
    """Returns a copy of items with the element at `old` moved to `new` (drag-to-reorder)."""
    moved = list(items)
    moved.insert(new, moved.pop(old))
    return moved


def apply_custom_order(tracks: list, order: list[str]) -> list:
    """The user's saved order; songs that appeared since then go at the end in A–Z order."""
    position = {path: i for i, path in enumerate(order)}
    known = sorted((t for t in tracks if t.path in position), key=lambda t: position[t.path])
    return known + sort_tracks([t for t in tracks if t.path not in position])
