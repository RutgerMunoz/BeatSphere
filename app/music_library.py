from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

supported_extensions = {'.mp3', '.wav', '.ogg', '.m4a'}


@dataclass
class Track:
    path: str
    title: str
    artist: str = "Unknown Artist"
    duration: float = 0.0

    @property
    def display_name(self) -> str:
        return self.title


def _normalize_title(file_path: Path) -> str:
    title = file_path.stem.replace('_', ' ').replace('-', ' ')
    return ' '.join(part.lower() for part in title.split())


def scan_music_files(search_roots: Iterable[str | Path]) -> list[Track]:
    discovered: dict[str, Track] = {}

    for root in search_roots:
        root_path = Path(root)
        if not root_path.exists() or not root_path.is_dir():
            continue

        for candidate in root_path.rglob('*'):
            if not candidate.is_file():
                continue

            if candidate.suffix.lower() not in supported_extensions:
                continue

            file_key = str(candidate.resolve())
            if file_key in discovered:
                continue

            title = _normalize_title(candidate)
            discovered[file_key] = Track(path=file_key, title=title)

    return sorted(discovered.values(), key=lambda item: item.title.lower())
