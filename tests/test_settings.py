"""Settings, looks, shortcuts and window size (everything here runs without a screen)."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication

from symbolpad import macos, storage, theme
from symbolpad.storage import Store

CONTROL, OPTION, SHIFT, COMMAND = 1 << 18, 1 << 19, 1 << 17, 1 << 20       # NSEvent modifier flags

# Windows need a full QApplication.  Make it now, while the tests are still being
# collected, so the other test files (which only draw glyphs) share it.
_qapp = QApplication.instance() or QApplication([])


class UpgradeTests(unittest.TestCase):
    def test_version_1_settings_are_carried_over(self):
        new = storage.upgrade({"glass": True, "theme": "system", "hotkey": "ctrl+shift+space", "recent": ["π"]})
        self.assertEqual(new["look"], "glass-dark")
        self.assertEqual(new["open_key"], {"code": 49, "mods": 4096 | 512, "label": "⌃⇧Space"})
        self.assertEqual(new["recent"], ["π"])
        self.assertFalse({"glass", "theme", "hotkey"} & set(new))

    def test_old_looks(self):
        self.assertEqual(storage.upgrade({"glass": True, "theme": "light"})["look"], "glass-light")
        self.assertEqual(storage.upgrade({"glass": False, "theme": "dark"})["look"], "solid-dark")
        self.assertEqual(storage.upgrade({"glass": False})["look"], "solid-system")

    def test_shortcut_that_was_off_stays_off(self):
        self.assertIsNone(storage.upgrade({"hotkey": "off"})["open_key"])

    def test_new_settings_are_left_alone(self):
        saved = {"look": "solid-light", "open_key": None, "panel_size": [500, 700]}
        self.assertEqual(storage.upgrade(saved), saved)

    def test_store_reads_old_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "settings.json").write_text('{"glass": false, "theme": "light", "hotkey": "alt+cmd+s"}')
            store = Store(Path(tmp))
            self.assertEqual(store["look"], "solid-light")
            self.assertEqual(store["open_key"]["label"], "⌥⌘S")
            self.assertIsNone(store["close_key"])
            self.assertEqual(store["show_in"], "menu")

    def test_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            self.assertEqual(store["look"], "glass-dark")
            self.assertEqual(store["open_key"]["label"], "⌃⌥S")
            self.assertIsNone(store["panel_size"])


class ShortcutTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(macos.shortcut_from_key(1, CONTROL | OPTION, "s"),
                         {"code": 1, "mods": 4096 | 2048, "label": "⌃⌥S"})
        self.assertEqual(macos.shortcut_from_key(49, COMMAND | SHIFT, " ")["label"], "⇧⌘Space")
        self.assertEqual(macos.shortcut_from_key(122, 0)["label"], "F1")
        self.assertEqual(macos.shortcut_from_key(13, COMMAND)["label"], "⌘W")          # no character given
        self.assertEqual(macos.shortcut_from_key(41, OPTION, "ö")["label"], "⌥Ö")       # other keyboard layouts

    def test_plain_keys_are_refused(self):
        self.assertIsNone(macos.shortcut_from_key(1, 0, "s"))
        self.assertIsNone(macos.shortcut_from_key(1, SHIFT, "S"))
        self.assertIsNone(macos.shortcut_from_key(macos.ESCAPE_KEY, 0))

    def test_comparing(self):
        a = {"code": 1, "mods": 6144, "label": "⌃⌥S"}
        self.assertTrue(macos.same_shortcut(a, {"code": 1, "mods": 6144, "label": "anything"}))
        self.assertFalse(macos.same_shortcut(a, {"code": 2, "mods": 6144}))
        self.assertFalse(macos.same_shortcut(a, None))
        self.assertFalse(macos.same_shortcut(None, None))
        self.assertTrue(macos.valid_shortcut(a))
        self.assertFalse(macos.valid_shortcut({"code": "S"}))
        self.assertFalse(macos.valid_shortcut(None))


class LookTests(unittest.TestCase):
    def test_every_look_builds(self):
        for look in [entry[0] for entry in theme.LOOKS if entry]:
            for color in ("", "#2f6df6", "#f3ead8"):
                t = theme.build(look, color, 50, system_dark=False)
                self.assertEqual(bool(t.glass), look.startswith("glass"), look)
                self.assertGreater(t.panel.alpha(), 0, look)        # never fully see-through: clicks must land

    def test_glass_is_see_through_and_solid_is_not(self):
        self.assertLess(theme.build("glass-dark").panel.alpha(), 40)
        self.assertEqual(theme.build("glass-clear").glass, "clear")
        self.assertEqual(theme.build("solid-dark").panel.alpha(), 255)
        self.assertFalse(theme.build("glass-light").glass_dark)

    def test_text_contrasts_with_your_colour(self):
        self.assertTrue(theme.build("solid-light", "#1b2540").dark)       # dark colour: light text
        self.assertFalse(theme.build("solid-dark", "#f4c430").dark)       # bright colour: dark text
        self.assertFalse(theme.build("glass-dark", "#f3ead8", 100).dark)
        self.assertTrue(theme.build("glass-dark", "#f3ead8", 25).dark)    # a light tint leaves the glass dark

    def test_colour_strength(self):
        weak, strong = theme.build("glass-dark", "#2f6df6", 25), theme.build("glass-dark", "#2f6df6", 100)
        self.assertLess(weak.panel.alpha(), strong.panel.alpha())
        self.assertEqual(strong.panel.alpha(), 255)
        self.assertEqual(theme.build("solid-light", "#2f6df6", 25).panel.name(), "#2f6df6")

    def test_bad_values_fall_back(self):
        self.assertEqual(theme.build("nonsense").glass, "")
        self.assertEqual(theme.build("glass-dark", "not a colour"), theme.build("glass-dark"))
        self.assertIsNone(theme.parse_color(""))

    def test_follows_macos(self):
        self.assertTrue(theme.build("solid-system", system_dark=True).dark)
        self.assertFalse(theme.build("solid-system", system_dark=False).dark)


class WindowTests(unittest.TestCase):
    """The real window, on Qt's invisible "offscreen" screen."""

    @classmethod
    def setUpClass(cls):
        from symbolpad import app as symbolpad_app
        cls.qapp = QApplication.instance()
        if not isinstance(cls.qapp, QApplication):
            raise unittest.SkipTest("another test already started Qt without window support")
        cls.tmp = tempfile.TemporaryDirectory()

        class TemporaryStore(Store):                          # never touch your real settings
            def __init__(self):
                super().__init__(Path(cls.tmp.name))

        original = symbolpad_app.Store
        symbolpad_app.Store = TemporaryStore
        try:
            cls.ctl = symbolpad_app.Controller(cls.qapp)
        finally:
            symbolpad_app.Store = original
        cls.ctl.start()
        cls.window = cls.ctl.window

    @classmethod
    def tearDownClass(cls):
        cls.window.hide()
        cls.tmp.cleanup()

    def setUp(self):
        w = self.window
        w.store.settings.update(dock="float", expanded=True, panel_size=None, panel_pos=[100, 60])
        w.apply_layout()

    def drag(self, edges, dx, dy):
        w = self.window
        start = QPoint(500, 500)
        w.begin_resize(edges, start)
        w.resize_to(start + QPoint(dx, dy))
        w.end_resize()

    def test_starts_at_the_default_size(self):
        self.assertEqual(self.window.size().toTuple(), (384, 620))

    def test_resizing_from_a_corner(self):
        self.drag("br", 60, 40)
        self.assertEqual(self.window.geometry(), QRect(100, 60, 444, 660))
        self.assertEqual(self.window.store["panel_size"], [444, 660])

    def test_resizing_from_the_top_left_keeps_the_other_corner_still(self):
        before = self.window.geometry()
        self.drag("tl", -30, -20)
        after = self.window.geometry()
        self.assertEqual((after.right(), after.bottom()), (before.right(), before.bottom()))
        self.assertEqual(after.size().toTuple(), (414, 640))

    def test_size_survives_the_bubble(self):
        self.drag("br", 80, 50)
        size, corner = self.window.size(), self.window.pos()
        self.window.collapse(return_focus=False)
        self.assertEqual(self.window.size().toTuple(), (56, 56))
        self.window.expand()
        self.assertEqual(self.window.size(), size)
        self.assertEqual(self.window.pos(), corner)

    def test_size_is_remembered_next_time(self):
        self.drag("r", 50, 0)
        self.assertEqual(Store(Path(self.tmp.name))["panel_size"], [434, 620])

    def test_cannot_shrink_to_nothing(self):
        self.drag("br", -2000, -2000)
        smallest = self.window.min_size()
        self.assertEqual(self.window.size(), smallest)
        self.assertGreaterEqual(smallest.width(), 300)

    def test_cannot_grow_past_the_screen(self):
        self.drag("br", 5000, 5000)
        area = self.window.screen().availableGeometry()
        self.assertTrue(area.contains(self.window.geometry()))

    def test_docked_keeps_your_width_and_fills_the_height(self):
        self.drag("r", 46, 0)
        self.window.dock_to("right")
        area = self.window.screen().availableGeometry()
        self.assertEqual(self.window.width(), 430)
        self.assertEqual(self.window.height(), area.height() - 16)
        visible = [edges for edges, grip in self.window.grips.items() if grip.isVisible()]
        self.assertEqual(visible, ["l"])                      # only the free edge can be dragged

    def test_reset_size(self):
        self.drag("br", 90, 90)
        self.window.reset_size()
        self.assertEqual(self.window.size().toTuple(), (384, 620))
        self.assertIsNone(self.window.store["panel_size"])

    def test_no_grips_on_the_bubble(self):
        self.window.collapse(return_focus=False)
        self.assertFalse(any(grip.isVisible() for grip in self.window.grips.values()))

    def test_grips_leave_the_contents_clickable(self):
        w = self.window
        for name in ("search", "close_btn", "settings_btn", "info"):
            widget = getattr(w.panel, name)
            centre = widget.mapTo(w, widget.rect().center())
            self.assertIs(w.childAt(centre) is not None and not isinstance(w.childAt(centre), type(w.grips["l"])),
                          True, name)
        self.assertIs(w.childAt(QPoint(2, 300)), w.grips["l"])
        self.assertIs(w.childAt(QPoint(w.width() - 3, w.height() - 3)), w.grips["br"])

    def test_changing_shortcuts(self):
        ctl = self.ctl
        new = macos.shortcut_from_key(49, CONTROL | SHIFT, " ")
        ok, message = ctl.set_shortcut("open", new)
        self.assertTrue(ok)
        self.assertIn("⌃⇧Space", message)
        self.assertEqual(ctl.open_label, "⌃⇧Space")
        self.assertIn("⌃⇧Space", self.window.panel.close_btn.toolTip())
        self.assertFalse(ctl.has_close_key())

        ok, message = ctl.set_shortcut("close", macos.shortcut_from_key(13, COMMAND | OPTION, "w"))
        self.assertTrue(ctl.has_close_key())
        self.assertIn("⌥⌘W closes", message)

        ctl.set_shortcut("close", dict(new))                  # same keys as open = one shortcut for both
        self.assertIsNone(ctl.store["close_key"])
        ctl.set_shortcut("open", None)
        self.assertEqual(ctl.open_label, "")

    def test_closing_hides_or_shrinks(self):
        ctl, w = self.ctl, self.window
        ctl.store.settings["close_action"] = "bubble"
        ctl.close_pressed()
        self.assertTrue(w.isVisible())
        self.assertFalse(w.expanded)
        w.summon()
        ctl.store.settings["close_action"] = "hide"
        ctl.close_pressed()
        self.assertFalse(w.isVisible())
        w.summon()
        self.assertTrue(w.isVisible() and w.expanded)

    def test_look_and_colour_settings_restyle_the_palette(self):
        ctl = self.ctl
        ctl.set_setting("look", "solid-light")
        self.assertEqual(ctl.theme.glass, "")
        ctl.set_setting("bg_color", "#1b2540")
        self.assertEqual(ctl.theme.panel.name(), "#1b2540")
        self.assertTrue(ctl.theme.dark)
        ctl.set_setting("bg_color", "")
        ctl.set_setting("look", "glass-dark")
        self.assertEqual(ctl.theme.glass, "regular")

    def test_settings_menu_builds(self):
        from PySide6.QtWidgets import QMenu

        class FakeMenu(QMenu):                                # don't actually pop the menu up
            made = []

            def __init__(self, *args):
                super().__init__(*args)
                FakeMenu.made.append(self)

            def exec(self, *_args):
                return None

        from symbolpad import window as window_module
        real = window_module.QMenu
        window_module.QMenu = FakeMenu
        try:
            self.window.panel._open_settings()
        finally:
            window_module.QMenu = real
        titles = [a.text() for a in FakeMenu.made[0].actions()]
        for wanted in ("Look", "Background colour", "Show the τ icon in", "Reset window size"):
            self.assertIn(wanted, titles)
        self.assertTrue(any(t.startswith("Shortcuts…") for t in titles))


if __name__ == "__main__":
    unittest.main()
