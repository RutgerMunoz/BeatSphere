from app.favorite_playlist_ui import FavoritePlaylistScreen


def test_favorites_playlist_screen_exposes_library_sections():
    screen = FavoritePlaylistScreen()
    assert 'Favorites' in screen.sections
    assert 'Playlists' in screen.sections
    assert 'Recently Played' in screen.sections

    data = screen.snapshot()
    assert data['playlists'] == []
    assert data['favorites_count'] == 0
