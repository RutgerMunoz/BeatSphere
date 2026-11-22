from app.library_views import LETTERS, filter_tracks, fmt_time, group_by_folder, letter_of, make_mix, sort_tracks
from app.music_library import Track


def _tracks(*titles, folder='/music'):
    return [Track(path=f'{folder}/{title}.mp3', title=title) for title in titles]


def test_letter_of_groups_digits_symbols_and_accents():
    assert letter_of('7 Rings') == '#'
    assert letter_of('¡Hola!') == '#'
    assert letter_of('Éxitos') == 'E'
    assert letter_of('bohemian rhapsody') == 'B'
    assert LETTERS[:3] == ['All', '#', 'A'] and LETTERS[-1] == 'Z'


def test_sort_puts_numbers_first_then_a_to_z_naturally():
    tracks = _tracks('zebra', 'Track 10', '99 Problems', 'apple', 'Éxitos', 'Track 2', '7 Rings')
    assert [t.title for t in sort_tracks(tracks)] == ['7 Rings', '99 Problems', 'apple', 'Éxitos', 'Track 2', 'Track 10', 'zebra']


def test_filter_by_letter_and_query():
    tracks = _tracks('Apple Song', 'Another One', 'Banana', '1999')
    assert len(filter_tracks(tracks)) == 4
    assert [t.title for t in filter_tracks(tracks, 'A')] == ['Apple Song', 'Another One']
    assert [t.title for t in filter_tracks(tracks, '#')] == ['1999']
    assert [t.title for t in filter_tracks(tracks, 'All', 'nan')] == ['Banana']


def test_group_by_folder_sorts_folders_and_tracks():
    tracks = _tracks('b', 'a', folder='/x/Rock') + _tracks('c', folder='/x/Jazz')
    groups = group_by_folder(tracks)
    assert [p.replace('\\', '/') for p in groups] == ['/x/Jazz', '/x/Rock']
    assert [t.title for t in list(groups.values())[1]] == ['a', 'b']


def test_make_mix_is_a_permutation():
    paths = [f'/m/{i}.mp3' for i in range(20)]
    mixed = make_mix(paths, seed=1)
    assert sorted(mixed) == sorted(paths) and mixed != paths


def test_fmt_time():
    assert [fmt_time(s) for s in (0, 5.9, 65, 3725, None)] == ['0:00', '0:05', '1:05', '1:02:05', '0:00']


def test_move_item_moves_to_any_position():
    from app.library_views import move_item

    assert move_item([1, 2, 3, 4, 5], 0, 2) == [2, 3, 1, 4, 5]
    assert move_item([1, 2, 3, 4, 5], 4, 0) == [5, 1, 2, 3, 4]


def test_apply_custom_order_keeps_saved_order_and_appends_new_songs_a_to_z():
    from app.library_views import apply_custom_order

    tracks = _tracks('Apple', 'Zebra', 'Mango', 'Banana')
    order = ['/music/Zebra.mp3', '/music/Apple.mp3', '/music/Deleted.mp3']
    assert [t.title for t in apply_custom_order(tracks, order)] == ['Zebra', 'Apple', 'Banana', 'Mango']
