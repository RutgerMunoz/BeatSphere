import importlib
import string

import pytest

from app import i18n
from app.lang import KEYS


def _fields(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


@pytest.mark.parametrize('code', [code for code in i18n.LANGUAGES if code != 'en'])
def test_every_language_covers_all_texts_and_keeps_placeholders(code):
    strings = importlib.import_module(f'app.lang.{code}').STRINGS
    assert set(strings) == set(KEYS), set(KEYS) ^ set(strings)
    for english, translated in strings.items():
        assert translated.strip(), (code, english)
        assert _fields(translated) == _fields(english), (code, english, translated)


def test_tr_switches_language_and_falls_back_to_english():
    try:
        assert i18n.set_language('es') == 'es'
        assert i18n.tr('Songs') == 'Canciones'
        assert i18n.tr('Some song title') == 'Some song title'
        assert i18n.set_language('xx') in i18n.LANGUAGES  # unknown code: the phone's language
    finally:
        i18n.set_language('en')
    assert i18n.tr('Songs') == 'Songs'
