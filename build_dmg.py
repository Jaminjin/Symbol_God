"""Build SymbolPad.app and a SymbolPad.dmg installer (macOS).

In PyCharm: right-click this file → Run 'build_dmg'.  Or in Terminal:
    .venv/bin/python build_dmg.py
The finished installer is dist/SymbolPad.dmg.  Needs: pip install pyinstaller
"""

import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST, BUILD = ROOT / "dist", ROOT / "build"
APP, DMG = DIST / "SymbolPad.app", DIST / "SymbolPad.dmg"
sys.path.insert(0, str(ROOT))


def make_icon(icns):
    """Save the τ app icon (drawn by symbolpad/icon.py) as a macOS .icns file."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    from symbolpad.icon import app_icon

    _app = QGuiApplication.instance() or QGuiApplication([])
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "SymbolPad.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale, suffix in ((1, ""), (2, "@2x")):
                app_icon(size * scale).save(str(iconset / f"icon_{size}x{size}{suffix}.png"))
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True)


def build_app(icns):
    from symbolpad import __version__
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
                    "--name", "SymbolPad", "--icon", str(icns),
                    "--osx-bundle-identifier", "com.jaminjin.symbolpad",
                    "--exclude-module", "tkinter",
                    "--distpath", str(DIST), "--workpath", str(BUILD), "--specpath", str(BUILD),
                    str(ROOT / "main.py")], check=True)
    plist_path = APP / "Contents" / "Info.plist"
    with open(plist_path, "rb") as f:
        info = plistlib.load(f)
    info.update({
        "LSUIElement": True,                       # menu-bar style: no Dock icon
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "NSHumanReadableCopyright": "SymbolPad by Jamin Jin",
    })
    with open(plist_path, "wb") as f:
        plistlib.dump(info, f)
    # Editing Info.plist breaks PyInstaller's signature, so sign again (ad-hoc, no Apple account needed).
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(APP)], check=True)


def build_dmg():
    DMG.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "SymbolPad"
        stage.mkdir()
        shutil.copytree(APP, stage / APP.name, symlinks=True)
        (stage / "Applications").symlink_to("/Applications")   # drag-to-install shortcut
        subprocess.run(["hdiutil", "create", "-volname", "SymbolPad", "-srcfolder", str(stage),
                        "-ov", "-format", "UDZO", str(DMG)], check=True)


if __name__ == "__main__":
    DIST.mkdir(exist_ok=True)
    icon = BUILD / "SymbolPad.icns"
    BUILD.mkdir(exist_ok=True)
    make_icon(icon)
    build_app(icon)
    build_dmg()
    print(f"\nDone: {DMG}  ({DMG.stat().st_size / 1e6:.0f} MB)")
