"""Popups: text prompt (rename), options sheet (song/playlist menu), confirm, info and the "Add songs" picker."""

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.modalview import ModalView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.scrollview import ScrollView

from app.i18n import tr
from app.ui.widgets import Card, Pressable, ThemedInput, ThemedLabel, animate


class TextPrompt(ModalView):
    """Asks for one line of text; Save (or the keyboard's Enter) calls on_save(text)."""

    def __init__(self, title, initial, on_save, **kwargs):
        super().__init__(size_hint=(0.9, None), height=dp(190), pos_hint={'center_x': 0.5, 'top': 0.9},
                         background_color=(0, 0, 0, 0), overlay_color=(0, 0, 0, 0.6), **kwargs)
        self.on_save = on_save
        card = Card(orientation='vertical', padding=dp(16), spacing=dp(12), radius=dp(24))
        card.add_widget(ThemedLabel(text=title, bold=True, font_size='18sp', size_hint_y=None, height=dp(28)))
        self.field = ThemedInput(text=initial, size_hint_y=None, height=dp(48))
        self.field.bind(on_text_validate=lambda *_: self._save())
        card.add_widget(self.field)
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        cancel = Pressable(text='Cancel', radius=dp(18))
        save = Pressable(text='Save', radius=dp(18), gradient=True, bold=True)
        cancel.bind(on_release=lambda *_: self.dismiss())
        save.bind(on_release=lambda *_: self._save())
        buttons.add_widget(cancel)
        buttons.add_widget(save)
        card.add_widget(buttons)
        self.add_widget(card)
        Clock.schedule_once(self._focus, 0.2)  # open the keyboard with the old name selected

    def _focus(self, *_):
        self.field.focus = True
        self.field.select_all()

    def _save(self):
        self.dismiss()
        self.on_save(self.field.text.strip())


class OptionsSheet(ModalView):
    """Menu that slides up from the bottom; each option is (label, callback)."""

    def __init__(self, title, options, **kwargs):
        row = dp(54)
        height = min(dp(70) + row * len(options) + dp(12), Window.height * 0.8)
        super().__init__(size_hint=(0.96, None), height=height,
                         pos_hint={'center_x': 0.5, 'y': 0.02}, background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, 0.55), **kwargs)
        card = Card(orientation='vertical', padding=dp(12), spacing=dp(6), radius=dp(26))
        card.add_widget(ThemedLabel(text=title, bold=True, font_size='17sp', size_hint_y=None, height=dp(34),
                                    shorten=True, padding=[dp(6), 0]))
        buttons = BoxLayout(orientation='vertical', spacing=dp(6), size_hint_y=None)
        buttons.bind(minimum_height=buttons.setter('height'))
        for label, callback in options:
            btn = Pressable(text=label, markup=True, size_hint_y=None, height=row - dp(6), radius=dp(16),
                            halign='left', valign='middle', padding=[dp(16), 0], bg_role='surface_alt')
            btn.bind(size=lambda w, *_: setattr(w, 'text_size', w.size))
            btn.bind(on_release=lambda _, cb=callback: self._choose(cb))
            buttons.add_widget(btn)
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
        scroll.add_widget(buttons)
        card.add_widget(scroll)
        self.card = card
        self.add_widget(card)

    def on_open(self):
        self.card.opacity = 0
        animate(self.card, 0.25, 'out_quad', opacity=1)

    def _choose(self, callback):
        self.dismiss()
        Clock.schedule_once(lambda dt: callback(), 0.05)  # let this sheet close before another popup opens


class ConfirmDialog(ModalView):
    """Warning before something that can't be undone; the destructive button is red and must be tapped."""

    def __init__(self, title, message, confirm_text, on_confirm, **kwargs):
        super().__init__(size_hint=(0.88, None), height=dp(230), background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, 0.65), **kwargs)
        card = Card(orientation='vertical', padding=dp(18), spacing=dp(10), radius=dp(24))
        card.add_widget(ThemedLabel(text=title, bold=True, font_size='18sp', size_hint_y=None, height=dp(28)))
        card.add_widget(ThemedLabel(text=message, role='muted', font_size='14sp', wrap=True, valign='top'))
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        cancel = Pressable(text='Cancel', radius=dp(18))
        confirm = Pressable(text=confirm_text, radius=dp(18), bold=True, bg_role='danger', fg_role='on_danger')
        confirm.bind(on_release=lambda *_: self._confirm(on_confirm))
        cancel.bind(on_release=lambda *_: self.dismiss())
        buttons.add_widget(cancel)
        buttons.add_widget(confirm)
        card.add_widget(buttons)
        self.add_widget(card)

    def _confirm(self, on_confirm):
        self.dismiss()
        on_confirm()


class InfoDialog(ModalView):
    """Properties sheet: label/value rows (song file details, playlist stats) and a Close button."""

    def __init__(self, title, rows, **kwargs):
        row_h = dp(46)
        super().__init__(size_hint=(0.92, None), height=dp(126) + row_h * len(rows), background_color=(0, 0, 0, 0),
                         overlay_color=(0, 0, 0, 0.6), **kwargs)
        card = Card(orientation='vertical', padding=dp(18), spacing=dp(4), radius=dp(24))
        card.add_widget(ThemedLabel(text=title, bold=True, font_size='18sp', size_hint_y=None, height=dp(34),
                                    shorten=True))
        for label, value in rows:
            row = BoxLayout(size_hint_y=None, height=row_h, spacing=dp(10))
            row.add_widget(ThemedLabel(text=label, role='muted', font_size='13sp', size_hint_x=0.34, valign='top'))
            # one line, shortened from the left so long folder paths keep their most specific end
            row.add_widget(ThemedLabel(text=str(value) or '—', font_size='13sp', valign='top', shorten=True,
                                       shorten_from='left'))
            card.add_widget(row)
        close = Pressable(text='Close', size_hint_y=None, height=dp(46), radius=dp(18))
        close.bind(on_release=lambda *_: self.dismiss())
        card.add_widget(close)
        self.add_widget(card)


class PickRow(RecycleDataViewBehavior, ButtonBehavior, BoxLayout):
    """A song in the "Add songs" picker; tapping toggles its checkmark."""

    title = StringProperty('')
    subtitle = StringProperty('')
    path = StringProperty('')
    selected = BooleanProperty(False)
    owner = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(padding=[dp(12), dp(4)], spacing=dp(10), **kwargs)
        texts = BoxLayout(orientation='vertical')
        self.title_label = ThemedLabel(font_size='15sp', bold=True, shorten=True)
        self.subtitle_label = ThemedLabel(role='muted', font_size='12sp', shorten=True)
        texts.add_widget(self.title_label)
        texts.add_widget(self.subtitle_label)
        self.check = Pressable(text='', icon=True, font_size='16sp', size_hint=(None, None), size=(dp(30), dp(30)),
                               radius=dp(15), pos_hint={'center_y': 0.5}, disabled=True)
        self.add_widget(texts)
        self.add_widget(self.check)
        self.bind(title=self._sync, subtitle=self._sync, selected=self._sync)

    def _sync(self, *_):
        self.title_label.text, self.subtitle_label.text = self.title, self.subtitle
        self.check.text = '✓' if self.selected else ''
        self.check.selected = self.selected
        self.title_label.role = 'primary' if self.selected else 'text'

    def on_release(self):
        if self.owner is not None:
            self.owner.toggle(self.path)


class SongPicker(ModalView):
    """Searchable list of songs with checkmarks; "Add" calls on_done(selected paths in library order)."""

    def __init__(self, title, tracks, subtitles, on_done, **kwargs):
        super().__init__(size_hint=(0.94, 0.86), background_color=(0, 0, 0, 0), overlay_color=(0, 0, 0, 0.6), **kwargs)
        self.tracks, self.subtitles, self.on_done = tracks, subtitles, on_done
        self.chosen = set()
        card = Card(orientation='vertical', padding=dp(14), spacing=dp(10), radius=dp(24))
        card.add_widget(ThemedLabel(text=title, bold=True, font_size='18sp', size_hint_y=None, height=dp(30),
                                    shorten=True))
        self.search = ThemedInput(hint_text='Search songs...', size_hint_y=None, height=dp(46))
        self.search.bind(text=lambda *_: self.refresh())
        card.add_widget(self.search)
        self.list = RecycleView(bar_width=dp(3))
        layout = RecycleBoxLayout(orientation='vertical', default_size=(None, dp(56)), default_size_hint=(1, None),
                                  size_hint_y=None, spacing=dp(4))
        layout.bind(minimum_height=layout.setter('height'))
        self.list.add_widget(layout)
        self.list.viewclass = PickRow  # after add_widget: viewclass is forwarded to the layout manager
        card.add_widget(self.list)
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        cancel = Pressable(text='Cancel', radius=dp(18))
        self.add_btn = Pressable(text='Add', radius=dp(18), gradient=True, bold=True)
        cancel.bind(on_release=lambda *_: self.dismiss())
        self.add_btn.bind(on_release=lambda *_: self._done())
        buttons.add_widget(cancel)
        buttons.add_widget(self.add_btn)
        card.add_widget(buttons)
        self.add_widget(card)
        self.refresh()

    def refresh(self):
        query = self.search.text.strip().lower()
        self.list.data = [{'title': t.title, 'subtitle': self.subtitles.get(t.path, ''), 'path': t.path,
                           'selected': t.path in self.chosen, 'owner': self}
                          for t in self.tracks if query in t.title.lower()]
        self.add_btn.text = tr('Add {count}').format(count=len(self.chosen)) if self.chosen else 'Add'

    def toggle(self, path):
        self.chosen ^= {path}
        self.refresh()

    def _done(self):
        self.dismiss()
        if self.chosen:
            self.on_done([t.path for t in self.tracks if t.path in self.chosen])
