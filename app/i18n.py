"""App languages: follows the phone's language unless the user picks one in Settings.

Translations live in app/lang/<code>.py as STRINGS = {english text: translation}. Text without a
translation stays in English. Only scripts Kivy can draw are offered (Latin, Cyrillic, Greek):
its text engine does not join or reorder letters, so Arabic, Hebrew, Hindi or Thai would come out broken.
"""

import importlib
import locale

# code -> the language's own name, as shown in the picker
LANGUAGES = {
    'en': 'English',
    'es': 'Español',
    'pt': 'Português',
    'fr': 'Français',
    'de': 'Deutsch',
    'it': 'Italiano',
    'nl': 'Nederlands',
    'ca': 'Català',
    'ro': 'Română',
    'pl': 'Polski',
    'cs': 'Čeština',
    'sk': 'Slovenčina',
    'hr': 'Hrvatski',
    'hu': 'Magyar',
    'sv': 'Svenska',
    'da': 'Dansk',
    'nb': 'Norsk',
    'fi': 'Suomi',
    'tr': 'Türkçe',
    'id': 'Bahasa Indonesia',
    'ms': 'Bahasa Melayu',
    'tl': 'Filipino',
    'vi': 'Tiếng Việt',
    'sw': 'Kiswahili',
    'ru': 'Русский',
    'uk': 'Українська',
    'bg': 'Български',
    'el': 'Ελληνικά',
}
# phone language codes that mean one of ours (Android reports Norwegian as 'no', Filipino as 'fil', ...)
_ALIASES = {'no': 'nb', 'nn': 'nb', 'fil': 'tl', 'in': 'id'}

_strings = {}
current = 'en'


def tr(text):
    """The text in the current language (English, or unchanged, when there is no translation)."""
    return _strings.get(text, text)


def set_language(code):
    """Switches to `code` ('' or unknown: the phone's language). Returns the code now in use."""
    global _strings, current
    code = code if code in LANGUAGES else system_language()
    try:
        _strings = {} if code == 'en' else importlib.import_module(f'app.lang.{code}').STRINGS
    except ImportError:
        code, _strings = 'en', {}
    current = code
    return code


def system_language():
    """The phone's (or computer's) language if we have it, else English."""
    code = ''
    try:
        from kivy.utils import platform

        if platform == 'android':
            from jnius import autoclass

            code = autoclass('java.util.Locale').getDefault().getLanguage()
        else:
            code = (locale.getlocale()[0] or '').split('_')[0]
    except Exception:
        pass
    code = _ALIASES.get(code.lower(), code.lower())
    return code if code in LANGUAGES else 'en'
