"""Animated brand: the header's living logo and the intro played when BeatSphere opens.

Android launcher icons can't move, so the motion lives inside the app: the planet spins
while sound-wave rings expand from it. Both respect app.motion.
"""

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, PopMatrix, PushMatrix, Rectangle, Rotate, RoundedRectangle, SmoothLine
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.widget import Widget

from app.ui.widgets import app, cover_texture, gradient_texture

PLANET = 'assets/brand/planet.png'
WORDMARK = 'assets/brand/wordmark.png'
RING_COLORS = [(0.13, 0.88, 1), (0.30, 0.48, 1), (1, 0.37, 0.82)]  # the planet's cyan → blue → magenta


class WaveRings:
    """Rings that grow out of a center and fade; call step(dt) every frame."""

    def __init__(self, canvas, count, period, width):
        self.period, self.width, self.phases = period, width, [i / count for i in range(count)]
        with canvas:
            self.items = [(Color(*RING_COLORS[i % 3], 0), SmoothLine(width=width)) for i in range(count)]

    def step(self, dt, center, r_from, r_to, alpha=0.7):
        for i, (color, line) in enumerate(self.items):
            self.phases[i] = (self.phases[i] + dt / self.period) % 1
            t = self.phases[i]
            radius = r_from + (r_to - r_from) * t
            color.a = alpha * (1 - t) ** 1.6
            line.circle = (center[0], center[1], radius)


def spinning_disc(canvas, texture):
    """Planet drawn as a disc inside a rotation; returns (rotate, disc) to update each frame."""
    with canvas:
        PushMatrix()
        rotate = Rotate(angle=0)
        Color(1, 1, 1, 1)
        disc = RoundedRectangle(texture=texture)
        PopMatrix()
    return rotate, disc


class LivingLogo(Widget):
    """The header logo: the planet slowly spinning, with soft waves pulsing out of it."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self.rings = WaveRings(self.canvas.before, 2, 2.6, dp(1.2))
        self.rotate, self.disc = spinning_disc(self.canvas, cover_texture(PLANET))
        self.bind(pos=self._layout, size=self._layout)
        Clock.schedule_interval(self._tick, 1 / 30)

    def _layout(self, *_):
        side = min(self.size) * 0.82
        self.disc.pos = (self.center_x - side / 2, self.center_y - side / 2)
        self.disc.size = (side, side)
        self.disc.radius = [side / 2]
        self.rotate.origin = self.center

    def _tick(self, dt):
        side = min(self.size) * 0.82
        if app().motion:
            self.rotate.angle = (self.rotate.angle - dt * 360 / 14) % 360  # one slow turn every 14 s
            self.rings.step(dt, self.center, side / 2, side / 2 + dp(9), alpha=0.8)
        else:
            self.rings.step(0, self.center, side / 2, side / 2, alpha=0)


class IntroOverlay(FloatLayout):
    """Opening animation: the planet spins in, waves expand, the name fades in; tap to skip."""

    def __init__(self, on_done, **kwargs):
        super().__init__(**kwargs)
        self.on_done = on_done
        self.elapsed = 0
        palette = app().palette
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.bg = Rectangle(texture=gradient_texture(palette['bg2'], palette['bg']))
        self.rings = WaveRings(self.canvas.before, 4, 1.4, dp(2))
        # the planet as a disc, so the art's own dark square background doesn't show as a box
        self.planet = Widget(size_hint=(None, None), opacity=0)
        self.rotate, self.disc = spinning_disc(self.planet.canvas, cover_texture(PLANET, 512))
        self.word = Image(source=WORDMARK, size_hint=(None, None), opacity=0, fit_mode='contain')
        self.add_widget(self.planet)
        self.add_widget(self.word)
        self.bind(pos=self._layout, size=self._layout)
        self._event = None

    def begin(self):
        """Starts the timeline; call once the window is on screen so the user sees all of it."""
        # Timeline runs on frames actually drawn, not wall-clock timers: a slow app start would
        # otherwise end the intro before the user saw it.
        self._event = Clock.schedule_interval(self._tick, 1 / 30)

    def _layout(self, *_):
        self.bg.pos, self.bg.size = self.pos, self.size
        self.base_side = min(self.width * 0.62, self.height * 0.4)
        self.word.size = (min(self.width * 0.8, dp(320)), dp(60))
        self.word.center = (self.center_x, self.center_y + dp(30) - self.base_side / 2 - dp(52))
        self._tick(0)

    def _tick(self, dt):
        self.elapsed += min(dt, 1 / 20)  # a slow first frame shouldn't skip the scale-in
        grow = 1 - (1 - min(self.elapsed / 0.6, 1)) ** 3  # ease-out scale-in over 0.6 s
        side = getattr(self, 'base_side', 0) * (0.55 + 0.45 * grow)
        self.planet.size = (side, side)
        self.planet.center = (self.center_x, self.center_y + dp(30))
        self.disc.pos, self.disc.size, self.disc.radius = self.planet.pos, self.planet.size, [side / 2]
        spin = 1 - (1 - min(self.elapsed / 2.4, 1)) ** 3  # fast turn that eases to a stop
        self.rotate.origin, self.rotate.angle = self.planet.center, -720 * spin  # two full turns: lands upright
        self.rings.step(dt, self.planet.center, side * 0.35, side * 1.05, alpha=0.85)
        self.planet.opacity = min(self.elapsed / 0.5, 1)
        self.word.opacity = min(max(self.elapsed - 0.9, 0) / 0.6, 1)
        if self.elapsed >= 2.6:
            self.finish()

    def on_touch_down(self, touch):
        self.finish()
        return True

    def finish(self):
        if self._event is None:
            return
        self._event.cancel()
        self._event = None
        anim = Animation(opacity=0, d=0.45, t='in_quad')
        anim.bind(on_complete=lambda *_: self.on_done(self))
        anim.start(self)
