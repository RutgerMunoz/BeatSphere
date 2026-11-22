"""Packs android_aar/AndroidManifest.xml into beatsphere-media-service.aar (manifest-only library).

Run after editing the manifest: python android_aar/build_aar.py
"""
import io
import zipfile
from pathlib import Path

here = Path(__file__).parent
empty_jar = io.BytesIO()
with zipfile.ZipFile(empty_jar, 'w') as jar:
    jar.writestr('META-INF/MANIFEST.MF', 'Manifest-Version: 1.0\n')
with zipfile.ZipFile(here / 'beatsphere-media-service.aar', 'w', zipfile.ZIP_DEFLATED) as aar:
    aar.write(here / 'AndroidManifest.xml', 'AndroidManifest.xml')
    aar.writestr('classes.jar', empty_jar.getvalue())  # the service class itself comes from java/ (android.add_src)
    aar.writestr('R.txt', '')
print('built', here / 'beatsphere-media-service.aar')
