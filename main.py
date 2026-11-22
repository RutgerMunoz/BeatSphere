"""BeatSphere Android entry point.

Buildozer expects a top-level main.py file when packaging the app. This wrapper
loads the real application class from the app package and starts the Kivy app.
"""

from app.main import BeatSphereApp


if __name__ == '__main__':
    BeatSphereApp().run()
