"""BeatSphere main application entry point.

Wires the music library, playback state and the animated Kivy interface:
Songs (whole library, A–Z), Playlists, Folders, Mix and Settings tabs, a mini
player that appears at the bottom while a song plays, and a full-screen Now
Playing view that slides up when the mini player is tapped.
"""

import hashlib
import os
import shutil
import threading
import time
import weakref
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.logger import Logger
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, DictProperty, StringProperty
from kivy.resources import resource_find
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.utils import platform

from app.android_files import delete_audio_file, media_store_audio_paths, pick_image_from_system
from app.audio import create_player
from app.media_controls import create_media_controls
from app.background_playback import AndroidBackgroundPlaybackController
from app.favorite_playlist_ui import FavoritePlaylistScreen
from app.library_views import (LETTERS, apply_custom_order, filter_tracks, fmt_time, group_by_folder, make_mix,
                               sort_tracks)
from app.music_library import extract_cover, read_metadata, scan_music_files, tracks_from_index
from app.player_state import PlayerState
from app.library_views import find_images
from app.ui.brand import WORDMARK, IntroOverlay, LivingLogo
from app.ui.dialogs import ConfirmDialog, InfoDialog, OptionsSheet, SongPicker, TextPrompt
from app.ui.image_picker import ImagePicker
from app.ui.now_playing import MiniPlayer, NowPlayingView
from app.ui.theme import FONT_CHOICES, ICON_FONT, THEMES, songs_label
from app.ui.widgets import (Card, ImageButton, NavBar, PlaylistTile, Pressable, SongList, ThemedInput, ThemedLabel,
                            ThemeSwatch, animate, gradient_texture)

HEADER_HEIGHT = dp(56)
TABS = [('Songs', '♫'), ('Playlists', '☰'), ('Folders', '▤'), ('Mix', '⇄'), ('Settings', '⚙')]


def icon_text(glyph, text):
    """Markup mixing an icon-font glyph with normal text in one label."""
    return f'[font={ICON_FONT}]{glyph}[/font]  {text}'


class BeatSphereApp(App):
    """Main app class that builds the BeatSphere music player interface."""

    icon = 'assets/icon.png'
    title = 'BeatSphere'
    palette = DictProperty(THEMES['Ocean'])
    font = StringProperty('Roboto')
    motion = BooleanProperty(True)

    def build(self):
        self.state = PlayerState()
        self.library_screen = FavoritePlaylistScreen()
        self.background_playback = AndroidBackgroundPlaybackController({'WAKE_LOCK', 'READ_EXTERNAL_STORAGE'})
        self.player = create_player(on_complete=self._song_finished_in_background)
        self.in_background = False  # Kivy's clock doesn't run while the app is in the background
        self.ui_stale = False  # the screen needs a refresh after background playback changes
        self.media = None  # notification/lock-screen controls, created on first play (Android setup is slow)
        self.loaded_path = None
        self.tracks = []
        self.titles = {}
        self.meta = {}
        self.covers = {}
        self.meta_store = JsonStore(os.path.join(self.user_data_dir, 'song_info.json'))
        self.song_info = dict(self.meta_store.get('songs')['info']) if self.meta_store.exists('songs') else {}
        self.wallpapers_loaded = False
        self.custom_covers = {}  # song path -> user-chosen image
        self.playlist_covers = {}  # playlist name -> user-chosen image
        self.custom_titles = {}  # song path -> name the user gave it (the file itself is never renamed)
        self.file_titles = {}  # song path -> name derived from the file, to undo a rename
        self.hidden = set()  # songs removed from BeatSphere but still on the phone
        self.custom_order = []  # "My order" for the Songs tab
        self.letter = 'All'
        self.editing_songs = False
        self.song_lists = weakref.WeakSet()
        self.back_action = None
        self.store = JsonStore(os.path.join(self.user_data_dir, 'settings.json'))
        settings = self.store.get('settings') if self.store.exists('settings') else {}
        self.theme_name = settings.get('theme') if settings.get('theme') in THEMES else 'Ocean'
        self.palette = THEMES[self.theme_name]
        self.font = settings.get('font', 'Roboto')
        self.wallpaper = settings.get('wallpaper', '')
        self.motion = settings.get('motion', True)
        self.sort_mode = settings.get('sort', 'az')
        self._load_library_data()
        Window.softinput_mode = 'below_target'  # keep text fields visible above the keyboard

        self.root = FloatLayout()
        self.root.bind(size=self._draw_background, pos=self._draw_background)
        self.bind(palette=self._draw_background)

        column = BoxLayout(orientation='vertical', padding=[dp(14), dp(12), dp(14), dp(10)], spacing=dp(10))
        self.header = self._build_header()
        column.add_widget(self.header)
        self.pages = {'Songs': self._build_songs(), 'Playlists': self._page(), 'Folders': self._page(),
                      'Mix': self._build_mix(), 'Settings': self._build_settings()}
        self.content = BoxLayout()
        self.content.add_widget(self.pages['Songs'])
        column.add_widget(self.content)
        self.mini = MiniPlayer()
        column.add_widget(self.mini)
        self.nav = NavBar(TABS, self.show_tab)
        column.add_widget(self.nav)
        self.root.add_widget(column)

        self.now_playing = NowPlayingView(opacity=0)
        self.root.add_widget(self.now_playing)
        self.root.bind(height=lambda *_: None if self.now_playing.is_open else setattr(self.now_playing, 'y', -self.root.height - dp(10)))

        self.intro = IntroOverlay(on_done=self.root.remove_widget) if self.motion else None
        if self.intro:
            self.root.add_widget(self.intro)
        self.song_count.text = 'Loading your music…'
        self.started_at = time.time()
        Clock.schedule_interval(self._tick, 0.25)
        Window.bind(on_keyboard=self._on_keyboard)
        if platform == 'android':
            self.request_android_permissions()
        return self.root

    # ---------- layout ----------

    def _build_header(self):
        header = BoxLayout(size_hint_y=None, height=HEADER_HEIGHT, spacing=dp(12))
        header.add_widget(LivingLogo(size_hint_x=None, width=dp(52)))
        texts = BoxLayout(orientation='vertical')
        hour = datetime.now().hour
        greeting = 'Good morning' if hour < 12 else 'Good afternoon' if hour < 19 else 'Good evening'
        texts.add_widget(ThemedLabel(text=greeting, role='muted', font_size='13sp'))
        name = BoxLayout()
        name.add_widget(Image(source=WORDMARK, fit_mode='contain', size_hint_x=None, width=dp(150)))  # 5:1 wordmark
        name.add_widget(Widget())
        texts.add_widget(name)
        header.add_widget(texts)
        return header

    def _page(self):
        return BoxLayout(orientation='vertical', spacing=dp(10))

    def watch_scroll(self, view):
        """Hides the header while a list is scrolled down; shows it again at the very top."""
        view.bind(scroll_y=lambda *_: self._on_scroll(view))
        return view

    def _on_scroll(self, view):
        if view.children and view.children[0].height > view.height:  # lists too short to scroll keep the header
            self.set_header_visible(view.scroll_y >= 0.995)

    def set_header_visible(self, visible):
        target = HEADER_HEIGHT if visible else 0
        if getattr(self, '_header_target', HEADER_HEIGHT) != target:
            self._header_target = target
            animate(self.header, 0.25, 'out_cubic', height=target, opacity=1 if visible else 0)

    def show_tab(self, name):
        """Switches tabs with a slide-and-fade entrance."""
        self.back_action = None
        self.set_header_visible(True)
        if name == 'Settings' and not self.wallpapers_loaded:
            self.render_wallpapers()
        if name in ('Playlists', 'Folders'):
            (self.render_playlists if name == 'Playlists' else self.render_folders)()
        self.nav.select(name)
        page = self.pages[name]
        self.content.clear_widgets()
        self.content.add_widget(page)
        page.opacity = 0
        self.content.padding = [0, dp(24), 0, 0]
        animate(page, 0.3, 'out_quad', opacity=1)
        animate(self.content, 0.35, 'out_cubic', padding=[0, 0, 0, 0])

    def make_song_list(self, playlist=None, on_reorder=None):
        songs = SongList(self.play_path, on_hold=lambda path: self.song_options(path, playlist), on_reorder=on_reorder)
        self.song_lists.add(songs)
        self.watch_scroll(songs)
        return songs

    def _build_songs(self):
        page = self._page()
        self.search_input = ThemedInput(hint_text='Search songs...', size_hint_y=None, height=dp(48))
        self.search_input.bind(text=lambda *_: self.render_songs())
        page.add_widget(self.search_input)

        letters_scroll = ScrollView(do_scroll_y=False, size_hint_y=None, height=dp(40), bar_width=0)
        letters = BoxLayout(size_hint_x=None, spacing=dp(6))
        letters.bind(minimum_width=letters.setter('width'))
        self.letter_chips = {}
        for letter in LETTERS:
            chip = Pressable(text=letter, size_hint_x=None, width=dp(54) if letter == 'All' else dp(40),
                             radius=dp(20), selected=letter == 'All', bold=True)
            chip.bind(on_release=lambda c: self.choose_letter(c.text))
            self.letter_chips[letter] = chip
            letters.add_widget(chip)
        letters_scroll.add_widget(letters)
        page.add_widget(letters_scroll)

        actions = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.song_count = ThemedLabel(role='muted', font_size='13sp')
        shuffle = Pressable(text=icon_text('⇄', 'Shuffle'), markup=True, size_hint_x=None, width=dp(108),
                            radius=dp(22))
        play_all = Pressable(text=icon_text('▶', 'Play all'), markup=True, size_hint_x=None, width=dp(116),
                             radius=dp(22), gradient=True, bold=True)
        shuffle.bind(on_release=lambda *_: self.play_collection(self.song_list.paths, shuffled=True))
        play_all.bind(on_release=lambda *_: self.play_collection(self.song_list.paths))
        for widget in (self.song_count, shuffle, play_all):
            actions.add_widget(widget)
        page.add_widget(actions)

        order = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        self.sort_chips = {}
        for mode, label in (('az', 'A–Z'), ('custom', 'My order')):
            chip = Pressable(text=label, size_hint_x=None, width=dp(64) if mode == 'az' else dp(96), radius=dp(19),
                             selected=self.sort_mode == mode)
            chip.bind(on_release=lambda _, m=mode: self.set_sort(m))
            self.sort_chips[mode] = chip
            order.add_widget(chip)
        order.add_widget(Widget())
        scan = Pressable(text='↻', icon=True, font_size='20sp', size_hint_x=None, width=dp(44), radius=dp(19))
        scan.bind(on_release=lambda *_: self.scan_library())
        order.add_widget(scan)
        self.edit_order_btn = Pressable(text=icon_text('≡', 'Reorder'), markup=True, size_hint_x=None, width=dp(116),
                                        radius=dp(19))
        self.edit_order_btn.bind(on_release=lambda *_: self.toggle_song_editing())
        order.add_widget(self.edit_order_btn)
        page.add_widget(order)

        self.song_list = self.make_song_list(on_reorder=self._songs_reordered)
        page.add_widget(self.song_list)
        return page

    def set_sort(self, mode):
        self.sort_mode = mode
        for name, chip in self.sort_chips.items():
            chip.selected = name == mode
        if mode == 'az' and self.editing_songs:
            self.toggle_song_editing()
        self._save_settings()
        self.render_songs()

    def toggle_song_editing(self):
        """Reorder mode for the whole library: switches to "My order" and shows every song."""
        self.editing_songs = not self.editing_songs
        if self.editing_songs:
            if self.sort_mode != 'custom':
                self.set_sort('custom')
            self.search_input.text = ''
            self.choose_letter('All')
        self.edit_order_btn.text = icon_text('✓', 'Done') if self.editing_songs else icon_text('≡', 'Reorder')
        self.edit_order_btn.selected = self.editing_songs
        self.song_list.set_editing(self.editing_songs)

    def _songs_reordered(self, paths):
        self.custom_order = paths
        self._save_library_data()

    def _build_mix(self):
        page = self._page()
        page.add_widget(ThemedLabel(text='Made for you', bold=True, font_size='20sp', size_hint_y=None, height=dp(30)))
        heroes = GridLayout(cols=2, size_hint_y=None, height=dp(200), spacing=dp(10))
        for title, sub, source, rgb, glyph in [('Shuffle all', 'Your whole library', 'all', (77, 163, 255), '⇄'),
                                               ('Favorites mix', 'Songs you love', 'favorites', (255, 95, 162), '♥'),
                                               ('Recently played', 'Pick up again', 'recent', (46, 229, 157), '↻'),
                                               ('Discover', '20 random songs', 'discover', (255, 166, 77), '✦')]:
            tile = PlaylistTile(title, sub, rgb, glyph=glyph)
            tile.bind(on_release=lambda _, s=source: self.start_mix(s))
            heroes.add_widget(tile)
        page.add_widget(heroes)
        self.mix_label = ThemedLabel(text='Tap a mix to start', role='muted', font_size='13sp',
                                     size_hint_y=None, height=dp(22))
        page.add_widget(self.mix_label)
        self.mix_list = self.make_song_list()
        page.add_widget(self.mix_list)
        return page

    def _build_settings(self):
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
        box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10), padding=[0, 0, 0, dp(16)])
        box.bind(minimum_height=box.setter('height'))

        box.add_widget(self._section('Color style'))
        themes = GridLayout(cols=2, size_hint_y=None, spacing=dp(10), row_default_height=dp(84), row_force_default=True)
        themes.bind(minimum_height=themes.setter('height'))
        self.swatches = {}
        for name, palette in THEMES.items():
            swatch = ThemeSwatch(name, palette, selected=name == self.theme_name)
            swatch.bind(on_release=lambda s: self.set_setting('theme', s.name))
            self.swatches[name] = swatch
            themes.add_widget(swatch)
        box.add_widget(themes)

        box.add_widget(self._section('Font'))
        fonts = GridLayout(cols=2, size_hint_y=None, spacing=dp(8), row_default_height=dp(50), row_force_default=True)
        fonts.bind(minimum_height=fonts.setter('height'))
        self.font_chips = {}
        for label, font in FONT_CHOICES:
            if font != 'Roboto' and not resource_find(font):
                continue
            chip = Pressable(text=label, font_size='16sp', radius=dp(18), selected=font == self.font, font_file=font)
            chip.bind(on_release=lambda c: self.set_setting('font', c.font_file))
            self.font_chips[font] = chip
            fonts.add_widget(chip)
        box.add_widget(fonts)

        box.add_widget(self._section('Wallpaper'))
        wall_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        browse = Pressable(text='Photos, Drive, Gallery…', radius=dp(18), gradient=True, bold=True)
        browse.bind(on_release=lambda *_: self.browse_system_photos(
            os.path.join(self.user_data_dir, 'wallpapers'), lambda path: self.set_setting('wallpaper', path)))
        none_btn = Pressable(text='No wallpaper', size_hint_x=0.6, radius=dp(18))
        none_btn.bind(on_release=lambda *_: self.set_setting('wallpaper', ''))
        wall_row.add_widget(browse)
        wall_row.add_widget(none_btn)
        box.add_widget(wall_row)
        self.wallpaper_grid = GridLayout(cols=3, size_hint_y=None, spacing=dp(8), row_default_height=dp(120),
                                         row_force_default=True)
        self.wallpaper_grid.bind(minimum_height=self.wallpaper_grid.setter('height'))
        box.add_widget(self.wallpaper_grid)
        self.wallpaper_hint = ThemedLabel(text='', role='muted', font_size='13sp', size_hint_y=None, height=dp(24))
        box.add_widget(self.wallpaper_hint)

        box.add_widget(self._section('Music library'))
        scan_btn = Pressable(text=icon_text('↻', 'Scan for music'), markup=True, size_hint_y=None, height=dp(46),
                             radius=dp(18))
        scan_btn.bind(on_release=lambda *_: self.scan_library())
        box.add_widget(scan_btn)

        box.add_widget(self._section('Hidden songs'))
        self.hidden_btn = Pressable(text='', size_hint_y=None, height=dp(46), radius=dp(18))
        self.hidden_btn.bind(on_release=lambda *_: self.restore_hidden())
        box.add_widget(self.hidden_btn)
        self._sync_hidden_btn()

        box.add_widget(self._section('Motion'))
        self.motion_btn = Pressable(text='', size_hint_y=None, height=dp(46), radius=dp(18))
        self.motion_btn.bind(on_release=lambda *_: self.set_setting('motion', not self.motion))
        box.add_widget(self.motion_btn)
        self._sync_motion_btn()

        about = Card(size_hint_y=None, height=dp(76), padding=dp(12), spacing=dp(12))
        about.add_widget(Image(source='assets/icon.png', size_hint_x=None, width=dp(52)))
        about_texts = BoxLayout(orientation='vertical')
        about_texts.add_widget(ThemedLabel(text='BeatSphere', bold=True, font_size='16sp'))
        about_texts.add_widget(ThemedLabel(text='Version 1.0.3', role='muted', font_size='12sp'))
        about.add_widget(about_texts)
        box.add_widget(Widget(size_hint_y=None, height=dp(6)))
        box.add_widget(about)
        scroll.add_widget(box)
        page = self._page()
        page.add_widget(self.watch_scroll(scroll))
        return page

    def _section(self, text):
        return ThemedLabel(text=text, bold=True, font_size='18sp', size_hint_y=None, height=dp(34), valign='bottom')

    def show_detail(self, page, title, tracks, back, extras=(), playlist=None, on_reorder=None):
        """Replaces a tab with a song list page that has a back button (Android back works too)."""
        self.back_action = back
        page.clear_widgets()
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        back_btn = Pressable(text='◀', icon=True, size_hint_x=None, width=dp(46), radius=dp(23))
        back_btn.bind(on_release=lambda *_: back())
        top.add_widget(back_btn)
        top.add_widget(ThemedLabel(text=title, bold=True, font_size='20sp', shorten=True))
        for widget in extras:
            top.add_widget(widget)
        page.add_widget(top)
        paths = [track.path for track in tracks]
        actions = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        actions.add_widget(ThemedLabel(text=songs_label(len(tracks)), role='muted', font_size='13sp'))
        shuffle = Pressable(text=icon_text('⇄', 'Shuffle'), markup=True, size_hint_x=None, width=dp(108), radius=dp(22))
        play = Pressable(text=icon_text('▶', 'Play'), markup=True, size_hint_x=None, width=dp(96), radius=dp(22),
                         gradient=True, bold=True)
        shuffle.bind(on_release=lambda *_: self.play_collection(paths, shuffled=True))
        play.bind(on_release=lambda *_: self.play_collection(paths))
        songs = self.make_song_list(playlist=playlist, on_reorder=on_reorder)
        if on_reorder is not None:
            reorder = Pressable(text='≡', icon=True, font_size='20sp', size_hint_x=None, width=dp(44), radius=dp(22))

            def toggle(*_):
                songs.set_editing(not songs.editing)
                reorder.selected = songs.editing
                reorder.text = '✓' if songs.editing else '≡'
            reorder.bind(on_release=toggle)
            actions.add_widget(reorder)
        actions.add_widget(shuffle)
        actions.add_widget(play)
        page.add_widget(actions)
        songs.set_tracks(tracks)
        page.add_widget(songs)

    # ---------- library ----------

    def music_roots(self):
        """Folders to scan; on Android, Path.home() is the app's private dir, not shared storage."""
        if platform == 'android':
            return [Path('/storage/emulated/0/Music'), Path('/storage/emulated/0/Download')]
        return [Path.home() / 'Music', Path.home() / 'Downloads', Path('C:/Music')]

    def picture_roots(self):
        """Folders searched for wallpaper images."""
        if platform == 'android':
            base = Path('/storage/emulated/0')
            return [base / 'Pictures', base / 'DCIM', base / 'Download']
        return [Path.home() / 'Pictures']

    def request_android_permissions(self):
        """Asks for audio and image access at runtime (READ_MEDIA_* on Android 13+, storage before that)."""
        from android.permissions import Permission, check_permission, request_permissions

        self.had_music_access = any(check_permission(p) for p in
                                    (Permission.READ_MEDIA_AUDIO, Permission.READ_EXTERNAL_STORAGE))
        request_permissions(
            [Permission.READ_MEDIA_AUDIO, Permission.READ_MEDIA_IMAGES,
             Permission.READ_EXTERNAL_STORAGE, Permission.POST_NOTIFICATIONS],
            self._on_android_permissions,
        )

    def _on_android_permissions(self, permissions, grants):
        """Rescans once access is granted; the callback runs off the UI thread."""
        if any(grants) and not self.had_music_access:  # already allowed: the startup scan saw everything
            Clock.schedule_once(lambda dt: (self.load_tracks(),
                                            self.render_wallpapers() if self.wallpapers_loaded else None))

    def load_tracks(self):
        """Scans the device, refreshes the tabs, then reads artist tags in the background."""
        indexed = self._indexed_songs()
        if indexed:
            found = tracks_from_index(indexed)
            threading.Thread(target=self._add_unindexed, args=(found,), daemon=True).start()
        else:
            found = scan_music_files(self.music_roots())
        self._show_tracks(found)

    def _add_unindexed(self, found):
        """Folder walk after the fast list: adds songs Android hasn't finished indexing (new downloads)."""
        known = {track.path for track in found}
        extra = [track for track in scan_music_files(self.music_roots()) if track.path not in known]
        if extra:
            Clock.schedule_once(lambda dt: self._show_tracks(found + extra))

    def _show_tracks(self, found):
        tracks = [track for track in found if track.path not in self.hidden]
        self.file_titles = {track.path: track.title for track in tracks}
        for track in tracks:
            track.title = self.custom_titles.get(track.path, track.title)
        self.tracks = sort_tracks(tracks)
        self.titles = {track.path: track.title for track in self.tracks}
        if not self.state.track_paths:
            self.state.set_tracks([track.path for track in self.tracks])
        self.render_songs()
        Logger.info('BeatSphere: %d songs listed %.1fs after start', len(self.tracks), time.time() - self.started_at)
        threading.Thread(target=self._read_all_metadata, args=(list(self.tracks),), daemon=True).start()

    def _indexed_songs(self):
        """All songs Android has indexed (any folder, SD card); empty off Android or if the query fails."""
        try:
            return media_store_audio_paths()
        except Exception:
            import traceback
            traceback.print_exc()
            return []

    def scan_library(self):
        before = len(self.tracks)
        self.load_tracks()
        found = len(self.tracks)
        new = found - before
        self.toast(f'Found {songs_label(found)}' + (f' · {new} new' if new > 0 else ''))

    def browse_system_photos(self, folder, on_picked):
        """Android's own picker: Google Photos, Drive, Gallery, Files…"""
        if platform != 'android':
            self.toast('Opens Photos, Drive and Gallery on the phone')
            return
        pick_image_from_system(folder, lambda path: Clock.schedule_once(lambda dt: on_picked(path) if path else None))

    def _read_all_metadata(self, tracks):
        """Artist/album/length and embedded cover per song, cached between launches by file size and date."""
        changed = False
        for track in tracks:
            try:
                stat = os.stat(track.path)
            except OSError:
                continue
            stamp = [stat.st_size, int(stat.st_mtime)]
            cached = self.song_info.get(track.path)
            if cached and cached['stamp'] == stamp and (not cached['cover'] or os.path.exists(cached['cover'])):
                self.meta[track.path] = cached['meta']
                self.covers.setdefault(track.path, cached['cover'])
            else:
                self.meta[track.path] = read_metadata(track.path)
                cover = self.cover_for(track.path)  # embedded art -> list avatars
                self.song_info[track.path] = {'stamp': stamp, 'meta': self.meta[track.path], 'cover': cover}
                changed = True
                time.sleep(0.002)  # yield to the UI thread between files
        if changed:
            Clock.schedule_once(lambda dt: self.meta_store.put('songs', info=self.song_info))
        Clock.schedule_once(lambda dt: self.refresh_lists())

    def refresh_lists(self):
        for songs in list(self.song_lists):
            songs.refresh_rows()

    def folder_name(self, path):
        return Path(path).parent.name

    def render_songs(self):
        ordered = apply_custom_order(self.tracks, self.custom_order) if self.sort_mode == 'custom' else self.tracks
        shown = filter_tracks(ordered, self.letter, self.search_input.text)
        self.song_list.set_tracks(shown)
        total = len(self.tracks)
        if not total:
            self.song_count.text = 'No songs found in Music or Download'
        elif len(shown) == total:
            self.song_count.text = songs_label(total)
        else:
            self.song_count.text = f'{len(shown)} of {total}'

    def choose_letter(self, letter):
        self.letter = letter
        for name, chip in self.letter_chips.items():
            chip.selected = name == letter
        self.render_songs()

    def _tracks_for(self, paths):
        by_path = {track.path: track for track in self.tracks}
        return [by_path[path] for path in paths if path in by_path]

    def render_playlists(self):
        page = self.pages['Playlists']
        self.back_action = None
        page.clear_widgets()
        create = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.new_playlist_input = ThemedInput(hint_text='New playlist name')
        add = Pressable(text='+ Create', size_hint_x=None, width=dp(104), radius=dp(18), gradient=True, bold=True)
        add.bind(on_release=self.create_playlist)
        reorder = Pressable(text='≡', icon=True, font_size='20sp', size_hint_x=None, width=dp(46), radius=dp(23))
        reorder.bind(on_release=lambda *_: self.reorder_playlists())
        create.add_widget(self.new_playlist_input)
        create.add_widget(add)
        if len(self.library_screen.playlists) > 1:
            create.add_widget(reorder)
        page.add_widget(create)
        grid = GridLayout(cols=2, size_hint_y=None, spacing=dp(10), row_default_height=dp(150), row_force_default=True)
        grid.bind(minimum_height=grid.setter('height'))
        favorites = PlaylistTile('Favorites', songs_label(len(self.library_screen.favorite_tracks)),
                                 (255, 95, 162), glyph='♥', image=self.playlist_cover('Favorites'),
                                 on_menu=self.playlist_menu)
        favorites.bind(on_release=lambda *_: self.open_favorites())
        grid.add_widget(favorites)
        for card in self.library_screen.playlist_cards:
            tile = PlaylistTile(card['name'], songs_label(card['track_count']), card['cover_color'],
                                image=self.playlist_cover(card['name']), on_menu=self.playlist_menu)
            tile.bind(on_release=lambda t: self.open_playlist(t.name))
            grid.add_widget(tile)
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
        scroll.add_widget(grid)
        page.add_widget(self.watch_scroll(scroll))

    def reorder_playlists(self):
        """Shows the playlists as a list with ≡ handles; drag to set their order."""
        page = self.pages['Playlists']
        rows = [SimpleNamespace(path=card['name'], title=card['name'], subtitle=songs_label(card['track_count']),
                                cover=self.playlist_cover(card['name'])) for card in self.library_screen.playlist_cards]

        def reordered(names):
            self.library_screen.set_playlist_order(names)
            self._save_library_data()

        self.back_action = self.render_playlists
        page.clear_widgets()
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        top.add_widget(ThemedLabel(text=f'Drag [font={ICON_FONT}]≡[/font] to reorder', markup=True, bold=True, font_size='18sp'))
        done = Pressable(text=icon_text('✓', 'Done'), markup=True, size_hint_x=None, width=dp(100), radius=dp(20),
                         gradient=True, bold=True)
        done.bind(on_release=lambda *_: self.render_playlists())
        top.add_widget(done)
        page.add_widget(top)
        playlists = SongList(lambda *_: None, on_reorder=reordered, songs_only=False)
        playlists.set_tracks(rows)
        playlists.set_editing(True)
        page.add_widget(playlists)

    def _options_button(self, open_menu):
        btn = Pressable(text='⋯', icon=True, font_size='22sp', size_hint_x=None, width=dp(46), radius=dp(23))
        btn.bind(on_release=lambda *_: open_menu())
        return btn

    def open_favorites(self):
        def reordered(paths):
            self.library_screen.favorite_tracks = paths
            self._save_library_data()

        self.show_detail(self.pages['Playlists'], 'Favorites', self._tracks_for(self.library_screen.favorite_tracks),
                         self.render_playlists, [self._options_button(lambda: self.playlist_menu('Favorites'))],
                         playlist='Favorites', on_reorder=reordered)

    def open_playlist(self, name):
        def reordered(paths):
            self.library_screen.playlist_tracks[name] = paths
            self._save_library_data()

        self.show_detail(self.pages['Playlists'], name,
                         self._tracks_for(self.library_screen.playlist_tracks.get(name, [])), self.render_playlists,
                         [self._options_button(lambda: self.playlist_menu(name))], playlist=name, on_reorder=reordered)

    def _playlist_paths(self, name):
        if name == 'Favorites':
            return self.library_screen.favorite_tracks
        return self.library_screen.playlist_tracks.setdefault(name, [])

    def playlist_menu(self, name):
        """⋮ menu for a playlist (on its card and inside it)."""
        options = [(icon_text('+', 'Add songs'), lambda: self.add_songs_to(name))]
        if name != 'Favorites':
            options.append((icon_text('✎', 'Rename'), lambda: self.rename_playlist(name)))
        options += [(icon_text('▣', 'Change cover'), lambda: self.pick_playlist_cover(name)),
                    (icon_text('ℹ', 'Info'), lambda: self.playlist_info(name))]
        if name != 'Favorites':
            options.append((icon_text('✖', 'Delete playlist'), lambda: self.delete_playlist(name)))
        OptionsSheet(name, options).open()

    def add_songs_to(self, name):
        """Pick several songs at once to add to a playlist (songs already in it aren't listed)."""
        present = set(self._playlist_paths(name))

        def added(paths):
            if name == 'Favorites':
                self.library_screen.favorite_tracks.extend(paths)
            else:
                for path in paths:
                    self.library_screen.add_track_to_playlist(name, path)
            self._save_library_data()
            self.toast(f'Added {songs_label(len(paths))} to “{name}”')
            (self.open_favorites if name == 'Favorites' else lambda: self.open_playlist(name))()

        subtitles = {t.path: self.meta.get(t.path, {}).get('artist') or self.folder_name(t.path) for t in self.tracks}
        SongPicker(f'Add songs to “{name}”', [t for t in self.tracks if t.path not in present], subtitles,
                   added).open()

    def playlist_info(self, name):
        paths = [p for p in self._playlist_paths(name) if p in self.titles]
        total = sum(self.meta.get(p, {}).get('duration', 0) for p in paths)
        InfoDialog(name, [('Songs', songs_label(len(paths))), ('Total length', fmt_time(total)),
                          ('Cover', 'Your picture' if self.playlist_cover(name) else 'Default')]).open()

    def rename_playlist(self, name):
        def save(new_name):
            if new_name == name:
                return
            if not self.library_screen.rename_playlist(name, new_name):
                self.toast('That name is empty or already used')
                return
            if name in self.playlist_covers:
                self.playlist_covers[new_name] = self.playlist_covers.pop(name)
            self._save_library_data()
            self.open_playlist(new_name)

        TextPrompt('Rename playlist', name, save).open()

    def delete_playlist(self, name):
        def delete():
            screen = self.library_screen
            screen.playlists.remove(name)
            screen.playlist_tracks.pop(name, None)
            screen.playlist_cover_map.pop(name, None)
            screen.set_playlist_order(list(screen.playlists))
            self._forget_image(self.playlist_covers.pop(name, None))
            self._save_library_data()
            self.render_playlists()
            self.toast(f'Deleted playlist “{name}”')

        ConfirmDialog(f'Delete “{name}”?', 'The playlist is removed. Your songs stay on your phone and in '
                      'BeatSphere.', 'Delete', delete).open()

    def create_playlist(self, *_):
        name = (self.new_playlist_input.text or '').strip()
        if name and self.library_screen.create_playlist(name):
            self._save_library_data()
            self.render_playlists()

    def render_folders(self):
        page = self.pages['Folders']
        self.back_action = None
        page.clear_widgets()
        column = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8))
        column.bind(minimum_height=column.setter('height'))
        for folder, tracks in group_by_folder(self.tracks).items():
            name = Path(folder).name or folder
            row = Pressable(text=f'{icon_text("▤", name)}\n[size=12sp]{songs_label(len(tracks))}[/size]', markup=True,
                            size_hint_y=None, height=dp(64), radius=dp(18), halign='left', valign='middle',
                            padding=[dp(18), 0])
            row.bind(size=lambda w, *_: setattr(w, 'text_size', w.size))
            row.bind(on_release=lambda _, n=name, t=tracks: self.show_detail(page, n, t, self.render_folders))
            column.add_widget(row)
        if not column.children:
            column.add_widget(ThemedLabel(text='No folders with music yet', role='muted', size_hint_y=None, height=dp(40)))
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
        scroll.add_widget(column)
        page.add_widget(self.watch_scroll(scroll))

    def start_mix(self, source):
        all_paths = [track.path for track in self.tracks]
        paths = {'favorites': self.library_screen.favorite_tracks, 'recent': self.library_screen.recent_tracks,
                 'discover': make_mix(all_paths)[:20]}.get(source, all_paths)
        mixed = make_mix([path for path in paths if path in self.titles])
        if not mixed:
            self.mix_label.text = 'No songs for this mix yet'
            return
        self.mix_label.text = f'Up next · {songs_label(len(mixed))}'
        self.mix_list.set_tracks(self._tracks_for(mixed))
        self.play_path(mixed[0], mixed)

    # ---------- settings ----------

    def set_setting(self, key, value):
        if key == 'theme':
            self.theme_name = value
            self.palette = THEMES[value]
            for name, swatch in self.swatches.items():
                swatch.selected = name == value
        elif key == 'font':
            self.font = value
            for font, chip in self.font_chips.items():
                chip.selected = font == value
        elif key == 'wallpaper':
            self.wallpaper = value
            self._draw_background()
        elif key == 'motion':
            self.motion = value
            self._sync_motion_btn()
        self._save_settings()

    def _sync_hidden_btn(self):
        count = len(self.hidden)
        self.hidden_btn.text = f'Show {songs_label(count)} again' if count else 'No hidden songs'
        self.hidden_btn.disabled = not count

    def _sync_motion_btn(self):
        self.motion_btn.text = 'Animations: On' if self.motion else 'Animations: Off'
        self.motion_btn.selected = self.motion

    def render_wallpapers(self):
        """Shows the 30 newest device images as wallpaper choices (thumbnails decode in the background)."""
        self.wallpapers_loaded = True
        self.wallpaper_grid.clear_widgets()
        images = find_images(self.picture_roots(), limit=30)
        for image in images:
            thumb = ImageButton(source=image, fit_mode='cover')
            thumb.bind(on_release=lambda _, p=image: self.set_setting('wallpaper', p))
            self.wallpaper_grid.add_widget(thumb)
        self.wallpaper_hint.text = '' if images else 'No pictures found in Pictures, DCIM or Download'

    def _draw_background(self, *_, full=False):
        """Theme gradient, then the wallpaper dimmed so text stays readable."""
        if self.root is None:
            return
        self.background_ready = getattr(self, 'background_ready', False) or full
        self.root.canvas.before.clear()
        with self.root.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(pos=self.root.pos, size=self.root.size,
                      texture=gradient_texture(self.palette['bg2'], self.palette['bg']))
            if self.background_ready and self.wallpaper and os.path.exists(self.wallpaper):
                Rectangle(pos=self.root.pos, size=self.root.size, source=self.wallpaper)
                Color(*self.palette['bg'][:3], 0.55)
                Rectangle(pos=self.root.pos, size=self.root.size)

    def _load_library_data(self):
        """Restores favorites and playlists saved on a previous run."""
        if self.store.exists('library'):
            saved = self.store.get('library')
            self.library_screen.favorite_tracks = list(saved.get('favorites', []))
            for name, paths in saved.get('playlists', {}).items():
                self.library_screen.create_playlist(name)
                for path in paths:
                    self.library_screen.add_track_to_playlist(name, path)
            self.custom_covers = dict(saved.get('song_covers', {}))
            self.playlist_covers = dict(saved.get('playlist_covers', {}))
            self.custom_titles = dict(saved.get('song_titles', {}))
            self.hidden = set(saved.get('hidden', []))
            self.custom_order = list(saved.get('song_order', []))

    def _save_library_data(self):
        # playlists are saved in display order (dicts keep insertion order), so reordering survives restarts
        self.store.put('library', favorites=self.library_screen.favorite_tracks,
                       playlists={n: self.library_screen.playlist_tracks.get(n, []) for n in self.library_screen.playlists},
                       song_covers=self.custom_covers, playlist_covers=self.playlist_covers,
                       song_titles=self.custom_titles, hidden=sorted(self.hidden), song_order=self.custom_order)

    def _save_settings(self):
        self.store.put('settings', theme=self.theme_name, font=self.font, wallpaper=self.wallpaper, motion=self.motion,
                       sort=self.sort_mode)

    # ---------- covers ----------

    def _covers_dir(self):
        return os.path.join(self.user_data_dir, 'custom_covers')

    def _keep_image(self, source, old=None):
        """Copies a chosen picture into app storage so the cover survives the photo being deleted."""
        os.makedirs(self._covers_dir(), exist_ok=True)
        # unique name per pick: Kivy caches images by filename, so reusing a name would show the old picture
        name = hashlib.md5(f'{source}{time.time()}'.encode('utf-8')).hexdigest() + Path(source).suffix.lower()
        target = os.path.join(self._covers_dir(), name)
        shutil.copyfile(source, target)
        self._forget_image(old)
        return target

    def _forget_image(self, path):
        if path and os.path.dirname(path) == self._covers_dir() and os.path.exists(path):
            os.remove(path)

    def playlist_cover(self, name):
        image = self.playlist_covers.get(name, '')
        return image if image and os.path.exists(image) else ''

    def known_cover(self, path):
        """Cover for list rows without reading the file: the user's pick, else embedded art found so far."""
        custom = self.custom_covers.get(path)
        return custom if custom and os.path.exists(custom) else self.covers.get(path, '')

    def pick_song_cover(self, path=None):
        path = path or self.state.current_track()
        if not path:
            return

        def chosen(image):
            self.custom_covers[path] = self._keep_image(image, self.custom_covers.get(path))
            self._covers_changed()

        def cleared():
            self._forget_image(self.custom_covers.pop(path, None))
            self._covers_changed()

        ImagePicker(f'Cover for {self.titles.get(path, "this song")}', find_images(self.picture_roots()), chosen,
                    cleared if path in self.custom_covers else None,
                    lambda: self.browse_system_photos(self._picked_dir(), lambda picked: self._use_pick(picked, chosen))).open()

    def pick_playlist_cover(self, name):
        def chosen(image):
            self.playlist_covers[name] = self._keep_image(image, self.playlist_covers.get(name))
            self._save_library_data()

        def cleared():
            self._forget_image(self.playlist_covers.pop(name, None))
            self._save_library_data()

        ImagePicker(f'Cover for {name}', find_images(self.picture_roots()), chosen,
                    cleared if name in self.playlist_covers else None,
                    lambda: self.browse_system_photos(self._picked_dir(), lambda picked: self._use_pick(picked, chosen))).open()

    def _picked_dir(self):
        return os.path.join(self.user_data_dir, 'picked')

    def _use_pick(self, picked, chosen):
        """A picture from Photos/Drive/Gallery: chosen() copies it into the covers folder, so drop the temp copy."""
        chosen(picked)
        os.remove(picked)

    def _covers_changed(self):
        self._save_library_data()
        self.refresh_player()
        self.refresh_lists()

    # ---------- song options (press and hold a song) ----------

    def song_options(self, path, playlist=None):
        favorite = path in self.library_screen.favorite_tracks
        options = [
            (icon_text('✎', 'Rename'), lambda: self.rename_song(path)),
            (icon_text('▣', 'Change cover'), lambda: self.pick_song_cover(path)),
            (icon_text('♡' if favorite else '♥', 'Remove from favorites' if favorite else 'Add to favorites'),
             lambda: self.toggle_favorite(path)),
            (icon_text('+', 'Add to a playlist'), lambda: self.choose_playlist_for(path)),
            (icon_text('ℹ', 'Info'), lambda: self.song_info(path)),
        ]
        if playlist == 'Favorites':
            options.pop(2)  # already covered by "Remove from this playlist"
        if playlist:
            options.append((icon_text('−', f'Remove from “{playlist}”'), lambda: self.remove_from_playlist(path, playlist)))
        options += [
            (icon_text('⊘', 'Remove from BeatSphere'), lambda: self.hide_song(path)),
            (icon_text('✖', 'Delete from phone…'), lambda: self.delete_song(path)),
        ]
        OptionsSheet(self.titles.get(path, Path(path).stem), options).open()

    def song_info(self, path):
        meta = self.meta.get(path) or read_metadata(path)
        try:
            stat = os.stat(path)
            size, added = f'{stat.st_size / 1048576:.1f} MB', datetime.fromtimestamp(stat.st_mtime).strftime('%b %d, %Y')
        except OSError:
            size = added = '—'
        file = Path(path)
        InfoDialog(self.titles.get(path, file.stem), [
            ('Artist', meta.get('artist') or 'Unknown'), ('Album', meta.get('album') or 'Unknown'),
            ('Length', fmt_time(meta.get('duration', 0))), ('Format', file.suffix.lstrip('.').upper()),
            ('Size', size), ('Added', added), ('File', file.name), ('Folder', str(file.parent)),
        ]).open()

    def rename_song(self, path):
        def save(new_title):
            original = self.file_titles.get(path, Path(path).stem)
            if not new_title or new_title == original:
                self.custom_titles.pop(path, None)
                new_title = original
            else:
                self.custom_titles[path] = new_title
            for track in self.tracks:
                if track.path == path:
                    track.title = new_title
            self.tracks = sort_tracks(self.tracks)
            self.titles[path] = new_title
            self._save_library_data()
            self.render_songs()
            self.refresh_lists()
            self.refresh_player()

        TextPrompt('Rename song', self.titles.get(path, ''), save).open()

    def toggle_favorite(self, path):
        self.library_screen.toggle_favorite(path)
        self._save_library_data()
        self.refresh_player()

    def choose_playlist_for(self, path):
        def add(name):
            self.library_screen.add_track_to_playlist(name, path)
            self._save_library_data()
            self.toast(f'Added to “{name}”')

        def new_playlist():
            def created(name):
                if name and self.library_screen.create_playlist(name):
                    add(name)
            TextPrompt('New playlist', '', created).open()

        options = [(icon_text('♫', name), lambda n=name: add(n)) for name in self.library_screen.playlists]
        options.append((icon_text('+', 'New playlist…'), new_playlist))
        OptionsSheet('Add to a playlist', options).open()

    def remove_from_playlist(self, path, playlist):
        if playlist == 'Favorites':
            if path in self.library_screen.favorite_tracks:
                self.library_screen.toggle_favorite(path)
            self._save_library_data()
            self.open_favorites()
            return
        paths = self.library_screen.playlist_tracks.get(playlist, [])
        if path in paths:
            paths.remove(path)
        self.library_screen.set_playlist_order(list(self.library_screen.playlists))  # refresh card counts
        self._save_library_data()
        self.open_playlist(playlist)

    def hide_song(self, path):
        """Removes a song from BeatSphere only; the file stays on the phone (Settings can bring it back)."""
        self.hidden.add(path)
        self._drop_song(path)
        self._sync_hidden_btn()
        self.toast('Removed from BeatSphere · the file is still on your phone')

    def delete_song(self, path):
        title = self.titles.get(path, Path(path).stem)

        def deleted(ok):
            if ok:
                self._drop_song(path)
                self.toast(f'Deleted “{title}”')
            else:
                self.toast('The file could not be deleted')

        def confirm():
            if self.loaded_path == path:  # release the file before deleting it
                self.player.unload()
                self.loaded_path = None
                self.state.playing = False
            delete_audio_file(path, lambda ok: Clock.schedule_once(lambda dt: deleted(ok)))

        ConfirmDialog(f'Delete “{title}”?', 'This permanently deletes the file from your phone. '
                      'It can\'t be undone.', 'Delete', confirm).open()

    def _drop_song(self, path):
        """Forgets a song everywhere in the app (lists, favorites, playlists, queue, custom name/cover)."""
        self.tracks = [track for track in self.tracks if track.path != path]
        self.titles.pop(path, None)
        screen = self.library_screen
        if path in screen.favorite_tracks:
            screen.favorite_tracks.remove(path)
        for paths in screen.playlist_tracks.values():
            if path in paths:
                paths.remove(path)
        screen.set_playlist_order(list(screen.playlists))
        self.custom_order = [p for p in self.custom_order if p != path]
        self.custom_titles.pop(path, None)
        self._forget_image(self.custom_covers.pop(path, None))
        if path in self.state.track_paths:
            current = self.state.current_track()
            self.state.track_paths.remove(path)
            if current == path:
                if self.loaded_path == path:
                    self.player.unload()
                    self.loaded_path = None
                self.state.playing = False
                self.state.current_index = min(self.state.current_index, len(self.state.track_paths) - 1)
            elif current in self.state.track_paths:
                self.state.current_index = self.state.track_paths.index(current)
        self._save_library_data()
        self.render_songs()
        self.refresh_lists()
        self.refresh_player()

    def restore_hidden(self):
        count = len(self.hidden)
        self.hidden.clear()
        self._save_library_data()
        self.load_tracks()
        self._sync_hidden_btn()
        self.toast(f'{songs_label(count)} back in BeatSphere' if count else 'No hidden songs')

    def toast(self, text):
        """Short message that fades in above the tab bar and fades out by itself."""
        card = Card(size_hint=(None, None), padding=[dp(16), dp(10)], radius=dp(18), bg_role='surface_alt')
        label = ThemedLabel(text=text, font_size='14sp', halign='center')
        card.add_widget(label)
        card.width = min(self.root.width - dp(40), dp(340))
        card.height = dp(48)
        card.pos = ((self.root.width - card.width) / 2, dp(150))
        card.opacity = 0
        self.root.add_widget(card)
        animate(card, 0.2, opacity=1)
        Clock.schedule_once(lambda dt: animate(card, 0.4, opacity=0), 2.2)
        Clock.schedule_once(lambda dt: self.root.remove_widget(card), 2.8)

    # ---------- playback ----------

    def play_collection(self, paths, shuffled=False):
        if paths:
            self.play_path(make_mix(paths)[0] if shuffled else paths[0], paths, force_shuffle=shuffled)

    def play_path(self, path, queue, force_shuffle=None):
        """Plays a song and makes the list it was picked from the play queue."""
        shuffle = self.state.shuffle if force_shuffle is None else force_shuffle
        self.state.set_tracks(queue)
        self.state.select_track(path)
        self.state.shuffle = False
        if shuffle:
            self.state.toggle_shuffle()
        self.library_screen.add_recent_track(path)
        self.play_current()

    def play_current(self):
        if self._load_and_play():
            self._show_changes(True)

    def _load_and_play(self):
        """Starts the current song without touching the screen (safe from Android's thread)."""
        path = self.state.current_track()
        if not path:
            return False
        self.loaded_path = path if self.player.load(path) else None
        if path not in self.meta:
            self.meta[path] = read_metadata(path)
        self.state.playing = self.loaded_path is not None
        if self.state.playing:
            self.player.play()
        return True

    def _show_changes(self, on_screen):
        """Refreshes the screen, or (in the background) just the notification and remembers to redraw later."""
        if on_screen:
            self.mini.show()
            self.refresh_player()
            self.refresh_lists()
        else:
            self._publish_media()
            self.ui_stale = True

    def _publish_media(self):
        path = self.state.current_track()
        if not path:
            return
        if self.media is None:
            if not self.state.playing:
                return
            self.media = create_media_controls(self.on_media_command, 'assets/icon.png')
        try:
            artist = self.meta.get(path, {}).get('artist') or self.folder_name(path)
            self.media.update(self.titles.get(path, Path(path).stem), artist, self.cover_for(path), self.state.playing,
                              self.player.position(), self.length())
        except Exception:
            import traceback
            traceback.print_exc()  # the notification must never break playback

    def on_media_command(self, command, value=0):
        """Buttons in the notification panel, lock screen or headphones (arrive on Android's thread)."""
        if self.in_background:
            self._media_command(command, value, on_screen=False)
        else:
            Clock.schedule_once(lambda dt: self._media_command(command, value, on_screen=True))

    def _media_command(self, command, value, on_screen):
        playing = self.state.playing
        if command == 'seek':
            self.player.seek(value / 1000)
        elif command in ('pause', 'toggle') and playing:
            self.state.playing = False
            self.player.pause()
        elif command in ('play', 'toggle') and not playing:
            if self.loaded_path is not None and self.loaded_path == self.state.current_track():
                self.player.play()
                self.state.playing = True
            else:
                self._load_and_play()
        elif command == 'next' and self.state.next_track():
            self._load_and_play()
        elif command == 'previous':
            if playing and self.player.position() > 3:
                self.player.seek(0)
            elif self.state.previous_track():
                self._load_and_play()
        self._show_changes(on_screen)

    def _song_finished_in_background(self):
        """Android's end-of-song event; in the foreground the clock tick handles it instead."""
        if not self.in_background:
            return
        if self.state.advance():
            self._load_and_play()
        else:
            self.state.playing = False
        self._show_changes(False)

    def cover_for(self, path):
        custom = self.custom_covers.get(path)
        if custom and os.path.exists(custom):
            return custom
        if path not in self.covers:
            self.covers[path] = (extract_cover(path, os.path.join(self.user_data_dir, 'covers'))
                                 or FavoritePlaylistScreen.resolve_album_art(path) or '')
        return self.covers[path]

    def length(self):
        return self.player.length() or self.meta.get(self.loaded_path, {}).get('duration', 0)

    def refresh_player(self):
        """Pushes the current song into the mini player and the Now Playing view."""
        path = self.state.current_track()
        if not path:
            return
        title = self.titles.get(path, self.state.current_track_title())
        artist = self.meta.get(path, {}).get('artist') or self.folder_name(path)
        if self.loaded_path is None:
            artist = 'Cannot play this file'
        cover = self.cover_for(path)
        playing = self.state.playing
        self.mini.title.text, self.mini.subtitle.text, self.mini.art.source = title, artist, cover
        self.mini.play_btn.text = '❚❚' if playing else '▶'
        self.mini.eq.active = playing
        self.now_playing.update(title, artist, cover, playing, self.player.position(), self.length(),
                                path in self.library_screen.favorite_tracks, self.state.shuffle, self.state.repeat_mode)
        self._publish_media()

    def toggle_play(self):
        self._media_command('toggle', 0, on_screen=True)

    def pause_current(self):
        self.state.playing = False  # set first so the tick doesn't treat the pause as "song ended"
        self.player.pause()
        self.refresh_player()
        self.refresh_lists()

    def next_track(self):
        self._media_command('next', 0, on_screen=True)

    def previous_track(self):
        """Restarts the song if it's past 3 seconds, otherwise goes to the previous one."""
        self._media_command('previous', 0, on_screen=True)

    def toggle_shuffle(self):
        self.state.toggle_shuffle()
        self.refresh_player()

    def cycle_repeat(self):
        self.state.cycle_repeat()
        self.refresh_player()

    def seek_fraction(self, fraction):
        if self.length():
            self.player.seek(fraction * self.length())
            self._publish_media()  # keep the notification's progress bar in step with the jump

    def toggle_current_favorite(self):
        path = self.state.current_track()
        if not path:
            return
        self.library_screen.toggle_favorite(path)
        self._save_library_data()
        self.refresh_player()

    def open_now_playing(self):
        self.refresh_player()
        self.now_playing.open()

    def _tick(self, dt):
        """Moves progress bars and continues to the next song when one ends."""
        if not self.state.playing:
            return
        if self.player.finished():
            if self.state.advance():
                self.play_current()
            else:
                self.state.playing = False
                self.refresh_player()
                self.refresh_lists()
            return
        position, length = self.player.position(), self.length()
        self.mini.set_progress(position / length if length else 0)
        if self.now_playing.is_open:
            self.now_playing.set_position(position, length)

    def _on_keyboard(self, window, key, *args):
        """Android back: close Now Playing, then leave a detail page, then return to Songs."""
        if key != 27:
            return False
        if self.now_playing.is_open:
            self.now_playing.close()
        elif self.back_action is not None:
            self.back_action()
        elif self.nav.current != 'Songs':
            self.show_tab('Songs')
        else:
            return False
        return True

    def on_pause(self):
        """Keeps the app alive when Android pauses it (permission dialogs, switching apps)."""
        if self.state.playing:
            prepared = self.background_playback.prepare_for_background_play(
                self.state.current_track(), {'state': 'playing'}
            )
            if prepared['background_mode'] != 'enabled':
                self.pause_current()
        self.in_background = True
        # Returning False tells Kivy to stop the app, which kills it on every pause (e.g. a permission dialog).
        return True

    def on_resume(self):
        self.in_background = False
        if self.ui_stale:  # songs changed from the notification or by themselves while we were away
            self.ui_stale = False
            self.refresh_player()
            self.refresh_lists()
        return True

    def on_start(self):
        if self.intro:
            Clock.schedule_once(lambda dt: self.intro.begin(), 0.15)
        Clock.schedule_once(lambda dt: self.load_tracks(), 0.1)  # after the first frame, so the screen shows at once
        Clock.schedule_once(lambda dt: self._draw_background(full=True), 0.5)  # big wallpaper decode after that

    def on_stop(self):
        if self.media is not None:
            self.media.release()


if __name__ == '__main__':
    BeatSphereApp().run()
