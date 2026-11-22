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


def test_folder_art_uses_standard_names_only(tmp_path):
    from app.favorite_playlist_ui import FavoritePlaylistScreen

    song = tmp_path / 'song.mp3'
    song.write_text('audio')
    (tmp_path / 'cover_photo_from_whatsapp.jpg').write_text('img')
    assert FavoritePlaylistScreen.resolve_album_art(str(song)) is None
    (tmp_path / 'Folder.JPG').write_text('img')
    assert FavoritePlaylistScreen.resolve_album_art(str(song)).endswith('Folder.JPG')


def test_rename_playlist_keeps_songs_and_position_and_rejects_bad_names():
    from app.favorite_playlist_ui import FavoritePlaylistScreen

    screen = FavoritePlaylistScreen()
    for name in ('Gym', 'Chill', 'Party'):
        screen.create_playlist(name)
    screen.add_track_to_playlist('Chill', '/m/a.mp3')
    assert screen.rename_playlist('Chill', '  Sunday Chill ')
    assert screen.playlists == ['Gym', 'Sunday Chill', 'Party']
    assert screen.playlist_tracks['Sunday Chill'] == ['/m/a.mp3'] and 'Chill' not in screen.playlist_tracks
    assert [card['name'] for card in screen.playlist_cards] == ['Gym', 'Sunday Chill', 'Party']
    assert not screen.rename_playlist('Gym', 'Party')      # duplicate
    assert not screen.rename_playlist('Gym', '   ')        # blank
    assert not screen.rename_playlist('Nope', 'Whatever')  # missing


def test_set_playlist_order_requires_the_same_playlists():
    from app.favorite_playlist_ui import FavoritePlaylistScreen

    screen = FavoritePlaylistScreen()
    for name in ('A', 'B', 'C'):
        screen.create_playlist(name)
    assert screen.set_playlist_order(['C', 'A', 'B'])
    assert [card['name'] for card in screen.playlist_cards] == ['C', 'A', 'B']
    assert not screen.set_playlist_order(['C', 'A'])
