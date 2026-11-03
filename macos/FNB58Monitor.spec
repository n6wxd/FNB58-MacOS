# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for "FNB58 Monitor.app".

Build with macos/build_app.sh. Entry point is desktop.py at the repo root.
"""

import os

ROOT = os.path.dirname(SPECPATH)
APP_NAME = 'FNB58 Monitor'
VERSION = '1.0.0'
USAGE = 'FNB58 Monitor uses Bluetooth to read live measurements from your FNIRSI power meter.'

a = Analysis(
    [os.path.join(ROOT, 'desktop.py')],
    pathex=[ROOT],
    datas=[
        (os.path.join(ROOT, 'templates'), 'templates'),
        (os.path.join(ROOT, 'static'), 'static'),
    ],
    # Flask-SocketIO picks its async driver with importlib at runtime.
    hiddenimports=['engineio.async_drivers.threading'],
    excludes=['tkinter', 'pandas', 'matplotlib', 'scipy', 'PIL', 'IPython', 'pytest'],
    noarchive=False,
)

# On macOS the meter is read through hidapi (bundled in the `hid` extension).
# PyInstaller's pyusb hook still drags in whatever libusb ctypes finds, which
# may not even match the app's architecture, so leave it out.
a.binaries = [b for b in a.binaries if not os.path.basename(b[0]).startswith('libusb')]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    argv_emulation=False,
    target_arch=None,          # native arch of the build Python
    codesign_identity=None,    # ad-hoc signature
    icon=os.path.join(SPECPATH, 'icon.icns'),
)

coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME)

app = BUNDLE(
    coll,
    name=f'{APP_NAME}.app',
    icon=os.path.join(SPECPATH, 'icon.icns'),
    bundle_identifier='io.github.redthoroughbred.fnb58-monitor',
    version=VERSION,
    info_plist={
        'CFBundleDisplayName': APP_NAME,
        'CFBundleVersion': VERSION,
        'LSApplicationCategoryType': 'public.app-category.utilities',
        'LSMinimumSystemVersion': '14.0',  # numpy's macOS wheels target 14.0
        'NSHumanReadableCopyright': 'MIT License. Not affiliated with FNIRSI.',
        'NSHighResolutionCapable': True,
        'NSBluetoothAlwaysUsageDescription': USAGE,
        # App Nap would throttle the 100 Hz USB reader while the window is hidden.
        'NSAppSleepDisabled': True,
    },
)
