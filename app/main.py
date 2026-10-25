from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.stacklayout import StackLayout
from kivy.uix.textinput import TextInput

from app.background_playback import AndroidBackgroundPlaybackController
from app.favorite_playlist_ui import FavoritePlaylistScreen
from app.music_library import scan_music_files
from app.now_playing_card import NowPlayingCard
from app.player_state import PlayerState

THEMES = {
    'dark': {
        'bg_start': (7 / 255, 12 / 255, 26 / 255, 1),
        'bg_end': (15 / 255, 45 / 255, 80 / 255, 1),
        'surface': (18 / 255, 24 / 255, 39 / 255, 1),
        'surface_alt': (26 / 255, 34 / 255, 52 / 255, 1),
        'primary': (90 / 255, 168 / 255, 255 / 255, 1),
        'primary_soft': (42 / 255, 121 / 255, 255 / 255, 1),
        'text': (1, 1, 1, 1),
        'muted': (0.75, 0.8, 0.88, 1),
        'shadow': (0.2, 0.4, 0.8, 1),
    },
    'light': {
        'bg_start': (229 / 255, 236 / 255, 255 / 255, 1),
        'bg_end': (191 / 255, 217 / 255, 255 / 255, 1),
        'surface': (1, 1, 1, 1),
        'surface_alt': (235 / 255, 240 / 255, 250 / 255, 1),
        'primary': (55 / 255, 123 / 255, 255 / 255, 1),
        'primary_soft': (96 / 255, 162 / 255, 255 / 255, 1),
        'text': (0.08, 0.10, 0.15, 1),
        'muted': (0.35, 0.42, 0.52, 1),
        'shadow': (0.62, 0.78, 1, 1),
    },
}


class TrackButton(Button):
    def __init__(self, track, **kwargs):
        super().__init__(**kwargs)
        self.track = track
        self.text = track.title


class BeatSphereApp(App):
    def build(self):
        self.state = PlayerState()
        self.sound = None
        self.search_query = ''
        self.background_playback = AndroidBackgroundPlaybackController({'WAKE_LOCK', 'READ_EXTERNAL_STORAGE'})

        self.root = BoxLayout(orientation='vertical', spacing=18, padding=[24, 24, 24, 24])
        self.root.bind(size=self._update_background, pos=self._update_background)
        self.root.canvas.before.clear()

        self.header = BoxLayout(size_hint_y=None, height=72, spacing=14)
        self.title_label = Label(text='BeatSphere', bold=True, font_size='28sp', halign='left')
        self.theme_toggle = Button(text='☾', size_hint_x=None, width=64)
        self.theme_toggle.bind(on_press=self.toggle_theme)
        self.header.add_widget(self.title_label)
        self.header.add_widget(self.theme_toggle)
        self.root.add_widget(self.header)

        self.hero_card = BoxLayout(orientation='vertical', size_hint_y=None, height=220, spacing=10, padding=18)
        self.now_playing_label = Label(text='Now Playing', font_size='18sp', halign='left')
        self.track_title = Label(text='Select a song', font_size='26sp', bold=True, halign='left', valign='middle')
        self.track_artist = Label(text='Your library', halign='left', font_size='16sp')
        self.album_label = Label(text='BeatSphere', halign='left', font_size='14sp')
        self.duration_label = Label(text='0:00', halign='right', font_size='14sp')
        self.hero_card.add_widget(self.now_playing_label)
        self.hero_card.add_widget(self.track_title)
        self.hero_card.add_widget(self.track_artist)
        self.hero_card.add_widget(self.album_label)
        self.root.add_widget(self.hero_card)

        self.progress = Slider(min=0, max=100, value=0, disabled=True)
        self.root.add_widget(self.progress)

        self.controls = BoxLayout(size_hint_y=None, height=82, spacing=14)
        self.shuffle_btn = Button(text='⇄', font_size='20sp')
        self.prev_btn = Button(text='⏮', font_size='22sp')
        self.play_btn = Button(text='▶', font_size='22sp')
        self.next_btn = Button(text='⏭', font_size='22sp')
        self.repeat_btn = Button(text='↻', font_size='20sp')
        self.shuffle_btn.bind(on_press=self.shuffle_tracks)
        self.prev_btn.bind(on_press=self.previous_track)
        self.play_btn.bind(on_press=self.play_current)
        self.next_btn.bind(on_press=self.next_track)
        self.repeat_btn.bind(on_press=self.toggle_repeat)
        self.controls.add_widget(self.shuffle_btn)
        self.controls.add_widget(self.prev_btn)
        self.controls.add_widget(self.play_btn)
        self.controls.add_widget(self.next_btn)
        self.controls.add_widget(self.repeat_btn)
        self.root.add_widget(self.controls)

        self.search_input = TextInput(hint_text='Search your music...', multiline=False, size_hint_y=None, height=52)
        self.search_input.bind(text=self.filter_tracks)
        self.root.add_widget(self.search_input)

        self.library_screen = FavoritePlaylistScreen()
        self.library_label = Label(text='Favorites • Playlists • Recently Played', size_hint_y=None, height=28)
        self.root.add_widget(self.library_label)

        self.status_label = Label(text='Ready to play', size_hint_y=None, height=28)
        self.root.add_widget(self.status_label)

        scroll = ScrollView(do_scroll_x=False)
        self.track_list = StackLayout(size_hint_y=None, spacing=10, padding=[6, 6, 6, 6])
        self.track_list.bind(minimum_height=self.track_list.setter('height'))
        scroll.add_widget(self.track_list)
        self.root.add_widget(scroll)

        self.load_tracks()
        self.apply_theme()
        return self.root

    def _update_background(self, *args):
        self.root.canvas.before.clear()
        palette = THEMES[self.state.theme]
        with self.root.canvas.before:
            Color(*palette['bg_start'])
            Rectangle(pos=self.root.pos, size=self.root.size)

    def apply_theme(self):
        palette = THEMES[self.state.theme]
        self.theme_toggle.text = '☀' if self.state.theme == 'dark' else '☾'

        self.root.canvas.before.clear()
        with self.root.canvas.before:
            Color(*palette['bg_start'])
            Rectangle(pos=self.root.pos, size=self.root.size)

        for widget in [
            self.title_label,
            self.track_title,
            self.track_artist,
            self.album_label,
            self.duration_label,
            self.now_playing_label,
            self.library_label,
            self.status_label,
            self.search_input,
            self.progress,
        ]:
            widget.color = palette['text']

        self.hero_card.canvas.before.clear()
        with self.hero_card.canvas.before:
            Color(*palette['surface'])
            Rectangle(pos=self.hero_card.pos, size=self.hero_card.size)

        self.controls.canvas.before.clear()
        with self.controls.canvas.before:
            Color(*palette['surface'])
            Rectangle(pos=self.controls.pos, size=self.controls.size)

        self.search_input.background_color = palette['surface_alt']
        self.search_input.foreground_color = palette['text']
        self.search_input.cursor_color = palette['primary']

        for button in [self.theme_toggle, self.shuffle_btn, self.prev_btn, self.play_btn, self.next_btn, self.repeat_btn]:
            button.background_color = palette['surface_alt']
            button.color = palette['text']

        self.progress.background_color = palette['surface_alt']
        self.progress.foreground_color = palette['primary']
        self.progress.value_track_color = palette['primary']
        self.progress.value_track_width = 6

        self.track_list.canvas.before.clear()
        with self.track_list.canvas.before:
            Color(*palette['surface'])
            Rectangle(pos=self.track_list.pos, size=self.track_list.size)

    def toggle_theme(self, instance):
        self.state.toggle_theme()
        self.apply_theme()

    def load_tracks(self):
        roots = [
            Path.home() / 'Music',
            Path.home() / 'Downloads',
            Path('C:/Music'),
        ]
        tracks = scan_music_files(roots)
        self.state.set_tracks([track.path for track in tracks])
        self.library_screen.playlists = ['Favorites', 'Chill Mix', 'Workout']
        self.library_screen.favorite_tracks = [track.path for track in tracks[:3]]
        self.library_screen.recent_tracks = [track.path for track in tracks[:5]]
        self.library_label.text = 'Favorites • Playlists • Recently Played'
        self.render_tracks(tracks)

        self.now_playing_card = NowPlayingCard(
            title='Select a song',
            artist='Your BeatSphere library',
            album='BeatSphere',
            duration='0:00',
        )

        if self.state.track_paths:
            self.state.select_track(self.state.track_paths[0])
            self.track_title.text = self.state.current_track_title()
            self.track_artist.text = 'Your BeatSphere library'
            self.album_label.text = 'BeatSphere'
            self.duration_label.text = '0:00'

    def render_tracks(self, tracks):
        self.track_list.clear_widgets()
        for track in tracks:
            btn = TrackButton(track, size_hint=(1, None), height=52)
            btn.bind(on_press=self.select_track)
            self.track_list.add_widget(btn)

    def filter_tracks(self, instance, value):
        query = value.strip().lower()
        self.search_query = query
        if not query:
            tracks = scan_music_files([
                Path.home() / 'Music',
                Path.home() / 'Downloads',
                Path('C:/Music'),
            ])
        else:
            all_tracks = scan_music_files([
                Path.home() / 'Music',
                Path.home() / 'Downloads',
                Path('C:/Music'),
            ])
            tracks = [track for track in all_tracks if query in track.title.lower()]

        self.render_tracks(tracks)

    def select_track(self, instance):
        track_path = instance.track.path if hasattr(instance, 'track') else self.state.current_track()
        if not track_path:
            self.status_label.text = 'No track selected'
            return

        self.state.select_track(track_path)
        title = self.state.current_track_title()
        self.track_title.text = title
        self.track_artist.text = 'Now playing from your library'
        self.album_label.text = 'BeatSphere'
        self.duration_label.text = '0:00'
        self.status_label.text = f'Selected: {title}'
        self.now_playing_card = NowPlayingCard(
            title=title,
            artist='Now playing from your library',
            album='BeatSphere',
            duration='0:00',
        )
        self.play_current(None)

    def play_current(self, instance):
        if not self.state.current_track():
            self.status_label.text = 'No track selected'
            return

        if self.sound is not None:
            self.sound.stop()
        self.sound = SoundLoader.load(self.state.current_track())
        if self.sound is None:
            self.status_label.text = 'Unable to play file in this environment'
            return

        self.sound.play()
        self.state.playing = True
        self.state.background_playing = self.background_playback.prepare_for_background_play(
            self.state.current_track(), {'state': 'playing'}
        )['should_keep_playing']
        self.play_btn.text = '⏸'
        self.duration_label.text = self.now_playing_card.duration
        self.status_label.text = f'Playing: {self.state.current_track_title()}'
        Clock.schedule_interval(self._update_progress, 0.2)

    def on_pause(self):
        if self.sound is not None and self.sound.state == 'play':
            prepared = self.background_playback.prepare_for_background_play(
                self.state.current_track(), {'state': 'playing'}
            )
            if prepared['background_mode'] == 'enabled':
                self.state.background_playing = True
                self.status_label.text = 'Background playback enabled'
                return True
            self.pause_current()
            return True
        return False

    def on_resume(self):
        if self.state.background_playing and self.state.current_track():
            self.status_label.text = f'Resumed: {self.state.current_track_title()}'
        return True

    def pause_current(self):
        if self.sound is not None:
            self.sound.stop()
            self.state.playing = False
            self.play_btn.text = '▶'
            self.status_label.text = f'Paused: {self.state.current_track_title()}'

    def shuffle_tracks(self, instance):
        self.state.track_paths = self.state.track_paths[::-1]
        self.state.current_index = 0
        self.status_label.text = 'Shuffled your library'

    def toggle_repeat(self, instance):
        self.state.background_playing = not self.state.background_playing
        self.status_label.text = 'Repeat mode toggled'

    def _update_progress(self, dt):
        if self.sound is None or not self.sound.state == 'play':
            return
        duration = max(self.sound.length, 1)
        position = min(self.sound.get_pos() / duration * 100, 100)
        self.progress.value = position

    def next_track(self, instance):
        next_path = self.state.next_track()
        if not next_path:
            return
        self.sound = SoundLoader.load(next_path)
        self.track_title.text = self.state.current_track_title()
        self.status_label.text = f'Playing: {self.state.current_track_title()}'
        self.play_current(None)

    def previous_track(self, instance):
        prev_path = self.state.previous_track()
        if not prev_path:
            return
        self.sound = SoundLoader.load(prev_path)
        self.track_title.text = self.state.current_track_title()
        self.status_label.text = f'Playing: {self.state.current_track_title()}'
        self.play_current(None)


if __name__ == '__main__':
    BeatSphereApp().run()
