"""Puts a chosen symbol into the app you were typing in (Word, Pages, ...)."""

from __future__ import annotations

import time

from PySide6.QtCore import QMimeData, QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from . import macos


class Inserter(QObject):
    finished = Signal(str)          # short message for a toast
    needs_permission = Signal()     # typing is blocked until the user allows it

    def __init__(self, store, tracker):
        super().__init__()
        self.store = store
        self.tracker = tracker

    def copy(self, text):
        QGuiApplication.clipboard().setText(text)

    def insert(self, text):
        method = self.store["insert_method"]
        target = self.tracker.target() if self.tracker else None
        if method == "copy" or target is None:
            self.copy(text)
            self.finished.emit(f"Copied {text} · paste it with ⌘V")
            return
        name = target.localizedName() or "the app"
        if not macos.can_type():
            self.copy(text)
            macos.activate(target)
            self.finished.emit(f"Copied {text} · press ⌘V in {name}")
            self.needs_permission.emit()
            return
        saved = None
        if method == "paste":
            saved = self._snapshot_clipboard()
            self.copy(text)
        macos.activate(target)
        self._when_in_front(target, lambda: self._deliver(text, method, saved, name),
                            lambda: self._give_up(text, name))

    def copy_equation(self, mathml, text):
        """On the clipboard as an equation for Word, and as ordinary characters for everything else."""
        if not macos.set_clipboard({macos.MATHML: mathml, macos.PLAIN_TEXT: text}):
            self.copy(text)

    def insert_equation(self, mathml, text):
        """Paste built-up maths into the app you were typing in.  Word makes a real equation of it."""
        target = self.tracker.target() if self.tracker else None
        if self.store["insert_method"] == "copy" or target is None:
            self.copy_equation(mathml, text)
            self.finished.emit("Copied the equation · paste it with ⌘V")
            return
        name = target.localizedName() or "the app"
        if not macos.can_type():
            self.copy_equation(mathml, text)
            macos.activate(target)
            self.finished.emit(f"Copied the equation · press ⌘V in {name}")
            self.needs_permission.emit()
            return
        saved = macos.clipboard_snapshot()
        self.copy_equation(mathml, text)
        macos.activate(target)

        def paste():
            macos.press_paste()
            QTimer.singleShot(1200, lambda: macos.restore_clipboard(saved))
            self.finished.emit(f"Inserted the equation into {name}")

        def give_up():
            self.finished.emit(f"Copied the equation · click into {name} and press ⌘V")

        self._when_in_front(target, paste, give_up)

    def _when_in_front(self, target, then, give_up):
        pid = target.processIdentifier()
        start = time.monotonic()
        nudged = False

        def check():
            nonlocal nudged
            waited = time.monotonic() - start
            if macos.frontmost_pid() == pid:
                QTimer.singleShot(40, then)        # give its window a moment to take focus
            elif waited > 1.0:
                give_up()                          # never type into the wrong app
            else:
                if waited > 0.35 and not nudged:
                    nudged = True
                    macos.hand_back_focus()
                QTimer.singleShot(15, check)

        check()

    def _give_up(self, text, name):
        self.copy(text)
        self.finished.emit(f"Copied {text} · click into {name} and press ⌘V")

    def _deliver(self, text, method, saved, name):
        if method == "paste":
            macos.press_paste()
            if saved is not None:
                QTimer.singleShot(600, lambda: QGuiApplication.clipboard().setMimeData(saved))
        else:
            macos.type_text(text)
        self.finished.emit(f"Inserted {text} into {name}")

    @staticmethod
    def _snapshot_clipboard():
        current = QGuiApplication.clipboard().mimeData()
        copy = QMimeData()
        if current is not None:
            for fmt in current.formats():
                copy.setData(fmt, current.data(fmt))
        return copy
