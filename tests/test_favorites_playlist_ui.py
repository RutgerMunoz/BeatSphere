from app.favorite_playlist_ui import FavoritePlaylistScreen


def test_favorites_playlist_screen_exposes_library_sections():
    screen = FavoritePlaylistScreen()
    assert 'Favorites' in screen.sections
    assert 'Playlists' in screen.sections
    assert 'Recently Played' in screen.sections

    data = screen.snapshot()
    assert data['playlists'] == []
    assert data['favorites_count'] == 0


def test_favorites_playlist_screen_creates_playlists_and_favorites():
    screen = FavoritePlaylistScreen()

    assert screen.create_playlist('Focus Mix') is True
    assert 'Focus Mix' in screen.playlists
    assert screen.create_playlist('') is False

    track_path = '/music/track-01.mp3'
    assert screen.toggle_favorite(track_path) is True
    assert track_path in screen.favorite_tracks
    assert screen.favorites_count == 1

    assert screen.toggle_favorite(track_path) is False
    assert track_path not in screen.favorite_tracks
