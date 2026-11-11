"""The little window where you choose the shortcuts that open and close SymbolPad."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QButtonGroup, QDialog, QGridLayout, QHBoxLayout, QLabel, QLayout, QPushButton,
                               QRadioButton)

from . import macos

HOW = "Click a box, then press the keys you want, for example ⌃⌥S or ⌘⇧Space."
RECORDING = "Hold ⌘, ⌃ or ⌥ and press a key.  Esc cancels, ⌫ removes the shortcut."
NEEDS_MODIFIER = "That key needs ⌘, ⌃ or ⌥ held with it (the F keys work on their own)."
EMPTY = {"open": "None", "close": "Same as open"}


class ShortcutDialog(QDialog):
    def __init__(self, ctl):
        super().__init__(ctl.window, Qt.WindowType.Tool | Qt.WindowType.WindowTitleHint
                         | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setWindowTitle("SymbolPad shortcuts")
        self.ctl, self.store = ctl, ctl.store
        self.recording = None                              # "open" or "close" while waiting for keys
        self.capture = macos.KeyCapture(self._key_pressed)

        grid = QGridLayout(self)
        grid.setContentsMargins(18, 16, 18, 14)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        self.keys = {}
        for row, (which, title) in enumerate((("open", "Open SymbolPad"), ("close", "Close SymbolPad"))):
            key = QPushButton()
            key.setObjectName("key")
            key.setCheckable(True)
            key.setCursor(Qt.CursorShape.PointingHandCursor)
            key.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            key.clicked.connect(lambda on, w=which: self._start(w) if on else self._stop(HOW))
            clear = QPushButton("✕")
            clear.setObjectName("small")
            clear.setFixedWidth(30)
            clear.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            clear.setToolTip("Remove this shortcut" if which == "open" else "Use the open shortcut to close as well")
            clear.clicked.connect(lambda _=False, w=which: self._record(w, None))
            grid.addWidget(QLabel(title), row, 0)
            grid.addWidget(key, row, 1)
            grid.addWidget(clear, row, 2)
            self.keys[which] = key

        grid.addWidget(QLabel("Closing"), 2, 0)
        actions = QHBoxLayout()
        actions.setSpacing(14)
        self.actions = QButtonGroup(self)
        for value, label in (("hide", "hides it"), ("bubble", "shrinks it to the bubble")):
            radio = QRadioButton(label)
            radio.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            radio.setChecked(self.store["close_action"] == value)
            radio.toggled.connect(lambda on, v=value: on and self.ctl.set_setting("close_action", v))
            self.actions.addButton(radio)
            actions.addWidget(radio)
        actions.addStretch(1)
        grid.addLayout(actions, 2, 1, 1, 2)

        self.status = QLabel(HOW)
        self.status.setObjectName("hint")
        self.status.setWordWrap(True)
        self.status.setFixedWidth(330)
        self.status.setMinimumHeight(34)
        self.status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        grid.addWidget(self.status, 3, 0, 1, 3)
        done = QPushButton("Done")
        done.setObjectName("link")
        done.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        done.clicked.connect(self.close)
        grid.addWidget(done, 4, 1, 1, 2, Qt.AlignmentFlag.AlignRight)

        QGuiApplication.instance().applicationStateChanged.connect(self._app_state_changed)
        self.refresh()

    # ------------------------------------------------------------------ showing
    def refresh(self):
        for which, key in self.keys.items():
            key.setChecked(self.recording == which)
            if self.recording == which:
                key.setText("Press the keys…")
            else:
                key.setText(macos.shortcut_label(self.store[f"{which}_key"]) or EMPTY[which])

    def show_beside(self, anchor):
        """Open next to the palette (`anchor` is its frame), on whichever side has room."""
        self.adjustSize()
        screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        x = anchor.left() - self.width() - 12
        if x < area.left() + 8:
            x = min(anchor.right() + 12, area.right() - self.width() - 8)
        y = max(area.top() + 8, min(anchor.top() + 40, area.bottom() - self.height() - 40))
        self.move(QPoint(x, y))
        self.show()

    def hideEvent(self, e):
        self._stop()
        super().hideEvent(e)

    def _app_state_changed(self, state):
        if state != Qt.ApplicationState.ApplicationActive:      # you went to another app: stop listening
            self._stop()

    # ------------------------------------------------------------------ recording
    def _start(self, which):
        self.recording = which
        self.ctl.pause_hotkeys(True)        # or pressing the current shortcut would trigger it instead
        if not self.capture.start():
            self._stop("Shortcuts can only be recorded on a Mac.")
            return
        self.status.setText(RECORDING)
        self.refresh()

    def _stop(self, message=None):
        was_recording = self.recording is not None or self.capture.active
        self.recording = None
        self.capture.stop()
        if was_recording:
            self.ctl.pause_hotkeys(False)
        if message is not None:
            self.status.setText(message)
        self.refresh()

    def _key_pressed(self, code, flags, char):
        # Called from inside macOS's event handling; do the real work once that has returned.
        QTimer.singleShot(0, lambda: self.key_pressed(code, flags, char))

    def key_pressed(self, code, flags, char=""):
        which = self.recording
        if which is None:
            return
        spec = macos.shortcut_from_key(code, flags, char)
        if spec is None and code == macos.ESCAPE_KEY:
            self._stop(HOW)
        elif spec is None and code == macos.DELETE_KEY:
            self._record(which, None)
        elif spec is None:
            self.status.setText(NEEDS_MODIFIER)
        else:
            self._record(which, spec)

    def _record(self, which, spec):
        self._stop()
        _ok, message = self.ctl.set_shortcut(which, spec)
        self.status.setText(message)
        self.refresh()
