"""The song summary bar at the bottom and the full-screen Now Playing view it opens."""

from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.slider import Slider
from kivy.uix.widget import Widget

from app.library_views import fmt_time
from app.ui.widgets import AlbumArt, Card, EqualizerBars, Pressable, ThemedLabel, animate, app, gradient_texture


class MiniPlayer(Card):
    """Bottom summary of the playing song; tap or swipe up to open Now Playing."""

    def __init__(self, **kwargs):
        super().__init__(orientation='horizontal', size_hint_y=None, height=0, opacity=0,
                         padding=[dp(8), dp(8), dp(10), dp(8)], spacing=dp(8), radius=dp(20), **kwargs)
        with self.canvas.after:
            self._bar_color = Color()
            self._bar = RoundedRectangle(radius=[dp(2)])
        self.progress = 0
        # Fixed square, vertically centered: sizing it from the bar's height drew it low and clipped while the
        # bar was still animating open.
        self.art = AlbumArt(size_hint=(None, None), size=(dp(50), dp(50)), pos_hint={'center_y': 0.5})
        texts = BoxLayout(orientation='vertical', padding=[0, dp(2)])
        self.title = ThemedLabel(text='', bold=True, font_size='15sp', shorten=True)
        self.subtitle = ThemedLabel(text='', role='muted', font_size='12sp', shorten=True)
        texts.add_widget(self.title)
        texts.add_widget(self.subtitle)
        self.eq = EqualizerBars(size_hint=(None, None), size=(dp(20), dp(16)), pos_hint={'center_y': 0.5})
        # Fixed square sizes keep these perfectly round instead of stretching to the bar's height.
        self.prev_btn = Pressable(text='◀◀', icon=True, font_size='14sp', size_hint=(None, None), size=(dp(40), dp(40)),
                                  radius=dp(20), bg_role='surface', pos_hint={'center_y': 0.5})
        self.play_btn = Pressable(text='▶', icon=True, font_size='20sp', size_hint=(None, None), size=(dp(50), dp(50)),
                                  radius=dp(25), selected=True, pos_hint={'center_y': 0.5})
        self.next_btn = Pressable(text='▶▶', icon=True, font_size='14sp', size_hint=(None, None), size=(dp(40), dp(40)),
                                  radius=dp(20), bg_role='surface', pos_hint={'center_y': 0.5})
        for widget in (self.art, texts, self.eq, self.prev_btn, self.play_btn, self.next_btn):
            self.add_widget(widget)
        self.prev_btn.bind(on_release=lambda *_: app().previous_track())
        self.play_btn.bind(on_release=lambda *_: app().toggle_play())
        self.next_btn.bind(on_release=lambda *_: app().next_track())
        self.bind(pos=self._redraw_bar, size=self._redraw_bar)
        app().bind(palette=lambda *_: self._redraw_bar())

    def show(self):
        if self.height == 0:
            animate(self, 0.4, 'out_back', height=dp(72), opacity=1)

    def set_progress(self, fraction):
        self.progress = fraction
        self._redraw_bar()

    def _redraw_bar(self, *_):
        self._bar_color.rgba = app().palette['primary']
        inset = dp(18)
        self._bar.pos = (self.x + inset, self.y + dp(3))
        self._bar.size = (max((self.width - inset * 2) * self.progress, 0), dp(3))

    def on_touch_down(self, touch):
        if self.height and self.collide_point(*touch.pos):
            if super().on_touch_down(touch):  # a button took it
                return True
            touch.ud['mini_start'] = touch.y
            return True
        return False

    def on_touch_up(self, touch):
        if 'mini_start' in touch.ud and (self.collide_point(*touch.pos) or touch.y - touch.ud['mini_start'] > dp(30)):
            app().open_now_playing()
            return True
        return super().on_touch_up(touch)


class NowPlayingView(FloatLayout):
    """Full-screen player that slides up over the app; swipe down or tap ▾ to close."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_open = False
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = Rectangle()
            self._tint = Color(0, 0, 0, 0)
            self._tint_rect = Rectangle()
        col = BoxLayout(orientation='vertical', padding=[dp(22), dp(14), dp(22), dp(26)], spacing=dp(10))

        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        close = Pressable(text='▾', icon=True, font_size='24sp', size_hint_x=None, width=dp(48), radius=dp(24),
                          bg_role='surface')
        close.bind(on_release=lambda *_: self.close())
        self.source_label = ThemedLabel(text='NOW PLAYING', role='muted', font_size='12sp', bold=True, halign='center')
        self.fav_btn = Pressable(text='♡', icon=True, font_size='22sp', size_hint_x=None, width=dp(48), radius=dp(24),
                                 bg_role='surface')
        self.fav_btn.bind(on_release=lambda *_: app().toggle_current_favorite())
        cover_btn = Pressable(text='✎', icon=True, font_size='20sp', size_hint_x=None, width=dp(48), radius=dp(24),
                              bg_role='surface')
        cover_btn.bind(on_release=lambda *_: app().pick_song_cover())
        for widget in (close, self.source_label, cover_btn, self.fav_btn):
            top.add_widget(widget)
        col.add_widget(top)

        self.art = AlbumArt()
        col.add_widget(self.art)

        self.title = ThemedLabel(text='', bold=True, font_size='24sp', size_hint_y=None, height=dp(36),
                                 halign='center', shorten=True)
        self.artist = ThemedLabel(text='', role='muted', font_size='15sp', size_hint_y=None, height=dp(24),
                                  halign='center', shorten=True)
        col.add_widget(self.title)
        col.add_widget(self.artist)

        self.slider = Slider(min=0, max=1, value=0, size_hint_y=None, height=dp(34), value_track=True,
                             value_track_width=dp(4), cursor_size=(dp(18), dp(18)), background_width=dp(30))
        self._dragging = False
        self.slider.bind(on_touch_down=self._drag_start, on_touch_up=self._seek)
        col.add_widget(self.slider)
        times = BoxLayout(size_hint_y=None, height=dp(18))
        self.elapsed = ThemedLabel(text='0:00', role='muted', font_size='12sp')
        self.total = ThemedLabel(text='0:00', role='muted', font_size='12sp', halign='right')
        times.add_widget(self.elapsed)
        times.add_widget(self.total)
        col.add_widget(times)

        controls = BoxLayout(size_hint_y=None, height=dp(84), spacing=dp(10), padding=[0, dp(6)])
        self.shuffle_btn = Pressable(text='⇄', icon=True, font_size='20sp', radius=dp(24), bg_role='surface')
        prev_btn = Pressable(text='◀◀', icon=True, font_size='20sp', radius=dp(26), bg_role='surface')
        self.play_btn = Pressable(text='▶', icon=True, font_size='30sp', radius=dp(36), gradient=True,
                                  size_hint_x=1.5)
        next_btn = Pressable(text='▶▶', icon=True, font_size='20sp', radius=dp(26), bg_role='surface')
        self.repeat_btn = Pressable(text='↻', icon=True, font_size='22sp', radius=dp(24), bg_role='surface')
        self.shuffle_btn.bind(on_release=lambda *_: app().toggle_shuffle())
        prev_btn.bind(on_release=lambda *_: app().previous_track())
        self.play_btn.bind(on_release=lambda *_: app().toggle_play())
        next_btn.bind(on_release=lambda *_: app().next_track())
        self.repeat_btn.bind(on_release=lambda *_: app().cycle_repeat())
        for widget in (self.shuffle_btn, prev_btn, self.play_btn, next_btn, self.repeat_btn):
            controls.add_widget(widget)
        col.add_widget(controls)
        col.add_widget(Widget(size_hint_y=None, height=dp(8)))
        self.add_widget(col)

        self.bind(pos=self._redraw, size=self._redraw)
        app().bind(palette=self._redraw)

    def _redraw(self, *_):
        palette = app().palette
        self._bg.texture = gradient_texture(palette['bg'], palette['bg2'])
        self._bg.pos, self._bg.size = self.pos, self.size
        self._tint.rgba = list(palette['primary'][:3]) + [0.06]
        self._tint_rect.pos, self._tint_rect.size = self.pos, self.size

    def open(self):
        self.is_open = True
        self.y = -self.height
        self.opacity = 1
        animate(self, 0.42, 'out_cubic', y=0)

    def close(self):
        self.is_open = False
        animate(self, 0.32, 'in_cubic', y=-self.height - dp(10))

    def update(self, title, artist, cover, playing, position, length, favorite, shuffle, repeat):
        self.title.text = title
        self.artist.text = artist
        self.art.source = cover
        self.art.spinning = playing
        self.play_btn.text = '❚❚' if playing else '▶'
        self.fav_btn.text = '♥' if favorite else '♡'
        self.fav_btn.fg_role = 'primary' if favorite else 'text'
        self.shuffle_btn.selected = shuffle
        self.repeat_btn.selected = repeat != 'off'
        self.repeat_btn.text = '↻1' if repeat == 'one' else '↻'
        self.set_position(position, length)

    def set_position(self, position, length):
        if not self._dragging:  # don't yank the knob out from under the user's finger
            self.slider.value = position / length if length else 0
        self.elapsed.text = fmt_time(position)
        self.total.text = fmt_time(length)

    def _drag_start(self, slider, touch):
        self._dragging = slider.collide_point(*touch.pos)

    def _seek(self, slider, touch):
        if self._dragging:
            self._dragging = False
            app().seek_fraction(slider.value)

    def on_touch_down(self, touch):
        if not self.is_open or not self.collide_point(*touch.pos):
            return False
        touch.ud['np_start'] = touch.y
        super().on_touch_down(touch)
        return True  # the view is opaque: nothing underneath gets the touch

    def on_touch_up(self, touch):
        if not self.is_open:
            return False
        if touch.ud.get('np_start') is not None and touch.ud['np_start'] - touch.y > dp(90) \
                and not self.slider.collide_point(*touch.pos):
            self.close()
            return True
        return super().on_touch_up(touch)
