"""
py2app build script for Claude Menubar.

Build a standalone .app:
    .venv/bin/pip install py2app
    .venv/bin/python setup.py py2app

Fast iteration (alias mode, symlinks to this venv — not portable):
    .venv/bin/python setup.py py2app -A

Output: dist/Claude Menubar.app
"""

from setuptools import setup

APP = ["app.py"]
DATA_FILES = ["claude icon.png"]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "appicon.icns",
    "packages": ["rumps"],
    "plist": {
        "CFBundleName": "Claude Menubar",
        "CFBundleDisplayName": "Claude Menubar",
        "CFBundleIdentifier": "com.local.claude-menubar",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        # Menu-bar only: no Dock icon, no app-switcher entry.
        "LSUIElement": True,
        "NSHumanReadableCopyright": "",
    },
}

setup(
    name="Claude Menubar",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
