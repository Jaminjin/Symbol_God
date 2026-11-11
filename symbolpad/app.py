"""Starts SymbolPad and wires the window, search, recognizer and macOS pieces together."""

from __future__ import annotations

import os
import shutil
import signal
import sys
import threading
from pathlib import Path

# By default Qt activates the whole app whenever a window is raised, which would
# steal the keyboard back from Word right after typing a symbol.  We activate
# SymbolPad ourselves, only when you actually want it.
os.environ.setdefault("QT_MAC_SET_RAISE_PROCESS", "0")

from PySide6.QtCore import QObject, Qt, QTimer, Signal, qVersion
from PySide6.QtGui import QActionGroup, QColor, QFont, QIcon, QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QColorDialog, QFileDialog, QMenu, QSystemTrayIcon

from . import glyphs, macos, theme
from .engine import DrawingEngine
from .icon import app_icon
from .inserter import Inserter
from .shortcuts import ShortcutDialog
from .storage import Store
from .symbols import SymbolIndex
from .widgets import Toast
from .window import SHOW_IN, PaletteWindow

QT_VERSION = qVersion()


class Controller(QObject):
    _fonts_checked = Signal(object)

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.native = macos.AVAILABLE and app.platformName() == "cocoa"
        self.store = Store()
        self.index = SymbolIndex()
        self.index.usage = self.store["usage"]
        self.theme = self._build_theme()
        self.glass_kind = ""               # "glass" or "blur" once macOS is drawing glass behind the palette
        self.engine = DrawingEngine(self.index, self.store)
        self.tracker = macos.FrontAppTracker() if self.native else None
        self.inserter = Inserter(self.store, self.tracker)
        self.hotkeys = macos.GlobalHotkeys()
        self._hotkeys_paused = False
        self._shortcut_dialog = None
        self._color_dialog = None
        self._color_timer = QTimer(self, singleShot=True, interval=50, timeout=self._apply_picked_color)
        self._picked_color = None
        self.toast = Toast()
        self.window = PaletteWindow(self)
        self.tray = self._make_tray()
        self._dock_menu = self._make_dock_menu()

        self.inserter.finished.connect(self.show_toast)
        self.inserter.needs_permission.connect(self.window.panel.show_permission_banner)
        self.engine.ready.connect(self.window.panel.refresh_matches)
        self._fonts_checked.connect(self._hide_missing)
        self.window.changed.connect(self.refresh_hotkeys)
        app.styleHints().colorSchemeChanged.connect(lambda *_: self.apply_theme())
        app.applicationStateChanged.connect(self._app_state_changed)
        if self.native:
            macos.on_dock_click(lambda: QTimer.singleShot(0, self.window.summon))
        self.apply_theme()
        self._check_fonts()

    def start(self):
        self.apply_show_in()
        self.window.apply_layout()
        self.window.show()
        self.after_show()
        self.window.panel.load_media(self.media_path())
        self.window.panel.refresh_all()
        self._shortcuts_changed()
        if self.native:
            if not self.refresh_hotkeys().get("open", True):
                QTimer.singleShot(1500, lambda: self.show_toast(
                    f"{self.open_label} is taken by another app. Pick other keys in ⚙ → Shortcuts", ms=6000))
            if self.store["insert_method"] != "copy" and not macos.can_type():
                self.window.panel.show_permission_banner()
        QTimer.singleShot(200, self.engine.start)
        if not self.store["seen_welcome"]:
            QTimer.singleShot(1200, self._welcome)

    def _check_fonts(self):
        """Hide characters this Mac can't draw (checked on first launch, then cached).

        Step 1 (background thread): ask CoreText which characters have no font.
        Step 2 (main thread, in small batches): draw the rest and drop any that
        come out as the striped "no glyph" box.
        """
        if not macos.AVAILABLE:
            return
        self._coverage_path = self.store.folder / "font_coverage.json"
        self._coverage_key = f"{macos.font_signature()}|qt{QT_VERSION}"
        cached = Store._read(self._coverage_path, {})
        if cached.get("key") == self._coverage_key:
            self.index.hide(chr(cp) for cp in cached.get("missing", []))
            return
        chars = [s.char for s in self.index.symbols]
        threading.Thread(target=lambda: self._fonts_checked.emit(macos.missing_glyphs(chars)),
                         daemon=True).start()

    def _hide_missing(self, missing):
        self.index.hide(missing)
        self.window.panel.refresh_results()
        self._render_check([s.char for s in self.index.symbols], 0, set(missing))

    def _render_check(self, chars, start, bad, batch=1500):
        bad.update(glyphs.unrenderable(chars[start:start + batch], self.window.panel.grid.font()))
        if start + batch < len(chars):
            QTimer.singleShot(15, lambda: self._render_check(chars, start + batch, bad))
            return
        self.index.hide(bad)
        self.window.panel.refresh_results()
        self.store._write(self._coverage_path, {"key": self._coverage_key, "missing": sorted(ord(c) for c in bad)})

    def _welcome(self):
        self.store["seen_welcome"] = True
        key = self.open_label
        self.show_toast(f"Tip: press {key} anywhere to open SymbolPad" if key else "Tip: drag me by the top bar",
                        ms=4500)

    # ------------------------------------------------------------------ look
    def _build_theme(self):
        return theme.build(self.store["look"], self.store["bg_color"], self.store["bg_strength"])

    def apply_theme(self):
        self.theme = self._build_theme()
        self.app.setPalette(theme.palette(self.theme))
        self.app.setStyleSheet(theme.stylesheet(self.theme))
        self.window.set_theme(self.theme)
        self.toast.theme = self.theme

    def after_show(self):
        if self.native:
            macos.float_above_everything(self.window)
        self.update_glass()
        QTimer.singleShot(200, self.update_glass)      # again once macOS has finished setting the new window up

    def update_glass(self):
        """Have macOS draw Liquid Glass behind the palette (panel, bubble or edge tab) if the look uses it."""
        if not (self.native and self.window.isVisible()):
            return
        t = self.theme
        radius, inset = self.window.glass_shape()
        kind = macos.set_glass(self.window, bool(t.glass), radius=radius, clear=t.glass == "clear",
                               dark=t.glass_dark, inset=inset)
        if kind != self.glass_kind:
            self.glass_kind = kind
            self.window.update()
            self.window.bubble.update()

    def show_toast(self, text, ms=2200):
        self.toast.show_message(text, self.window.frameGeometry(), below=not self.window.expanded, ms=ms)
        if self.native:
            macos.float_above_everything(self.toast)

    def _make_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        pix = QPixmap(44, 44)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        font = QFont()
        font.setPixelSize(32)
        font.setBold(True)
        p.setFont(font)
        p.setPen(Qt.GlobalColor.black)
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "τ")
        p.end()
        icon = QIcon(pix)
        icon.setIsMask(True)          # lets macOS tint it for light/dark menu bars
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("SymbolPad")
        menu = QMenu()
        self._tray_show = menu.addAction("Show SymbolPad")
        self._tray_show.triggered.connect(lambda: self.window.summon())
        menu.addSeparator()
        self._add_places(menu)
        menu.addSeparator()
        where = menu.addMenu("Show the τ icon in")
        group = QActionGroup(where)
        self._tray_show_in = {}
        for value, label in SHOW_IN:
            a = where.addAction(label)
            a.setCheckable(True)
            a.setChecked(value == self.store["show_in"])
            group.addAction(a)
            a.triggered.connect(lambda _=False, v=value: self.set_setting("show_in", v))
            self._tray_show_in[value] = a
        self._tray_rgb = menu.addAction("RGB border")
        self._tray_rgb.setCheckable(True)
        self._tray_rgb.setChecked(self.store["rgb_border"])
        self._tray_rgb.triggered.connect(lambda on: self.set_setting("rgb_border", on))
        menu.addSeparator()
        menu.addAction("Quit SymbolPad").triggered.connect(self.quit)
        tray.setContextMenu(menu)
        self._tray_menu = menu
        return tray

    def _add_places(self, menu):
        menu.addAction("Dock to the left").triggered.connect(lambda: self._place("left"))
        menu.addAction("Dock to the right").triggered.connect(lambda: self._place("right"))
        menu.addAction("Floating box").triggered.connect(lambda: self._place("float"))

    def _make_dock_menu(self):
        """What you get by right-clicking the Dock icon (macOS adds Quit itself)."""
        menu = QMenu()
        if not hasattr(menu, "setAsDockMenu"):
            return None
        menu.addAction("Show SymbolPad").triggered.connect(lambda: self.window.summon())
        menu.addSeparator()
        self._add_places(menu)
        menu.setAsDockMenu()
        return menu

    def apply_show_in(self):
        """Put the τ icon in the menu bar, the Dock or both."""
        where = self.store["show_in"]
        if where not in ("menu", "dock", "both") or (self.tray is None and where == "menu"):
            where = "menu" if self.tray is not None else "dock"      # there must always be a way back in
        if self.native:
            macos.show_in_dock(where != "menu")
        if self.tray is not None:
            self.tray.setVisible(where != "dock")
            for value, action in self._tray_show_in.items():
                action.setChecked(value == where)
        self.window.panel.update_hints()

    def _app_state_changed(self, state):
        # With a Dock icon you can also come back with ⌘-Tab, which doesn't count as a Dock click.
        if (state == Qt.ApplicationState.ApplicationActive and self.native and macos.is_in_dock()
                and not self.window.isVisible()):
            QTimer.singleShot(0, self.window.summon)

    def _place(self, where):
        self.window.summon()
        if where == "float":
            if self.store["dock"] != "float":
                self.window.float_here()
        else:
            self.window.dock_to(where)

    # ------------------------------------------------------------------ actions
    def insert(self, ch, strokes=None, pad_size=None):
        if not ch:
            return
        if strokes:
            self.engine.learn(ch, strokes, pad_size)
        self._used(ch)
        self.inserter.insert(ch)
        if self.store["collapse_after_insert"]:
            self.window.collapse(return_focus=False)

    def copy(self, ch):
        self.inserter.copy(ch)
        self._used(ch)
        self.show_toast(f"Copied {ch}")

    def copy_text(self, text):
        self.inserter.copy(text)
        self.show_toast(f"Copied {text}")

    def _used(self, ch):
        self.store.record_use(ch)
        self.index.usage = self.store["usage"]
        self.window.panel.refresh_recent()

    def toggle_favorite(self, ch):
        added = self.store.toggle_favorite(ch)
        self.window.panel.on_favorites_changed(ch)
        self.show_toast(f"{ch} added to Favorites" if added else f"{ch} removed from Favorites")

    def focus_palette(self):
        if self.native:
            macos.bring_self_to_front()
        self.window.raise_()
        self.window.activateWindow()

    def return_focus(self):
        """Hand the keyboard back to the app you were typing in."""
        target = self.tracker.target() if self.tracker else None
        if target is not None:
            macos.activate(target)

    def hide_palette(self):
        self.window.hide()
        self.return_focus()

    def close_palette(self):
        """What the close shortcut does: hide the palette, or shrink it to the bubble."""
        if self.store["close_action"] == "bubble":
            self.window.collapse()
        else:
            self.hide_palette()

    # ------------------------------------------------------------------ shortcuts
    @property
    def open_label(self):
        return macos.shortcut_label(self.store["open_key"])

    def _wanted_hotkeys(self):
        """The shortcuts to listen for right now, as (open, close)."""
        open_key, close_key = self.store["open_key"], self.store["close_key"]
        open_key = open_key if macos.valid_shortcut(open_key) else None
        close_key = close_key if macos.valid_shortcut(close_key) else None
        if macos.same_shortcut(open_key, close_key):
            close_key = None                                     # one shortcut that does both
        # The close shortcut only exists while there is something to close; the
        # rest of the time those keys are left to whatever app you're in.
        if not (self.window.isVisible() and self.window.expanded):
            close_key = None
        return open_key, close_key

    def refresh_hotkeys(self):
        """(Re)register the system-wide shortcuts.  Returns {"open": worked, "close": worked}."""
        if not self.native or self._hotkeys_paused:
            return {}
        open_key, close_key = self._wanted_hotkeys()
        results = {}
        for name, spec, pressed in (("open", open_key, self.open_pressed), ("close", close_key, self.close_pressed)):
            now = self.hotkeys.spec(name)
            if (spec is None and now is None) or macos.same_shortcut(spec, now):
                results[name] = True
            else:
                results[name] = self.hotkeys.set(name, spec, lambda fn=pressed: QTimer.singleShot(0, fn))
        return results

    def pause_hotkeys(self, paused):
        """Stop listening while a new shortcut is being recorded, so the old one can be pressed again."""
        self._hotkeys_paused = bool(paused)
        if paused:
            self.hotkeys.clear()
        else:
            self.refresh_hotkeys()

    def has_close_key(self):
        """True if closing has its own shortcut, rather than sharing the open one."""
        close_key = self.store["close_key"]
        return macos.valid_shortcut(close_key) and not macos.same_shortcut(close_key, self.store["open_key"])

    def open_pressed(self):
        w = self.window
        if not self.has_close_key() and w.isVisible() and w.expanded and w.isActiveWindow():
            self.close_palette()                 # no separate close shortcut: pressing it again closes
        else:
            w.summon()

    def close_pressed(self):
        if self.window.isVisible() and self.window.expanded:
            self.close_palette()

    def set_shortcut(self, which, spec):
        """Change the "open" or "close" shortcut (None removes it).  Returns (worked, what to tell the user)."""
        key, other = f"{which}_key", "close_key" if which == "open" else "open_key"
        before = (self.store["open_key"], self.store["close_key"])
        if spec is not None and macos.same_shortcut(spec, self.store[other]):
            if which == "close":
                spec = None                      # same keys as open: that's simply one shortcut for both
            else:
                self.store.settings["close_key"] = None
        self.store[key] = spec
        if not self.refresh_hotkeys().get(which, True):
            self.store.settings["open_key"], self.store.settings["close_key"] = before
            self.store.save()
            self.refresh_hotkeys()
            self._shortcuts_changed()
            return False, (f"macOS wouldn't let SymbolPad use {macos.shortcut_label(spec)}; "
                           "another app probably has it. Try other keys.")
        self._shortcuts_changed()
        open_label = self.open_label
        close_label = macos.shortcut_label(self.store["close_key"]) if self.has_close_key() else ""
        if open_label and close_label:
            return True, f"{open_label} opens SymbolPad and {close_label} closes it, from any app."
        if open_label:
            return True, f"{open_label} opens SymbolPad from any app. Press it again to close it."
        if close_label:
            return True, f"{close_label} closes SymbolPad. Nothing opens it now, so use the τ icon for that."
        return True, "No shortcuts now. Open SymbolPad with the τ icon."

    def _shortcuts_changed(self):
        label = self.open_label
        if self.tray is not None:
            self._tray_show.setText(f"Show SymbolPad    {label}" if label else "Show SymbolPad")
        self.window.panel.update_hints()

    def edit_shortcuts(self, _checked=False):
        QTimer.singleShot(0, self._show_shortcut_dialog)          # let the menu close first

    def _show_shortcut_dialog(self):
        if self._shortcut_dialog is None:
            self._shortcut_dialog = ShortcutDialog(self)
        dialog = self._shortcut_dialog
        dialog.refresh()
        dialog.show_beside(self.window.frameGeometry())
        self._bring_forward(dialog)

    def _bring_forward(self, widget):
        if self.native:
            macos.float_above_everything(widget, over_palette=True)
            macos.bring_self_to_front()
        widget.raise_()
        widget.activateWindow()

    def ask_for_permission(self):
        self.window.panel.banner.hide()
        macos.ask_for_typing_permission()
        # macOS gives the permission to whatever started SymbolPad: the app itself, or PyCharm / Terminal.
        who = "SymbolPad" if getattr(sys, "frozen", False) else "PyCharm (or Terminal)"
        self.show_toast(f"Switch on {who} in the list, then quit and reopen SymbolPad", ms=6000)

    def set_setting(self, key, value):
        self.store[key] = value
        if key in ("look", "bg_color", "bg_strength"):
            self.apply_theme()
            self.update_glass()
        elif key == "rgb_border":
            self.window.set_rgb(value)
            if self.tray is not None:
                self._tray_rgb.setChecked(value)
        elif key == "show_in":
            self.apply_show_in()

    # ------------------------------------------------------------------ background colour
    def choose_bg_color(self, _checked=False):
        QTimer.singleShot(0, self._show_color_dialog)             # let the menu close first

    def _show_color_dialog(self):
        """macOS's colour picker; the palette changes colour as you move around in it."""
        if self._color_dialog is None:
            dialog = QColorDialog(self.window)
            dialog.setOption(QColorDialog.ColorDialogOption.NoButtons)
            dialog.setWindowTitle("SymbolPad background colour")
            dialog.currentColorChanged.connect(self._color_picked)
            self._color_dialog = dialog
        dialog = self._color_dialog
        start = theme.parse_color(self.store["bg_color"]) or QColor(theme.COLORS[1][0])
        dialog.blockSignals(True)
        dialog.setCurrentColor(start)
        dialog.blockSignals(False)
        self.focus_palette()
        dialog.show()
        dialog.raise_()
        if self.native:
            macos.raise_color_panel()

    def _color_picked(self, color):
        if color.isValid():
            self._picked_color = QColor(color.red(), color.green(), color.blue()).name()
            self._color_timer.start()             # restyling on every tiny mouse movement would lag

    def _apply_picked_color(self):
        if self._picked_color and self._picked_color != self.store["bg_color"]:
            self.set_setting("bg_color", self._picked_color)

    def clear_recent(self):
        self.store.clear_recent()
        self.index.usage = self.store["usage"]
        self.window.panel.refresh_recent()

    # ------------------------------------------------------------------ GIF display
    def media_path(self):
        name = self.store["media_file"]
        path = self.store.folder / name if name else None
        return path if path is not None and path.exists() else None

    def set_media(self, on):
        if on and self.media_path() is None:
            self.choose_media()
            return
        self.store["media_on"] = bool(on)
        self.window.panel.refresh_media()

    def choose_media(self, _checked=False):
        QTimer.singleShot(0, self._pick_media)       # let the menu close first

    def _pick_media(self):
        self.focus_palette()
        source, _filter = QFileDialog.getOpenFileName(
            self.window, "Choose a GIF or picture", str(Path.home() / "Downloads"),
            "GIFs and pictures (*.gif *.webp *.png *.jpg *.jpeg *.heic)")
        if source:
            self.use_media(Path(source))

    def use_media(self, source):
        """Keep our own copy, so the GIF still plays if the original is moved or deleted."""
        if not QImageReader(str(source)).canRead():
            self.show_toast("Couldn't open that file as a GIF or picture")
            return
        panel = self.window.panel
        folder = self.store.folder
        old = self.media_path()
        dest = folder / f"display{source.suffix.lower()}"
        panel.load_media(None)                       # let go of the file before replacing it
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if source.resolve() != dest.resolve():
                shutil.copyfile(source, dest)
            if old is not None and old != dest:
                old.unlink(missing_ok=True)
        except OSError:
            panel.load_media(old)
            self.show_toast("Couldn't save a copy of that file")
            return
        self.store.settings["media_file"] = dest.name
        self.store["media_on"] = True
        panel.load_media(dest)

    def forget_drawings(self):
        self.engine.forget_drawings()
        self.show_toast("Forgot your handwriting samples")

    def quit(self):
        self.hotkeys.clear()
        self.app.quit()


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    smoke_test = "--smoke-test" in argv
    QApplication.setApplicationName("SymbolPad")
    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(QPixmap.fromImage(app_icon(512))))     # the Dock icon, when it's shown there
    if macos.AVAILABLE and app.platformName() == "cocoa":
        macos.show_in_dock(False)       # start as a menu-bar app; start() adds the Dock icon if you chose it
        macos.keep_responsive()
    ctl = Controller(app)
    ctl.start()

    # Let Ctrl+C in a terminal (or PyCharm's Stop button) close the app cleanly.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start(250)

    if smoke_test:
        QTimer.singleShot(5000, lambda: (_report(ctl), app.quit()))
    return app.exec()


def _report(ctl):
    """Printed by `python main.py --smoke-test` to check the app starts correctly."""
    w = ctl.window
    print("platform:", ctl.app.platformName())
    print("window:", w.geometry().getRect(), "visible:", w.isVisible(), "expanded:", w.expanded)
    print("search results shown:", len(w.panel.grid.chars()), "| recognizer ready:", ctl.engine.is_ready)
    print("open shortcut:", macos.shortcut_label(ctl.hotkeys.spec("open")) or "none",
          "| close shortcut:", macos.shortcut_label(ctl.hotkeys.spec("close")) or "same as open",
          "| menu bar icon:", bool(ctl.tray and ctl.tray.isVisible()), "| Dock icon:", macos.is_in_dock())
    print("look:", ctl.store["look"], "| glass:", ctl.glass_kind or "none", "| size:", w.panel_size())
    print("typing allowed:", macos.can_type() if ctl.native else "n/a")
    if ctl.native:
        import AppKit
        import objc
        nswin = objc.objc_object(c_void_p=int(w.winId())).window()
        print("activation policy:", AppKit.NSApplication.sharedApplication().activationPolicy(),
              "| level:", nswin.level(), "| all spaces:", bool(nswin.collectionBehavior() & 1),
              "| hides when inactive:", nswin.hidesOnDeactivate())
        target = ctl.tracker.target()
        print("would type into:", target.localizedName() if target else None)
