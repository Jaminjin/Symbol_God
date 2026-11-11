"""Settings and personal data, kept in ~/Library/Application Support/SymbolPad."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

# SYMBOLPAD_HOME lets you keep a separate set of settings (handy for testing).
APP_DIR = Path(os.environ.get("SYMBOLPAD_HOME") or Path.home() / "Library" / "Application Support" / "SymbolPad")

# A shortcut is {"code": Mac key code, "mods": Carbon modifier bits, "label": what to show}.
CONTROL_OPTION_S = {"code": 1, "mods": 4096 | 2048, "label": "⌃⌥S"}

DEFAULTS = {
    "dock": "float",               # "float", "left" or "right"
    "expanded": True,
    "panel_pos": None,             # top-left of the floating panel
    "panel_size": None,            # [width, height] once you've resized it
    "bubble_pos": None,            # top-left of the floating bubble
    "dock_y": None,                # vertical centre of the edge tab when docked
    "insert_method": "type",       # "type", "paste" or "copy"
    "collapse_after_insert": False,
    "open_key": CONTROL_OPTION_S,  # shortcut that opens SymbolPad from any app (None = no shortcut)
    "close_key": None,             # shortcut that closes it (None = the open shortcut does both)
    "close_action": "hide",        # what closing does: "hide" or "bubble"
    "show_in": "menu",             # where the τ icon lives: "menu", "dock" or "both"
    "look": "glass-dark",          # see theme.LOOKS
    "bg_color": "",                # your own background colour, "#rrggbb" ("" = none)
    "bg_strength": 50,             # how strongly that colour tints the glass, in percent
    "rgb_border": True,            # animated rainbow edge
    "media_on": False,             # show the looping GIF in the panel
    "media_file": "",              # our saved copy of it, inside the data folder
    "category": "math",
    "page": "search",              # "search" or "draw"
    "recent": [],
    "favorites": [],
    "usage": {},
    "seen_welcome": False,
}
MAX_RECENT = 40
MAX_DRAWINGS_PER_SYMBOL = 12

# Version 1 offered a fixed list of shortcuts, stored by these names.
_V1_HOTKEYS = {
    "ctrl+alt+s": CONTROL_OPTION_S,
    "ctrl+shift+s": {"code": 1, "mods": 4096 | 512, "label": "⌃⇧S"},
    "alt+cmd+s": {"code": 1, "mods": 2048 | 256, "label": "⌥⌘S"},
    "ctrl+alt+cmd+s": {"code": 1, "mods": 4096 | 2048 | 256, "label": "⌃⌥⌘S"},
    "ctrl+shift+space": {"code": 49, "mods": 4096 | 512, "label": "⌃⇧Space"},
}


def upgrade(saved):
    """Turn settings saved by SymbolPad 1 into today's names (leaves newer settings alone)."""
    saved = dict(saved)
    if "look" not in saved and ("glass" in saved or "theme" in saved):
        tone = saved.get("theme", "system")
        if saved.get("glass", True):
            saved["look"] = "glass-light" if tone == "light" else "glass-dark"
        else:
            saved["look"] = f"solid-{tone}" if tone in ("system", "light", "dark") else "solid-system"
    if "open_key" not in saved and "hotkey" in saved:
        saved["open_key"] = copy.deepcopy(_V1_HOTKEYS.get(saved["hotkey"]))      # "off" becomes None
    for old in ("glass", "theme", "hotkey"):
        saved.pop(old, None)
    return saved


class Store:
    def __init__(self, folder: Path = APP_DIR):
        self.folder = Path(folder)
        self.settings_path = self.folder / "settings.json"
        self.drawings_path = self.folder / "my_drawings.json"
        self.cache_path = self.folder / "font_templates.npz"
        self.settings = copy.deepcopy(DEFAULTS)
        saved = self._read(self.settings_path, {})
        self.settings.update(upgrade(saved if isinstance(saved, dict) else {}))
        # {char: [drawing, ...]}; a drawing is a list of strokes of [x, y] in 0..1
        self.drawings = self._read(self.drawings_path, {})

    def __getitem__(self, key):
        return self.settings.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self.settings[key] = value
        self.save()

    def save(self):
        self._write(self.settings_path, self.settings)

    # -------------------------------------------------------------- symbols
    def record_use(self, ch):
        recent = [c for c in self.settings["recent"] if c != ch]
        self.settings["recent"] = [ch] + recent[: MAX_RECENT - 1]
        usage = self.settings["usage"]
        usage[ch] = usage.get(ch, 0) + 1
        self.save()

    def is_favorite(self, ch):
        return ch in self.settings["favorites"]

    def toggle_favorite(self, ch):
        favs = self.settings["favorites"]
        if ch in favs:
            favs.remove(ch)
        else:
            favs.append(ch)
        self.save()
        return ch in favs

    def clear_recent(self):
        self.settings["recent"] = []
        self.settings["usage"] = {}
        self.save()

    # -------------------------------------------------------------- drawings
    def add_drawing(self, ch, strokes):
        kept = self.drawings.setdefault(ch, [])
        kept.append([[[round(x, 3), round(y, 3)] for x, y in s] for s in strokes])
        del kept[:-MAX_DRAWINGS_PER_SYMBOL]
        self._write(self.drawings_path, self.drawings)

    def clear_drawings(self):
        self.drawings = {}
        self._write(self.drawings_path, self.drawings)

    # -------------------------------------------------------------- files
    @staticmethod
    def _read(path, default):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def _write(self, path, data):
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            tmp = Path(path).with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            print(f"SymbolPad: could not save {path}: {exc}")
