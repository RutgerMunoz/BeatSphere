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


def test_favorites_playlist_screen_builds_album_art_cards_for_playlists():
    screen = FavoritePlaylistScreen()
    screen.create_playlist('Late Night', cover_color=(20, 60, 120, 255), cover_path='/covers/late-night.jpg')
    screen.add_track_to_playlist('Late Night', '/music/track-01.mp3')
    screen.add_track_to_playlist('Late Night', '/music/track-02.mp3')

    card = screen.playlist_cards[0]
    assert card['name'] == 'Late Night'
    assert card['track_count'] == 2
    assert card['cover_path'] == '/covers/late-night.jpg'
    assert card['cover_color'] == (20, 60, 120, 255)
