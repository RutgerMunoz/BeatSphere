"""Reusable themed widgets with motion.

Every widget reads its colors and font from the running app (`app.palette`,
`app.font`) and redraws itself when the user changes the style in Settings.
Animations go through `animate()`, which respects the "Animations" setting.
"""

import colorsys
import random
import zlib
from collections import OrderedDict

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import (ClearBuffers, ClearColor, Color, Ellipse, Fbo, Line, PopMatrix, PushMatrix, Rectangle,
                           RoundedRectangle, Scale, SmoothLine)
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from app.library_views import letter_of, move_item
from app.ui.theme import ICON_FONT


def app():
    return App.get_running_app()


def animate(widget, duration=0.25, transition='out_quad', **props):
    """Animates widget properties, or sets them instantly when animations are off."""
    Animation.cancel_all(widget, *props)
    if app().motion and duration:
        Animation(d=duration, t=transition, **props).start(widget)
    else:
        for name, value in props.items():
            setattr(widget, name, value)


def gradient_texture(start, end, horizontal=False):
    """Builds a small two-color gradient texture that GPU-stretches over any rectangle."""
    steps = 64
    texture = Texture.create(size=(steps, 1) if horizontal else (1, steps), colorfmt='rgba')
    buf = bytearray()
    for i in range(steps):
        t = i / (steps - 1)
        buf += bytes(int(255 * (start[c] + (end[c] - start[c]) * t)) for c in range(4))
    texture.blit_buffer(bytes(buf), colorfmt='rgba', bufferfmt='ubyte')
    texture.mag_filter = 'linear'
    return texture


def edge(line, x, y, w, h, r):
    """Anti-aliased outline for a filled rounded shape; Kivy's fills alone have stair-stepped edges."""
    if w > 2 and h > 2:
        line.rounded_rectangle = (x, y, w, h, max(min(r, w / 2, h / 2), 1))
    else:
        line.points = []


# Bounded caches: small thumbnails for list rows, a few big ones for the player and playlist tiles.
_caches = {128: (OrderedDict(), 300), 512: (OrderedDict(), 8)}


def _square_thumbnail(path, size):
    """Center-crops an image to a square and renders it into a size x size mipmapped texture.

    Covers are drawn far smaller than their pixels, so they need mipmaps to look smooth; but Kivy pads
    non-power-of-two images when mipmapping and rounded shapes then show the padding as black.
    Rendering into a power-of-two square first avoids both problems (and tall photos aren't squashed).
    """
    try:
        source = CoreImage(path).texture
    except Exception:
        return None
    side = min(source.size)
    region = source.get_region((source.width - side) / 2, (source.height - side) / 2, side, side)
    fbo = Fbo(size=(size, size))
    with fbo:
        ClearColor(0, 0, 0, 0)
        ClearBuffers()
        Color(1, 1, 1, 1)
        # negative height draws it upside down, which cancels the flip of reading fbo.pixels back
        # (rounded shapes ignore a texture's flip flag, so the pixels themselves must be the right way up)
        Rectangle(pos=(0, size), size=(size, -size), texture=region)
    fbo.draw()
    texture = Texture.create(size=(size, size), colorfmt='rgba', mipmap=True)
    texture.blit_buffer(fbo.pixels, colorfmt='rgba', bufferfmt='ubyte')
    texture.min_filter = 'linear_mipmap_linear'
    texture.mag_filter = 'linear'
    return texture


def cover_texture(path, size=128):
    """Smooth square texture for a cover image (cached); None if it can't be read."""
    cache, capacity = _caches[size]
    if path in cache:
        cache.move_to_end(path)
        return cache[path]
    texture = _square_thumbnail(path, size)
    if texture is None:
        return None  # not cached: the picture may still be on its way, try again next time
    cache[path] = texture
    if len(cache) > capacity:
        cache.popitem(last=False)
    return texture


def avatar_color(text):
    """Stable pastel color per title, so each song keeps its avatar color."""
    hue = (zlib.crc32(text.encode('utf-8')) % 360) / 360
    return list(colorsys.hsv_to_rgb(hue, 0.55, 0.9)) + [1]


class ThemedLabel(Label):
    """Label that follows the app's text color (or another palette role) and font."""

    role = StringProperty('text')
    keep_font = BooleanProperty(False)
    wrap = BooleanProperty(False)

    def __init__(self, **kwargs):
        kwargs.setdefault('halign', 'left')
        kwargs.setdefault('valign', 'middle')
        super().__init__(**kwargs)
        app().bind(palette=self._sync, font=self._sync)
        self.bind(role=self._sync, size=self._fit)
        self._sync()

    def _fit(self, *_):
        self.text_size = (self.width, None if self.wrap else self.height)

    def _sync(self, *_):
        self.color = app().palette[self.role]
        if not self.keep_font:
            self.font_name = app().font


class ThemedInput(TextInput):
    """Rounded search/name field in the current style."""

    def __init__(self, **kwargs):
        kwargs.setdefault('multiline', False)
        super().__init__(**kwargs)
        self.background_normal = self.background_active = ''
        self.padding = [dp(16), dp(12)]
        with self.canvas.before:
            self._bg_color = Color()
            self._bg = RoundedRectangle(radius=[dp(16)])
            self._edge = SmoothLine(width=1)
            # TextInput draws its text with the last color set in canvas.before, so restore it after our background.
            self._text_color = Color()
        self.background_color = (0, 0, 0, 0)
        self.bind(pos=self._redraw, size=self._redraw, text=self._sync)
        app().bind(palette=self._sync, font=self._sync)
        self._sync()

    def _redraw(self, *_):
        self._bg.pos, self._bg.size = self.pos, self.size
        edge(self._edge, *self.pos, *self.size, dp(16))

    def _sync(self, *_):
        palette = app().palette
        self._bg_color.rgba = palette['surface_alt']
        self._text_color.rgba = palette['text'] if self.text else palette['muted']
        self.foreground_color = palette['text']
        self.hint_text_color = palette['muted']
        self.cursor_color = palette['primary']
        self.font_name = app().font


class Pressable(ButtonBehavior, Label):
    """Rounded button that squishes when pressed and springs back on release."""

    bg_role = StringProperty('surface_alt')
    fg_role = StringProperty('text')
    radius = NumericProperty(dp(16))
    selected = BooleanProperty(False)
    icon = BooleanProperty(False)
    gradient = BooleanProperty(False)
    font_file = StringProperty('')  # fixed font (font previews in Settings) instead of the app font
    scale = NumericProperty(1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            PushMatrix()
            self._scale = Scale()
            self._bg_color = Color()
            self._bg = RoundedRectangle()
            self._edge_color = Color()
            self._edge = SmoothLine(width=1)
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=self._redraw, size=self._redraw, scale=self._redraw, radius=self._redraw,
                  selected=self._sync, bg_role=self._sync, fg_role=self._sync, gradient=self._sync)
        app().bind(palette=self._sync, font=self._sync)
        self._sync()

    def _redraw(self, *_):
        self._bg.pos, self._bg.size, self._bg.radius = self.pos, self.size, [self.radius]
        edge(self._edge, *self.pos, *self.size, self.radius)
        self._scale.origin = self.center
        self._scale.x = self._scale.y = self.scale

    def _sync(self, *_):
        palette = app().palette
        if self.gradient:
            self._bg.texture = gradient_texture(palette['primary'], palette['accent'], horizontal=True)
            self._bg_color.rgba = (1, 1, 1, 1)
            self._edge_color.rgba = [(p + a) / 2 for p, a in zip(palette['primary'], palette['accent'])]
            self.color = palette['on_primary']
        else:
            self._bg.texture = None
            self._bg_color.rgba = palette['primary'] if self.selected else palette[self.bg_role]
            self._edge_color.rgba = self._bg_color.rgba
            self.color = palette['on_primary'] if self.selected else palette[self.fg_role]
        self.font_name = ICON_FONT if self.icon else (self.font_file or app().font)

    def on_press(self):
        animate(self, 0.08, 'out_quad', scale=0.9)

    def on_release(self):
        animate(self, 0.35, 'out_back', scale=1)


class Card(BoxLayout):
    """Rounded surface panel."""

    bg_role = StringProperty('surface')
    radius = NumericProperty(dp(22))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg_color = Color()
            self._bg = RoundedRectangle()
            self._edge = SmoothLine(width=1)
        self.bind(pos=self._redraw, size=self._redraw, bg_role=self._sync)
        app().bind(palette=self._sync)
        self._sync()

    def _redraw(self, *_):
        self._bg.pos, self._bg.size, self._bg.radius = self.pos, self.size, [self.radius]
        edge(self._edge, *self.pos, *self.size, self.radius)

    def _sync(self, *_):
        self._bg_color.rgba = app().palette[self.bg_role]


class EqualizerBars(Widget):
    """Little bouncing bars shown while music plays."""

    active = BooleanProperty(False)
    bars = NumericProperty(4)
    role = StringProperty('primary')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.levels = [0.25] * self.bars
        self.targets = list(self.levels)
        self._event = None
        with self.canvas:
            self._color = Color()
            self._rects = [RoundedRectangle(radius=[dp(1.5)]) for _ in range(self.bars)]
            self._edges = [SmoothLine(width=1) for _ in range(self.bars)]
        self.bind(pos=self._redraw, size=self._redraw, active=self._on_active, role=self._sync)
        app().bind(palette=self._sync)
        self._sync()

    def _sync(self, *_):
        self._color.rgba = app().palette[self.role]

    def _on_active(self, *_):
        if self.active and self._event is None:
            self._event = Clock.schedule_interval(self._tick, 1 / 30)
        elif not self.active and self._event is not None:
            self._event.cancel()
            self._event = None
            self.levels = [0.25] * self.bars
            self._redraw()

    def _tick(self, dt):
        if not app().motion:
            return
        for i in range(self.bars):
            if abs(self.levels[i] - self.targets[i]) < 0.05:
                self.targets[i] = random.uniform(0.2, 1)
            self.levels[i] += (self.targets[i] - self.levels[i]) * 0.3
        self._redraw()

    def _redraw(self, *_):
        gap = self.width / (self.bars * 3 - 1)
        for i, rect in enumerate(self._rects):
            rect.pos = (self.x + i * gap * 3, self.y)
            rect.size = (gap * 2, max(self.height * self.levels[i], dp(2)))
            edge(self._edges[i], *rect.pos, *rect.size, gap)


class Avatar(RelativeLayout):
    """Round letter badge for a song; turns into equalizer bars when it is the song playing."""

    text = StringProperty('')
    cover = StringProperty('')
    playing = BooleanProperty(False)
    active = BooleanProperty(False)  # playing and not paused: bars bounce

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._color = Color()
            self._circle = Ellipse()
            self._ring = SmoothLine(width=1)
        self.letter = Label(bold=True, font_size='17sp', color=(1, 1, 1, 1))
        self.eq = EqualizerBars(role='on_primary', size_hint=(0.5, 0.45), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.add_widget(self.letter)
        self.add_widget(self.eq)
        self.bind(size=self._redraw, text=self._sync, cover=self._sync, playing=self._sync, active=self._sync)
        app().bind(palette=self._sync)
        self._redraw()
        self._sync()

    def _redraw(self, *_):
        self._circle.size = self.size
        self._ring.ellipse = (0, 0, *self.size)

    def _sync(self, *_):
        texture = cover_texture(self.cover) if self.cover else None
        self._circle.texture = texture
        if self.playing or texture is not None:
            self.letter.text = ''
        elif letter_of(self.text) == '#':
            self.letter.text = '#'
        else:
            self.letter.text = self.text.strip()[:1].upper()
        if texture is not None:
            self._color.rgba = (0.45, 0.45, 0.45, 1) if self.playing else (1, 1, 1, 1)  # dim the cover under the bars
        else:
            self._color.rgba = app().palette['primary'] if self.playing else avatar_color(self.text)
        self.eq.opacity = 1 if self.playing else 0
        self.eq.active = self.active


class SongRow(RecycleDataViewBehavior, ButtonBehavior, BoxLayout):
    """One song in a list: avatar, title, artist; highlighted while it plays."""

    title = StringProperty('')
    subtitle = StringProperty('')
    path = StringProperty('')
    cover = StringProperty('')
    playing = BooleanProperty(False)
    active = BooleanProperty(False)
    editing = BooleanProperty(False)  # reorder mode: shows the ≡ drag handle
    dragging = BooleanProperty(False)  # this row is being dragged
    owner = ObjectProperty(None, allownone=True)
    flash = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(orientation='horizontal', padding=[dp(10), dp(6), dp(8), dp(6)], spacing=dp(12), **kwargs)
        with self.canvas.before:
            self._bg_color = Color()
            self._bg = RoundedRectangle(radius=[dp(16)])
            self._edge = SmoothLine(width=1)
        self.avatar = Avatar(size_hint=(None, None), size=(dp(44), dp(44)), pos_hint={'center_y': 0.5})
        texts = BoxLayout(orientation='vertical', padding=[0, dp(4)])
        self.title_label = ThemedLabel(font_size='15sp', bold=True, shorten=True, shorten_from='right')
        self.subtitle_label = ThemedLabel(role='muted', font_size='12sp', shorten=True, shorten_from='right')
        texts.add_widget(self.title_label)
        texts.add_widget(self.subtitle_label)
        self.handle = ThemedLabel(text='≡', font_name=ICON_FONT, keep_font=True, font_size='22sp', role='muted',
                                  halign='center', size_hint_x=None, width=0, opacity=0)
        self.dots = Pressable(text='⋮', icon=True, font_size='22sp', size_hint=(None, None), size=(dp(38), dp(42)),
                              radius=dp(19), bg_role='surface', fg_role='muted', pos_hint={'center_y': 0.5})
        self.dots.bind(on_release=lambda *_: self.owner.hold(self.path) if self.owner is not None else None)
        self.add_widget(self.avatar)
        self.add_widget(texts)
        self.add_widget(self.dots)
        self.add_widget(self.handle)
        self.bind(pos=self._redraw, size=self._redraw, flash=self._sync, playing=self._sync, active=self._sync,
                  title=self._sync, subtitle=self._sync, cover=self._sync, editing=self._sync, dragging=self._sync)
        app().bind(palette=self._sync)

    def _redraw(self, *_):
        self._bg.pos, self._bg.size = self.pos, self.size
        edge(self._edge, *self.pos, *self.size, dp(16))

    def _sync(self, *_):
        palette = app().palette
        self.title_label.text = self.title
        self.subtitle_label.text = self.subtitle
        self.avatar.text = self.title
        self.avatar.cover = self.cover
        self.avatar.playing = self.playing
        self.avatar.active = self.active
        self.title_label.role = 'primary' if self.playing else 'text'
        self.handle.width, self.handle.opacity = (dp(40), 1) if self.editing else (0, 0)
        self.dots.width, self.dots.opacity, self.dots.disabled = (0, 0, True) if self.editing else (dp(38), 1, False)
        self.handle.role = 'primary' if self.dragging else 'muted'
        if self.dragging:
            base = list(palette['primary'][:3]) + [0.38]
        elif self.playing:
            base = list(palette['primary'][:3]) + [0.16]
        else:
            base = palette['surface']
        mix = min(self.flash, 1)
        self._bg_color.rgba = [base[i] + (palette['primary'][i] - base[i]) * mix * 0.35 for i in range(3)] + [base[3]]

    def refresh_view_attrs(self, rv, index, data):
        # Rows are recycled for other songs: drop any tap flash still running from the previous song.
        Animation.cancel_all(self, 'flash')
        self.flash = 0
        return super().refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and not self.dots.collide_point(*touch.pos):
            # Remember which song was pressed: the list can redraw (and reuse this row for another song)
            # while the finger is still down.
            self._pressed_path = self.path
            touch.ud['row_hold'] = Clock.schedule_once(lambda dt: self._held(touch), 0.5)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        hold = touch.ud.get('row_hold')
        if hold is not None and (abs(touch.x - touch.ox) > dp(10) or abs(touch.y - touch.oy) > dp(10)):
            hold.cancel()  # the finger is scrolling, not holding
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        hold = touch.ud.pop('row_hold', None)
        if hold is not None:
            hold.cancel()
        return super().on_touch_up(touch)

    def _held(self, touch):
        touch.ud.pop('row_hold', None)
        self._suppress_release = True
        if self.owner is not None:
            self.owner.hold(getattr(self, '_pressed_path', None) or self.path)

    def on_press(self):
        self._suppress_release = False
        self.flash = 1
        animate(self, 0.45, 'out_quad', flash=0)

    def on_release(self):
        if getattr(self, '_suppress_release', False):  # a press-and-hold opened the menu; don't also play
            self._suppress_release = False
            return
        if self.owner is not None:
            self.owner.pick(getattr(self, '_pressed_path', None) or self.path)


ROW_HEIGHT = dp(62)
ROW_SPACING = dp(6)


class SongList(RecycleView):
    """Fast scrolling song list; fades in whenever its contents change.

    In reorder mode (`set_editing(True)`) each row shows a ≡ handle: drag it to move the song; the list
    calls on_reorder(paths) when the finger lifts.
    """

    def __init__(self, on_pick, on_hold=None, on_reorder=None, songs_only=True, **kwargs):
        super().__init__(bar_width=dp(3), **kwargs)
        self.songs_only = songs_only  # rows are library songs: drop any the user removed or deleted
        self.on_pick = on_pick
        self.on_hold = on_hold
        self.on_reorder = on_reorder
        self.editing = False
        self._drag_index = None
        self.paths = []
        self.tracks = []
        layout = RecycleBoxLayout(orientation='vertical', default_size=(None, ROW_HEIGHT), default_size_hint=(1, None),
                                  size_hint_y=None, spacing=ROW_SPACING, padding=[0, 0, 0, dp(8)])
        layout.bind(minimum_height=layout.setter('height'))
        self.add_widget(layout)
        self.viewclass = SongRow  # must come after add_widget: viewclass is forwarded to the layout manager

    def set_tracks(self, tracks, animated=True):
        self.tracks = tracks
        self.paths = [track.path for track in tracks]
        self.refresh_rows()
        self.scroll_y = 1
        if animated:
            self.opacity = 0
            animate(self, 0.3, 'out_quad', opacity=1)

    def refresh_rows(self):
        """Rebuilds row data, e.g. after the playing song or artist names change."""
        if self.songs_only:
            self.tracks = [track for track in self.tracks if track.path in app().titles]
            self.paths = [track.path for track in self.tracks]
        current, meta, active = app().loaded_path, app().meta, app().state.playing  # loaded song, not just selected
        dragged = self.paths[self._drag_index] if self._drag_index is not None else None
        self.data = [{'title': track.title, 'path': track.path, 'owner': self, 'playing': track.path == current,
                      'active': track.path == current and active, 'editing': self.editing,
                      'dragging': track.path == dragged,
                      # rows that aren't songs (the playlist list) bring their own cover and subtitle
                      'cover': getattr(track, 'cover', None) or app().known_cover(track.path),
                      'subtitle': getattr(track, 'subtitle', None) or meta.get(track.path, {}).get('artist')
                      or app().folder_name(track.path)}
                     for track in self.tracks]

    def set_editing(self, editing):
        self.editing = editing
        self.refresh_rows()

    def pick(self, path):
        if not self.editing:
            self.on_pick(path, self.paths)

    def hold(self, path):
        if self.on_hold is not None and not self.editing:
            self.on_hold(path)

    # ----- drag to reorder -----

    def _index_at(self, touch):
        layout = self.layout_manager
        _, y = layout.to_widget(*touch.pos)
        index = int((layout.top - y) // (ROW_HEIGHT + ROW_SPACING))
        return max(0, min(index, len(self.tracks) - 1))

    def on_touch_down(self, touch):
        # Only the ≡ handle (right edge) starts a drag; anywhere else scrolls as usual.
        if self.editing and self.tracks and self.collide_point(*touch.pos) and touch.x > self.right - dp(56):
            self._drag_index = self._index_at(touch)
            touch.grab(self)
            self.refresh_rows()
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self and self._drag_index is not None:
            target = self._index_at(touch)
            if target != self._drag_index:
                self.tracks = move_item(self.tracks, self._drag_index, target)
                self.paths = [track.path for track in self.tracks]
                self._drag_index = target
                self.refresh_rows()
            self._autoscroll(touch)
            return True
        return super().on_touch_move(touch)

    def _autoscroll(self, touch):
        """Dragging near the top or bottom edge scrolls the list so songs can travel far."""
        span = self.layout_manager.height - self.height
        if span <= 0:
            return
        step = dp(14) / span
        if touch.y > self.top - dp(48):
            self.scroll_y = min(1, self.scroll_y + step)
        elif touch.y < self.y + dp(48):
            self.scroll_y = max(0, self.scroll_y - step)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._drag_index = None
            self.refresh_rows()
            if self.on_reorder is not None:
                self.on_reorder(list(self.paths))
            return True
        return super().on_touch_up(touch)


class AlbumArt(Widget):
    """Cover art with a soft glow and spinning light rings while the song plays."""

    source = StringProperty('')
    spinning = BooleanProperty(False)
    angle = NumericProperty(0)
    glow = NumericProperty(0.25)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            self._glow_color = Color()
            self._glow = Ellipse()
            self._ring_color = Color()
            self._ring1 = SmoothLine(width=dp(2.5))
            self._ring2_color = Color()
            self._ring2 = SmoothLine(width=dp(1.5))
            Color(1, 1, 1, 1)
            self._art = RoundedRectangle()
        self._event = None
        self.bind(pos=self._redraw, size=self._redraw, angle=self._redraw, glow=self._sync,
                  source=self._load, spinning=self._on_spinning)
        self.bind(width=lambda *_: self._load())  # pick the small or big texture once the real size is known
        app().bind(palette=self._sync)
        self._load()
        self._sync()

    def _load(self, *_):
        try:
            size = 512 if self.width > 120 else 128
            self._art.texture = cover_texture(self.source, size) or cover_texture('assets/icon.png', size)
        except Exception:
            self._art.texture = cover_texture('assets/icon.png')

    def _sync(self, *_):
        palette = app().palette
        self._glow_color.rgba = list(palette['primary'][:3]) + [self.glow]
        self._ring_color.rgba = palette['primary']
        self._ring2_color.rgba = list(palette['accent'][:3]) + [0.8]

    def _on_spinning(self, *_):
        if self.spinning and self._event is None:
            self._event = Clock.schedule_interval(self._spin, 1 / 30)
            if app().motion:
                pulse = Animation(glow=0.45, d=1.2, t='in_out_sine') + Animation(glow=0.2, d=1.2, t='in_out_sine')
                pulse.repeat = True
                pulse.start(self)
        elif not self.spinning and self._event is not None:
            self._event.cancel()
            self._event = None
            Animation.cancel_all(self, 'glow')
            animate(self, 0.4, glow=0.25)

    def _spin(self, dt):
        if app().motion:
            self.angle = (self.angle + dt * 60) % 360

    def _redraw(self, *_):
        side = min(self.width, self.height)
        cx, cy = self.center
        ring = side * 0.94
        art = side * 0.74
        glow = side * 1.0
        self._glow.pos, self._glow.size = (cx - glow / 2, cy - glow / 2), (glow, glow)
        rx, ry = cx - ring / 2, cy - ring / 2
        self._ring1.ellipse = (rx, ry, ring, ring, self.angle, self.angle + 110)
        inner = ring * 0.9
        self._ring2.ellipse = (cx - inner / 2, cy - inner / 2, inner, inner, -self.angle * 1.4 + 180, -self.angle * 1.4 + 250)
        self._art.pos, self._art.size, self._art.radius = (cx - art / 2, cy - art / 2), (art, art), [art * 0.18]


class ImageButton(ButtonBehavior, AsyncImage):
    """Tappable thumbnail (wallpaper/cover picker); photos decode on a background thread, not the UI's."""

    def on_press(self):
        animate(self, 0.08, opacity=0.6)

    def on_release(self):
        animate(self, 0.3, opacity=1)


class ThemeSwatch(ButtonBehavior, BoxLayout):
    """Preview tile of a color style: its gradient, name and a ring when selected."""

    selected = BooleanProperty(False)
    colors = ListProperty([])

    def __init__(self, name, palette, **kwargs):
        super().__init__(orientation='vertical', padding=dp(10), **kwargs)
        self.name = name
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(radius=[dp(18)], texture=gradient_texture(palette['bg2'], palette['bg']))
            self._dot_color = Color(*palette['primary'])
            self._dot = Ellipse()
            self._dot2_color = Color(*palette['accent'])
            self._dot2 = Ellipse()
            self._ring_color = Color(0, 0, 0, 0)
            self._ring = Line(width=dp(2))
        self.add_widget(Label(text=name, bold=True, color=palette['text'], halign='left', valign='bottom',
                              text_size=(None, None)))
        self.bind(pos=self._redraw, size=self._redraw, selected=self._redraw)

    def _redraw(self, *_):
        self._bg.pos, self._bg.size = self.pos, self.size
        d = dp(18)
        self._dot.pos, self._dot.size = (self.right - d * 2.2, self.top - d * 1.5), (d, d)
        self._dot2.pos, self._dot2.size = (self.right - d * 1.4, self.top - d * 1.5), (d, d)
        self._ring_color.rgba = app().palette['primary'] if self.selected else (0, 0, 0, 0)
        self._ring.rounded_rectangle = (self.x + dp(1), self.y + dp(1), self.width - dp(2), self.height - dp(2), dp(18))

    def on_press(self):
        animate(self, 0.08, opacity=0.7)

    def on_release(self):
        animate(self, 0.3, opacity=1)


class NavItem(ButtonBehavior, BoxLayout):
    """One bottom tab: icon above its name."""

    selected = BooleanProperty(False)

    def __init__(self, name, icon, **kwargs):
        super().__init__(orientation='vertical', padding=[0, dp(6), 0, dp(4)], **kwargs)
        self.name = name
        self.icon = ThemedLabel(text=icon, font_name=ICON_FONT, keep_font=True, font_size='19sp', halign='center')
        self.label = ThemedLabel(text=name, font_size='11sp', halign='center', size_hint_y=None, height=dp(16))
        self.add_widget(self.icon)
        self.add_widget(self.label)
        self.bind(selected=self._sync)
        self._sync()

    def _sync(self, *_):
        role = 'on_primary' if self.selected else 'muted'
        self.icon.role = self.label.role = role

    def on_press(self):
        animate(self.icon, 0.08, font_size=dp(16))

    def on_release(self):
        animate(self.icon, 0.35, 'out_back', font_size=dp(19))


class NavBar(BoxLayout):
    """Bottom tabs with a highlight pill that slides to the selected tab."""

    pill_x = NumericProperty(0)

    def __init__(self, tabs, on_select, **kwargs):
        super().__init__(size_hint_y=None, height=dp(66), padding=[dp(6), dp(6)], spacing=dp(4), **kwargs)
        with self.canvas.before:
            self._bg_color = Color()
            self._bg = RoundedRectangle(radius=[dp(26)])
            self._bg_edge = SmoothLine(width=1)
            self._pill_color = Color()
            self._pill = RoundedRectangle(radius=[dp(20)])
            self._pill_edge = SmoothLine(width=1)
        self.items = {}
        for name, icon in tabs:
            item = NavItem(name, icon)
            item.bind(on_release=lambda it: on_select(it.name))
            self.items[name] = item
            self.add_widget(item)
        self.current = tabs[0][0]
        self.items[self.current].selected = True
        self.bind(pos=self._snap, size=self._snap, pill_x=self._redraw)
        app().bind(palette=self._sync)
        self._sync()

    def select(self, name):
        self.current = name
        for item_name, item in self.items.items():
            item.selected = item_name == name
        animate(self, 0.35, 'out_back', pill_x=self.items[name].x - self.x)

    def _snap(self, *_):
        Clock.schedule_once(lambda dt: setattr(self, 'pill_x', self.items[self.current].x - self.x) or self._redraw())

    def _redraw(self, *_):
        self._bg.pos, self._bg.size = self.pos, self.size
        item = self.items[self.current]
        self._pill.pos, self._pill.size = (self.x + self.pill_x, item.y), item.size
        edge(self._bg_edge, *self.pos, *self.size, dp(26))
        edge(self._pill_edge, *self._pill.pos, *self._pill.size, dp(20))

    def _sync(self, *_):
        palette = app().palette
        self._bg_color.rgba = palette['surface']
        self._pill_color.rgba = palette['primary']


class PlaylistTile(ButtonBehavior, BoxLayout):
    """Square-ish playlist card with a gradient cover and big glyph."""

    def __init__(self, name, count_text, cover_rgb, glyph='♫', image='', on_menu=None, **kwargs):
        super().__init__(orientation='vertical', padding=dp(12), spacing=dp(2), **kwargs)
        self.name = name
        top = [c / 255 for c in cover_rgb[:3]] + [1]
        bottom = [c * 0.45 for c in top[:3]] + [1]
        texture = cover_texture(image, 512) if image else None
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(radius=[dp(20)], texture=texture or gradient_texture(bottom, top))
            # with a picture, a dark fade at the bottom keeps the name readable
            Color(1, 1, 1, 1 if texture else 0)
            self._shade = RoundedRectangle(radius=[dp(20)], texture=gradient_texture((0, 0, 0, 0), (0, 0, 0, 0.85)))
        if on_menu is not None:
            top = BoxLayout(size_hint_y=None, height=dp(30))
            top.add_widget(Widget())
            dots = Pressable(text='⋮', icon=True, font_size='20sp', size_hint_x=None, width=dp(34), radius=dp(15))
            dots.bind(on_release=lambda *_: on_menu(name))
            top.add_widget(dots)
            self.add_widget(top)
        self.add_widget(Label(text='' if texture else glyph, font_name=ICON_FONT, font_size='34sp',
                              color=(1, 1, 1, 0.95)))
        name_label = Label(text=name, bold=True, color=(1, 1, 1, 1), size_hint_y=None, height=dp(22),
                           halign='left', valign='middle', shorten=True)
        name_label.bind(size=lambda w, *_: setattr(w, 'text_size', w.size))
        count = Label(text=count_text, color=(1, 1, 1, 0.75), font_size='12sp', size_hint_y=None, height=dp(18),
                      halign='left', valign='middle')
        count.bind(size=lambda w, *_: setattr(w, 'text_size', w.size))
        self.add_widget(name_label)
        self.add_widget(count)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self._bg.pos, self._bg.size = self.pos, self.size
        self._shade.pos, self._shade.size = self.pos, (self.width, self.height * 0.6)

    def on_press(self):
        animate(self, 0.08, opacity=0.75)

    def on_release(self):
        animate(self, 0.3, opacity=1)
