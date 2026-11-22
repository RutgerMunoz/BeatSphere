import os
import time

from app.library_views import find_images


def test_find_images_newest_first_skips_hidden_and_non_images(tmp_path):
    (tmp_path / '.thumbnails').mkdir()
    (tmp_path / '.thumbnails' / 'hidden.jpg').write_bytes(b'x')
    (tmp_path / 'notes.txt').write_text('x')
    old, new = tmp_path / 'old.jpg', tmp_path / 'sub' / 'new.PNG'
    new.parent.mkdir()
    old.write_bytes(b'x')
    new.write_bytes(b'x')
    os.utime(old, (time.time() - 100, time.time() - 100))
    assert [os.path.basename(p) for p in find_images([tmp_path, tmp_path / 'missing'])] == ['new.PNG', 'old.jpg']
