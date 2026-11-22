[app]

# (str) Title of your application
title = BeatSphere

# (str) Package name
package.name = beatsphere

# (str) Package domain
package.domain = com.beatsphere

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty for all the files)
source.include_exts = py,png,jpg,kv,atlas

# (list) List of inclusions using pattern matching
source.include_patterns = app/**, main.py, assets/**

# (list) List of exclusions using pattern matching
source.exclude_patterns = tests/**, build/**, dist/**
source.exclude_dirs = tests, bin, .venv, brotli, googletest, highway, lcms, lodepng, sjpeg, skcms

# (str) Application versioning
version = 1.0.3

# (str) Application requirements
requirements = python3,kivy,mutagen

# (str) Presplash of the application
presplash.filename = %(source.dir)s/assets/logo.png
android.presplash_color = #030620

# (str) Icon of the application
icon.filename = %(source.dir)s/assets/icon.png
# Adaptive icon (Android 8+): the phone crops these layers to its shape, so the logo fills it like other apps
icon.adaptive_foreground.filename = %(source.dir)s/assets/icon_fg.png
icon.adaptive_background.filename = %(source.dir)s/assets/icon_bg.png

# (str) Supported orientation
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, WAKE_LOCK, POST_NOTIFICATIONS, FOREGROUND_SERVICE, READ_MEDIA_AUDIO, READ_MEDIA_IMAGES

# Android specific
android.api = 34
android.minapi = 24
android.release_artifact = apk
# Java bridge for media buttons (MediaSession.Callback can't be subclassed from Python)
android.add_src = java
# Manifest-only library declaring the media-playback foreground service (see android_aar/)
android.add_aars = android_aar/beatsphere-media-service.aar
# p4a copies AARs into the dist's libs/ but doesn't add that folder as a repository
android.add_gradle_repositories = flatDir { dirs 'libs' }
android.ndk = 28c
android.ndk_path = /home/ubuntu_admin/.buildozer/android/platform/android-ndk-r28c

# (bool) Use AndroidX support
android.enable_androidx = True

# (list) Background service support
android.background = True

# (bool) Identify as media app
android.meta_data = com.google.android.gms.car.application=com.beatsphere

# (str) The Android entry point
android.entrypoint = org.kivy.android.PythonActivity

# (list) Application requirements 
# requirements = sqlite3,requests

[build]

# (int) Verbosity level
verbosity = 2

[python]

# (list) Package extra requirements
# requirements = socks

[buildozer]
# (int) Log level
log_level = 2
