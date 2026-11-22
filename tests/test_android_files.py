from app.android_files import delete_audio_file


def test_delete_removes_a_deletable_file(tmp_path):
    song = tmp_path / 'song.mp3'
    song.write_bytes(b'audio')
    results = []
    delete_audio_file(str(song), results.append)
    assert results == [True] and not song.exists()


def test_delete_reports_failure_for_missing_file_off_android(tmp_path):
    results = []
    delete_audio_file(str(tmp_path / 'missing.mp3'), results.append)
    assert results == [False]
