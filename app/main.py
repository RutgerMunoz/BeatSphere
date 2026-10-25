import os
from pathlib import Path

from kivy.app import App
from kivy.core.audio import SoundLoader
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.stacklayout import StackLayout
from kivy.uix.textinput import TextInput


class TrackButton(Button):
    def __init__(self, file_path, **kwargs):
        super().__init__(**kwargs)
        self.file_path = file_path
        self.text = Path(file_path).name


class BeatSphereApp(App):
    def build(self):
        self.root = BoxLayout(orientation='vertical', spacing=10, padding=20)
        self.current_track = None
        self.current_sound = None
        self.track_files = self.scan_music_files()

        self.status_label = Label(text='No track selected', size_hint_y=None, height=40)
        self.root.add_widget(self.status_label)

        controls = BoxLayout(size_hint_y=None, height=60, spacing=10)
        controls.add_widget(Button(text='Play', on_press=self.play_selected))
        controls.add_widget(Button(text='Pause', on_press=self.pause_current))
        controls.add_widget(Button(text='Stop', on_press=self.stop_current))
        self.root.add_widget(controls)

        self.search_input = TextInput(hint_text='Search music...', size_hint_y=None, height=40)
        self.search_input.bind(text=self.filter_tracks)
        self.root.add_widget(self.search_input)

        scroll = ScrollView(size_hint=(1, 1))
        self.track_list = StackLayout(size_hint_y=None, spacing=5, padding=5)
        self.track_list.bind(minimum_height=self.track_list.setter('height'))
        scroll.add_widget(self.track_list)
        self.root.add_widget(scroll)

        self.render_tracks(self.track_files)
        return self.root

    def scan_music_files(self):
        music_dirs = [
            Path.home() / 'Music',
            Path.home() / 'Downloads',
            Path('C:/Music'),
        ]

        supported_ext = {'.mp3', '.wav', '.ogg', '.m4a'}
        files = []

        for directory in music_dirs:
            if not directory.exists():
                continue
            for file_path in directory.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in supported_ext:
                    files.append(str(file_path))

        return sorted(files)

    def render_tracks(self, tracks):
        self.track_list.clear_widgets()
        for track in tracks:
            btn = TrackButton(track, size_hint=(1, None), height=40)
            btn.bind(on_press=self.select_track)
            self.track_list.add_widget(btn)

    def filter_tracks(self, instance, value):
        query = value.strip().lower()
        if not query:
            self.render_tracks(self.track_files)
            return

        filtered = [track for track in self.track_files if query in Path(track).name.lower()]
        self.render_tracks(filtered)

    def select_track(self, instance):
        self.current_track = instance.file_path
        self.status_label.text = f'Selected: {Path(self.current_track).name}'

    def play_selected(self, instance):
        if not self.current_track:
            self.status_label.text = 'No track selected'
            return

        if self.current_sound and self.current_sound.state == 'play':
            self.current_sound.stop()

        self.current_sound = SoundLoader.load(self.current_track)
        if self.current_sound is None:
            self.status_label.text = 'Unable to load this audio file'
            return

        self.current_sound.play()
        self.status_label.text = f'Playing: {Path(self.current_track).name}'

    def pause_current(self, instance):
        if self.current_sound is not None:
            self.current_sound.stop()
            self.status_label.text = f'Paused: {Path(self.current_track).name}'

    def stop_current(self, instance):
        if self.current_sound is not None:
            self.current_sound.stop()
            self.current_sound.unload()
            self.current_sound = None
        self.status_label.text = 'Stopped'


if __name__ == '__main__':
    BeatSphereApp().run()
