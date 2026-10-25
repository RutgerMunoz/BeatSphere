from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlayerState:
    theme: str = 'dark'
    track_paths: list[str] = field(default_factory=list)
    current_index: int = -1
    playing: bool = False

    def set_tracks(self, tracks: list[str]) -> None:
        self.track_paths = list(tracks)
        if self.track_paths and self.current_index < 0:
            self.current_index = 0
        elif not self.track_paths:
            self.current_index = -1

    def current_track(self) -> str | None:
        if not self.track_paths or self.current_index < 0:
            return None
        return self.track_paths[self.current_index]

    def current_track_title(self) -> str:
        track = self.current_track()
        if not track:
            return 'No track selected'
        return track.split('\\')[-1].split('/')[-1]

    def select_track(self, path: str) -> None:
        if path in self.track_paths:
            self.current_index = self.track_paths.index(path)
            self.playing = False

    def next_track(self) -> str | None:
        if not self.track_paths:
            return None
        if self.current_index >= len(self.track_paths) - 1:
            self.current_index = 0
        else:
            self.current_index += 1
        return self.current_track()

    def previous_track(self) -> str | None:
        if not self.track_paths:
            return None
        if self.current_index <= 0:
            self.current_index = len(self.track_paths) - 1
        else:
            self.current_index -= 1
        return self.current_track()

    def toggle_theme(self) -> None:
        self.theme = 'light' if self.theme == 'dark' else 'dark'
