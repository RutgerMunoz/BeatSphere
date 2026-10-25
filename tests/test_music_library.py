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
