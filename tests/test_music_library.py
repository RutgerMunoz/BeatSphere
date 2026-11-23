from pathlib import Path

from app.music_library import scan_music_files, supported_extensions


def test_supported_extensions_include_common_audio_types():
    assert '.mp3' in supported_extensions
    assert '.wav' in supported_extensions
    assert '.ogg' in supported_extensions
    assert '.m4a' in supported_extensions


def test_scan_music_files_filters_to_audio_ext_and_sorts_results(tmp_path):
    music_dir = tmp_path / 'music'
    music_dir.mkdir()

    valid_a = music_dir / 'track_one.mp3'
    valid_b = music_dir / 'track_two.wav'
    invalid = music_dir / 'notes.txt'
    valid_a.write_text('audio')
    valid_b.write_text('audio')
    invalid.write_text('not audio')

    tracks = scan_music_files([music_dir])

    assert [track.path for track in tracks] == [str(valid_a), str(valid_b)]
    assert tracks[0].title == 'track one'
    assert tracks[1].title == 'track two'


def test_scan_keeps_original_title_capitalization(tmp_path):
    (tmp_path / 'Bohemian_Rhapsody-Live.mp3').write_text('audio')
    assert scan_music_files([tmp_path])[0].title == 'Bohemian Rhapsody Live'


def _id3_frame(frame_id, body):
    import struct

    return frame_id.encode() + struct.pack('>I', len(body)) + b'\x00\x00' + body


def test_metadata_and_cover_from_id3_tags(tmp_path):
    from app.music_library import extract_cover, read_metadata

    frames = (_id3_frame('TPE1', b'\x03Queen') + _id3_frame('TALB', b'\x03A Night at the Opera')
              + _id3_frame('APIC', b'\x00image/png\x00\x03\x00' + b'\x89PNG fake'))
    size = len(frames)
    synchsafe = bytes([(size >> 21) & 127, (size >> 14) & 127, (size >> 7) & 127, size & 127])
    song = tmp_path / 'song.mp3'
    song.write_bytes(b'ID3\x03\x00\x00' + synchsafe + frames + b'\x00' * 64)

    meta = read_metadata(str(song))
    assert (meta['artist'], meta['album']) == ('Queen', 'A Night at the Opera')
    cover = extract_cover(str(song), tmp_path / 'covers')
    assert cover.endswith('.png') and Path(cover).read_bytes() == b'\x89PNG fake'


def test_metadata_is_blank_for_untagged_files(tmp_path):
    from app.music_library import extract_cover, read_metadata

    song = tmp_path / 'plain.mp3'
    song.write_bytes(b'not really audio')
    assert read_metadata(str(song)) == {'artist': '', 'album': '', 'duration': 0.0}
    assert extract_cover(str(song), tmp_path) is None


def test_tracks_from_index_filters_types_dedupes_and_sorts():
    from app.music_library import tracks_from_index

    paths = ['/m/Zebra.mp3', '/w/voice-note.opus', '/d/notes.txt', '/m/Zebra.mp3', '/m/apple_pie.FLAC']
    assert [t.title for t in tracks_from_index(paths)] == ['apple pie', 'voice note', 'Zebra']


def test_album_art_lookup_survives_unlistable_folder(tmp_path, monkeypatch):
    from pathlib import Path

    from app.favorite_playlist_ui import FavoritePlaylistScreen

    song = tmp_path / 'song.mp3'
    song.write_bytes(b'')

    def refuse(self):
        raise PermissionError('listing blocked')

    monkeypatch.setattr(Path, 'iterdir', refuse)
    assert FavoritePlaylistScreen.resolve_album_art(str(song)) is None
