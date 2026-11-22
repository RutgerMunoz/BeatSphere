"""Popup grid of device pictures, used to pick wallpapers and song/playlist covers."""

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView

from app.ui.widgets import Card, ImageButton, Pressable, ThemedLabel


class ImagePicker(ModalView):
    """Shows thumbnails; tapping one calls on_pick(path). Optional 'Remove' calls on_clear()."""

    def __init__(self, title, images, on_pick, on_clear=None, on_browse=None, **kwargs):
        super().__init__(size_hint=(0.92, 0.78), background_color=(0, 0, 0, 0), overlay_color=(0, 0, 0, 0.6),
                         **kwargs)
        card = Card(orientation='vertical', padding=dp(14), spacing=dp(10), radius=dp(24))
        card.add_widget(ThemedLabel(text=title, bold=True, font_size='18sp', size_hint_y=None, height=dp(30)))
        if on_browse is not None:
            browse = Pressable(text='Photos, Drive, Gallery…', size_hint_y=None, height=dp(46), radius=dp(18),
                               gradient=True, bold=True)
            browse.bind(on_release=lambda *_: self._choose(lambda _: on_browse(), None))
            card.add_widget(browse)
        grid = GridLayout(cols=3, spacing=dp(8), size_hint_y=None, row_default_height=dp(110), row_force_default=True)
        grid.bind(minimum_height=grid.setter('height'))
        for image in images:
            thumb = ImageButton(source=image, fit_mode='cover')
            thumb.bind(on_release=lambda _, p=image: self._choose(on_pick, p))
            grid.add_widget(thumb)
        if images:
            scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
            scroll.add_widget(grid)
            card.add_widget(scroll)
        else:
            card.add_widget(ThemedLabel(text='No pictures found in Pictures, DCIM or Download', role='muted',
                                        halign='center', wrap=True))
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        if on_clear is not None:
            remove = Pressable(text='Remove', radius=dp(18))
            remove.bind(on_release=lambda *_: self._choose(lambda _: on_clear(), None))
            buttons.add_widget(remove)
        cancel = Pressable(text='Cancel', radius=dp(18))
        cancel.bind(on_release=lambda *_: self.dismiss())
        buttons.add_widget(cancel)
        card.add_widget(buttons)
        self.add_widget(card)

    def _choose(self, callback, path):
        self.dismiss()
        callback(path)
