from app.playlist_queue import PlaylistQueue


def test_playlist_queue_tracks_order_and_recent_history():
    queue = PlaylistQueue()
    queue.add_track('song_a.mp3')
    queue.add_track('song_b.mp3')
    queue.add_track('song_c.mp3')

    queue.play_next()
    assert queue.current_track() == 'song_b.mp3'

    queue.mark_played('song_b.mp3')
    assert 'song_b.mp3' in queue.recent_history

    queue.add_to_playlist('favorites', 'song_c.mp3')
    assert 'song_c.mp3' in queue.playlists['favorites']
