from app.audio import KivyPlayer


class FakeSound:
    length = 30.0

    def __init__(self):
        self.state = 'stop'

    def play(self):
        self.state = 'play'

    def stop(self):
        self.state = 'stop'


def test_desktop_player_tracks_position_with_a_clock_and_detects_the_end():
    now = [100.0]
    player = KivyPlayer(clock=lambda: now[0])
    player._sound = FakeSound()
    player.play()
    now[0] += 12
    assert player.position() == 12 and not player.finished()
    player.pause()
    now[0] += 50
    assert player.position() == 12 and not player.finished()  # paused: clock time doesn't count
    player.play()
    now[0] += 100
    assert player.position() == 30  # clamped to the song length
    player._sound.state = 'stop'  # SDL2 reports stop when the song ends
    assert player.finished()
