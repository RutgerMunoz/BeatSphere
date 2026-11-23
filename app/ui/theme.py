"""Color styles and fonts offered in Settings.

Each style has a two-color background gradient (bg → bg2), card surfaces, and an
accent pair (primary → accent) used for highlights and gradient buttons.
"""


def _rgb(hex_color, alpha=1):
    """Converts '#rrggbb' into a Kivy RGBA list."""
    return [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)] + [alpha]


def _style(bg, bg2, surface, surface_alt, primary, accent, text='#ffffff', muted='#b8c2d6', on_primary='#ffffff'):
    return {'bg': _rgb(bg), 'bg2': _rgb(bg2), 'surface': _rgb(surface, 0.92), 'surface_alt': _rgb(surface_alt, 0.95),
            'primary': _rgb(primary), 'accent': _rgb(accent), 'text': _rgb(text), 'muted': _rgb(muted),
            'on_primary': _rgb(on_primary), 'danger': _rgb('#dc3340'), 'on_danger': _rgb('#ffffff')}


THEMES = {
    'Ocean': _style('#050b1d', '#0d2a52', '#111a2e', '#1a2640', '#4da3ff', '#22e1c3'),
    'Daylight': _style('#eef3ff', '#cfdcff', '#ffffff', '#e8eefc', '#3b6cff', '#8a5cff',
                       text='#131a2b', muted='#5b6884'),
    'Purple Night': _style('#0d0618', '#2b0f4a', '#1a1030', '#271a45', '#b26bff', '#ff5fa2'),
    'Emerald': _style('#03110c', '#0b3a2a', '#0d221a', '#163429', '#2ee59d', '#c6ff4d', on_primary='#03110c'),
    'Sunset': _style('#1a0707', '#4a1a12', '#2a1210', '#3d1c17', '#ff7a45', '#ffd166', on_primary='#1a0707'),
    'Midnight': _style('#000000', '#14141c', '#101014', '#1c1c24', '#f2f2f7', '#8e8ea8', on_primary='#000000'),
}

# Kivy's bundled fonts plus Android system fonts when the phone has them.
FONT_CHOICES = [
    ('Default', 'Roboto'),
    ('Clean', 'data/fonts/DejaVuSans.ttf'),
    ('Mono', 'data/fonts/RobotoMono-Regular.ttf'),
    ('Serif', '/system/fonts/NotoSerif-Regular.ttf'),
    ('Handwriting', '/system/fonts/DancingScript-Regular.ttf'),
    ('Casual', '/system/fonts/ComingSoon.ttf'),
    ('Typewriter', '/system/fonts/CutiveMono.ttf'),
]
ICON_FONT = 'data/fonts/DejaVuSans.ttf'  # has ♫ ☰ ⚙ ⇄ ↻ ◀ ▶ ❚ ♥ glyphs that Roboto lacks


def songs_label(count):
    from app.i18n import tr

    return tr('1 song') if count == 1 else tr('{count} songs').format(count=count)
