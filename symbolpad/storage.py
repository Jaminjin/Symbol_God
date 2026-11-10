"""Settings and personal data, kept in ~/Library/Application Support/SymbolPad."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

# SYMBOLPAD_HOME lets you keep a separate set of settings (handy for testing).
APP_DIR = Path(os.environ.get("SYMBOLPAD_HOME") or Path.home() / "Library" / "Application Support" / "SymbolPad")

DEFAULTS = {
    "dock": "float",               # "float", "left" or "right"
    "expanded": True,
    "panel_pos": None,             # top-left of the floating panel
    "bubble_pos": None,            # top-left of the floating bubble
    "dock_y": None,                # vertical centre of the edge tab when docked
    "insert_method": "type",       # "type", "paste" or "copy"
    "collapse_after_insert": False,
    "hotkey": "ctrl+alt+s",
    "theme": "system",             # "system", "light" or "dark"
    "rgb_border": True,            # animated rainbow edge
    "glass": True,                 # see-through Liquid Glass background
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


class Store:
    def __init__(self, folder: Path = APP_DIR):
        self.folder = Path(folder)
        self.settings_path = self.folder / "settings.json"
        self.drawings_path = self.folder / "my_drawings.json"
        self.cache_path = self.folder / "font_templates.npz"
        self.settings = copy.deepcopy(DEFAULTS)
        self.settings.update(self._read(self.settings_path, {}))
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
