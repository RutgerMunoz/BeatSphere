import random

from app.player_state import PlayerState


def _state(n=5, current=2):
    state = PlayerState()
    state.set_tracks([f'/m/{i}.mp3' for i in range(n)])
    state.current_index = current
    return state


def test_shuffle_keeps_current_song_first_and_restores_order():
    state = _state()
    original = list(state.track_paths)
    assert state.toggle_shuffle(random.Random(3)) is True
    assert state.current_track() == '/m/2.mp3' and state.current_index == 0
    assert sorted(state.track_paths) == sorted(original)
    assert state.toggle_shuffle() is False
    assert state.track_paths == original and state.current_track() == '/m/2.mp3'


def test_repeat_cycles_off_all_one():
    state = _state()
    assert [state.cycle_repeat() for _ in range(3)] == ['all', 'one', 'off']


def test_advance_honors_repeat_mode_at_the_end():
    state = _state(current=4)
    assert state.advance() is None
    state.repeat_mode = 'all'
    assert state.advance() == '/m/0.mp3'
    state.repeat_mode = 'one'
    assert state.advance() == '/m/0.mp3'
