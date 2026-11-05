"""The palette window: a floating box or side panel that shrinks to a bubble."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QActionGroup, QGuiApplication, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
                               QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from . import macos
from .symbols import code_of, display_text
from .widgets import Bubble, DrawPad, InfoBar, SymbolGrid

PANEL_W, PANEL_H = 384, 620
BUBBLE = 56
TAB_W, TAB_H = 30, 86
SNAP = 36            # cursor this close to a screen edge docks the palette there
MARGIN = 8


class Header(QWidget):
    """Title row.  Drag it to move the palette; double-click to dock/undock."""

    def __init__(self, window):
        super().__init__()
        self.window_ = window

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.window_.begin_drag(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        self.window_.drag_to(e.globalPosition().toPoint())

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.window_.end_drag(e.globalPosition().toPoint())

    def mouseDoubleClickEvent(self, _e):
        self.window_.toggle_dock()


class Panel(QWidget):
    def __init__(self, ctl, window):
        super().__init__(window)
        self.ctl, self.window_ = ctl, window
        self.index, self.store = ctl.index, ctl.store
        self.hovering = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(8)
        root.addWidget(self._build_header())
        root.addWidget(self._build_banner())
        root.addWidget(self._build_segments())
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_search_page())
        self.pages.addWidget(self._build_draw_page())
        root.addWidget(self.pages, 1)

        recent_row = QHBoxLayout()
        recent_row.setSpacing(6)
        label = QLabel("Recent")
        label.setObjectName("subtle")
        self.recent = SymbolGrid(self.index, cell=34, font_px=19, single_row=True)
        recent_row.addWidget(label)
        recent_row.addWidget(self.recent, 1)
        root.addLayout(recent_row)
        self.info = InfoBar(self.index, self.store)
        root.addWidget(self.info)

        for grid in (self.grid, self.matches, self.recent):
            grid.hovered.connect(self._hover)
            grid.menu_requested.connect(self._symbol_menu)
            grid.typed.connect(self._typed_in_grid)
        self.grid.picked.connect(self.ctl.insert)
        self.recent.picked.connect(self.ctl.insert)
        self.matches.picked.connect(self._pick_match)
        self.grid.current.connect(self._show_unless_hovering)
        self.matches.current.connect(self._show_unless_hovering)
        self.info.favorite_clicked.connect(self.ctl.toggle_favorite)
        self.info.copy_clicked.connect(self.ctl.copy)

    # ------------------------------------------------------------------ building
    def _header_button(self, text, tip):
        b = QToolButton()
        b.setObjectName("header")
        b.setText(text)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        return b

    def _build_header(self):
        header = Header(self.window_)
        row = QHBoxLayout(header)
        row.setContentsMargins(4, 0, 0, 0)
        row.setSpacing(0)
        title = QLabel("Ω  SymbolPad")
        title.setObjectName("title")
        row.addWidget(title)
        row.addStretch(1)
        self.dock_btn = self._header_button("◨", "")
        self.settings_btn = self._header_button("⚙", "Settings")
        shrink = self._header_button("–", "Shrink to a bubble")
        close = self._header_button("✕", "Hide; bring it back with your shortcut or the Ω in the menu bar")
        for b in (self.dock_btn, self.settings_btn, shrink, close):
            row.addWidget(b)
        self.dock_btn.clicked.connect(self.window_.toggle_dock)
        self.settings_btn.clicked.connect(self._open_settings)
        shrink.clicked.connect(self.window_.collapse)
        close.clicked.connect(self.ctl.hide_palette)
        return header

    def _build_banner(self):
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        row = QHBoxLayout(self.banner)
        row.setContentsMargins(10, 6, 6, 6)
        row.setSpacing(6)
        msg = QLabel("To type symbols straight into Word, allow it once in System Settings.")
        msg.setObjectName("hint")
        msg.setWordWrap(True)
        allow = QPushButton("Allow…")
        allow.setObjectName("link")
        allow.clicked.connect(self.ctl.ask_for_permission)
        later = QPushButton("✕")
        later.setObjectName("small")
        later.setFixedWidth(28)
        later.clicked.connect(self.banner.hide)
        row.addWidget(msg, 1)
        row.addWidget(allow)
        row.addWidget(later)
        self.banner.hide()
        return self.banner

    def _build_segments(self):
        seg = QWidget()
        seg.setObjectName("segments")
        row = QHBoxLayout(seg)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(3)
        self.search_tab = QPushButton("⌕  Search")
        self.draw_tab = QPushButton("✎  Draw")
        group = QButtonGroup(self)
        for b, page in ((self.search_tab, "search"), (self.draw_tab, "draw")):
            b.setObjectName("segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, p=page: self.show_page(p))
            group.addButton(b)
            row.addWidget(b)
        self.search_tab.setToolTip("Search by name, LaTeX (\\alpha) or code (U+03B1)   ⌘F")
        self.draw_tab.setToolTip("Draw the symbol and pick it from the matches   ⌘D")
        return seg

    def _build_search_page(self):
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search: alpha, integral, arrow, \\leq, U+2192")
        self.search.setClearButtonEnabled(True)
        self.search.installEventFilter(self)
        self._search_timer = QTimer(self, singleShot=True, interval=70, timeout=self.refresh_results)
        self.search.textChanged.connect(lambda _t: self._search_timer.start())
        row = QHBoxLayout()
        self.category_btn = QToolButton()
        self.category_btn.setObjectName("category")
        self.category_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.category_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.category_btn.setMenu(self._category_menu())
        self.count = QLabel()
        self.count.setObjectName("subtle")
        self.count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.count.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.category_btn)
        row.addWidget(self.count, 1)
        self.grid = SymbolGrid(self.index)
        col.addWidget(self.search)
        col.addLayout(row)
        col.addWidget(self.grid, 1)
        return page

    def _build_draw_page(self):
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)
        self.pad = DrawPad()
        self._draw_timer = QTimer(self, singleShot=True, interval=80, timeout=self.refresh_matches)
        self.pad.changed.connect(self._draw_timer.start)
        row = QHBoxLayout()
        self.undo_btn = QPushButton("↶  Undo")
        self.clear_btn = QPushButton("Clear")
        for b in (self.undo_btn, self.clear_btn):
            b.setObjectName("small")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_btn.clicked.connect(self.pad.undo)
        self.clear_btn.clicked.connect(self.pad.clear)
        self.draw_hint = QLabel()
        self.draw_hint.setObjectName("hint")
        self.draw_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.draw_hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.undo_btn)
        row.addWidget(self.clear_btn)
        row.addWidget(self.draw_hint, 1)
        self.matches = SymbolGrid(self.index, cell=44, font_px=25)
        col.addWidget(self.pad, 5)
        col.addLayout(row)
        col.addWidget(self.matches, 4)
        return page

    def _category_menu(self):
        menu = QMenu(self)
        entries = [("favorites", "★  Favorites"), ("recent", "◷  Recently used"), None]
        entries += [(key, f"{icon}   {title}") for key, title, icon, _chars in self.index.categories]
        for entry in entries:
            if entry is None:
                menu.addSeparator()
                continue
            key, label = entry
            action = menu.addAction(label)
            action.triggered.connect(lambda _=False, k=key: self.set_category(k))
        return menu

    # ------------------------------------------------------------------ theme
    def set_theme(self, theme):
        for grid in (self.grid, self.matches, self.recent):
            grid.set_theme(theme)
        self.pad.theme = theme
        self.pad.update()

    def update_dock_button(self, dock):
        if dock == "float":
            self.dock_btn.setText("◨")
            self.dock_btn.setToolTip("Dock to the side of the screen")
        else:
            self.dock_btn.setText("❐")
            self.dock_btn.setToolTip("Float as a box you can put anywhere")

    # ------------------------------------------------------------------ content
    def refresh_all(self):
        self.show_page(self.store["page"], focus=False)
        self.refresh_results()
        self.refresh_recent()
        self.refresh_matches()

    def _category_title(self, key):
        if key == "favorites":
            return "★  Favorites"
        if key == "recent":
            return "◷  Recently used"
        for k, title, icon, _chars in self.index.categories:
            if k == key:
                return f"{icon}  {title}"
        return "Symbols"

    def _category_chars(self, key):
        if key in ("favorites", "recent"):
            return list(self.store[key])
        chars = self.index.category_chars(key)
        return chars or self.index.category_chars("math")

    def set_category(self, key):
        self.store["category"] = key
        if self.search.text():
            self.search.clear()          # textChanged refreshes the results
        else:
            self.refresh_results()
        self.show_page("search")

    def refresh_results(self):
        query = self.search.text()
        key = self.store["category"]
        self.category_btn.setText(self._category_title(key) + "  ▾")
        if query.strip():
            chars = [s.char for s in self.index.search(query)]
            n = len(chars)
            self.count.setText(f"{n} result{'s' if n != 1 else ''}" if n else "No matches. Try other words, or Draw it")
        else:
            chars = self._category_chars(key)
            if chars:
                self.count.setText(f"{len(chars)} symbol{'s' if len(chars) != 1 else ''}")
            elif key == "favorites":
                self.count.setText("Right-click a symbol to add it")
            else:
                self.count.setText("Nothing here yet")
        self.grid.set_chars(chars)
        if self.hovering is None:
            self.info.show_char(chars[0] if chars else None)

    def refresh_recent(self):
        self.recent.set_chars(self.store["recent"][:24])
        self.recent.clearSelection()
        if self.store["category"] in ("recent", "favorites") and not self.search.text():
            self.refresh_results()

    def refresh_matches(self):
        has_ink = bool(self.pad.strokes)
        self.undo_btn.setEnabled(has_ink)
        self.clear_btn.setEnabled(has_ink)
        if not self.ctl.engine.is_ready:
            self.draw_hint.setText("Getting ready… (first launch only)")
            self.matches.set_chars([])
            return
        if not has_ink:
            self.draw_hint.setText("Matches appear below")
            self.matches.set_chars([])
            return
        chars = self.ctl.engine.rank(self.pad.strokes, self.pad.pad_size())
        self.matches.set_chars(chars)
        self.draw_hint.setText("Click the right one to insert it" if chars else "No idea yet, keep drawing")
        if self.hovering is None:
            self.info.show_char(chars[0] if chars else None)

    def _pick_match(self, ch):
        strokes = [list(s) for s in self.pad.strokes]
        self.ctl.insert(ch, strokes=strokes, pad_size=self.pad.pad_size())
        self.pad.clear()

    def insert_recent(self, i):
        recent = self.store["recent"]
        if i < len(recent):
            self.ctl.insert(recent[i])

    def on_favorites_changed(self, ch):
        if self.info.char == ch:
            self.info.show_char(ch)
        if self.store["category"] == "favorites" and not self.search.text():
            self.refresh_results()

    def show_permission_banner(self):
        self.banner.show()

    # ------------------------------------------------------------------ pages & keys
    def show_page(self, page, focus=True):
        page = "draw" if page == "draw" else "search"
        self.store.settings["page"] = page
        self.pages.setCurrentIndex(1 if page == "draw" else 0)
        self.search_tab.setChecked(page == "search")
        self.draw_tab.setChecked(page == "draw")
        if page == "draw":
            self.refresh_matches()
            if focus:
                self.pad.setFocus()
        elif focus:
            self.search.setFocus()
            self.search.selectAll()

    def focus_search(self):
        self.show_page("search")

    def undo_stroke(self):
        if self.pages.currentIndex() == 1:
            self.pad.undo()

    def escape(self):
        if self.pages.currentIndex() == 0 and self.search.text():
            self.search.clear()
        elif self.pages.currentIndex() == 1 and self.pad.strokes:
            self.pad.clear()
        else:
            self.ctl.return_focus()

    def eventFilter(self, obj, e):
        if obj is self.search and e.type() == QEvent.Type.KeyPress:
            key = e.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                ch = self.grid.current_char()
                if ch:
                    if e.modifiers() & Qt.KeyboardModifier.ControlModifier:     # ⌘Enter = copy only
                        self.ctl.copy(ch)
                    else:
                        self.ctl.insert(ch)
                return True
            if key == Qt.Key.Key_Down and self.grid.chars():
                self.grid.setFocus()
                return True
        return super().eventFilter(obj, e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.escape()
            return
        super().keyPressEvent(e)

    def _typed_in_grid(self, text):
        """Typing while browsing the grid keeps refining the search."""
        self.show_page("search", focus=False)
        self.search.setFocus()
        self.search.end(False)
        self.search.insert(text)

    # ------------------------------------------------------------------ hover & menus
    def _hover(self, ch):
        self.hovering = ch or None
        if ch:
            self.info.show_char(ch)
        else:
            grid = self.matches if self.pages.currentIndex() == 1 else self.grid
            self.info.show_char(grid.current_char())

    def _show_unless_hovering(self, ch):
        if self.hovering is None:
            self.info.show_char(ch)

    def _symbol_menu(self, ch, global_pos):
        sym = self.index.get(ch)
        menu = QMenu(self)
        actions = [(f"Insert  {display_text(ch)}", lambda: self.ctl.insert(ch)),
                   ("Copy", lambda: self.ctl.copy(ch))]
        if sym is not None and sym.latex:
            actions.append((f"Copy LaTeX  \\{sym.latex[0]}", lambda: self.ctl.copy_text("\\" + sym.latex[0])))
        actions.append((f"Copy code  {code_of(ch)}", lambda: self.ctl.copy_text(code_of(ch))))
        for label, fn in actions:
            menu.addAction(label).triggered.connect(fn)
        menu.addSeparator()
        fav = "Remove from Favorites" if self.store.is_favorite(ch) else "Add to Favorites"
        menu.addAction(fav).triggered.connect(lambda: self.ctl.toggle_favorite(ch))
        menu.exec(global_pos)

    def _open_settings(self):
        menu = QMenu(self)
        ctl, store = self.ctl, self.store

        def radio(sub, options, current, apply):
            group = QActionGroup(sub)
            for value, label in options:
                a = sub.addAction(label)
                a.setCheckable(True)
                a.setChecked(value == current)
                group.addAction(a)
                a.triggered.connect(lambda _=False, v=value: apply(v))

        radio(menu.addMenu("When I pick a symbol"),
              [("type", "Type it into the app I was using"),
               ("paste", "Paste it in (uses the clipboard briefly)"),
               ("copy", "Only copy it")],
              store["insert_method"], lambda v: ctl.set_setting("insert_method", v))
        collapse = menu.addAction("Shrink to a bubble after inserting")
        collapse.setCheckable(True)
        collapse.setChecked(store["collapse_after_insert"])
        collapse.toggled.connect(lambda on: ctl.set_setting("collapse_after_insert", on))
        keys = [(k, label) for k, (label, _code, _mods) in macos.HOTKEYS.items()] + [("off", "Off")]
        radio(menu.addMenu(f"Shortcut to open SymbolPad:  {ctl.hotkey.label or 'off'}"), keys,
              store["hotkey"], ctl.set_hotkey)
        radio(menu.addMenu("Appearance"), [("system", "Match macOS"), ("light", "Light"), ("dark", "Dark")],
              store["theme"], lambda v: ctl.set_setting("theme", v))
        menu.addSeparator()
        if ctl.native and macos.can_type():
            ok = menu.addAction("✓  Typing into other apps is allowed")
            ok.setEnabled(False)
        else:
            menu.addAction("Allow typing into other apps…").triggered.connect(ctl.ask_for_permission)
        menu.addSeparator()
        menu.addAction("Clear recent symbols").triggered.connect(ctl.clear_recent)
        n = sum(len(v) for v in store.drawings.values())
        forget = menu.addAction(f"Forget my handwriting ({n} drawing{'s' if n != 1 else ''})")
        forget.setEnabled(n > 0)
        forget.triggered.connect(ctl.forget_drawings)
        menu.addSeparator()
        menu.addAction("Quit SymbolPad").triggered.connect(ctl.quit)
        menu.exec(self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomLeft()))


class PaletteWindow(QWidget):
    def __init__(self, ctl):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setWindowTitle("SymbolPad")
        self.ctl, self.store = ctl, ctl.store
        # No layout on purpose: a layout would stop the window shrinking to the bubble.
        self.bubble = Bubble(self)
        self.panel = Panel(ctl, self)
        self._drag = None
        self._shortcuts()

    def resizeEvent(self, e):
        self.bubble.setGeometry(self.rect())
        self.panel.setGeometry(self.rect())
        super().resizeEvent(e)

    def _show_part(self, expanded):
        self.panel.setVisible(expanded)
        self.bubble.setVisible(not expanded)

    @property
    def expanded(self):
        return bool(self.store["expanded"])

    def set_theme(self, theme):
        self.bubble.theme = theme
        self.panel.set_theme(theme)
        self.update()

    def _shortcuts(self):
        def add(seq, fn):
            QShortcut(QKeySequence(seq), self).activated.connect(fn)

        add("Ctrl+F", self.panel.focus_search)          # Ctrl means ⌘ on macOS
        add("Ctrl+D", lambda: self.panel.show_page("draw"))
        add("Ctrl+Z", self.panel.undo_stroke)
        add("Ctrl+W", self.ctl.hide_palette)
        add("Ctrl+Q", self.ctl.quit)
        for i in range(1, 10):
            add(f"Ctrl+{i}", lambda i=i: self.panel.insert_recent(i - 1))

    # ------------------------------------------------------------------ geometry
    def _area(self, point=None):
        screen = QGuiApplication.screenAt(point if point is not None else self.geometry().center())
        return (screen or QGuiApplication.primaryScreen()).availableGeometry()

    @staticmethod
    def _clamp(rect, area):
        x = max(area.left(), min(rect.x(), area.right() - rect.width() + 1))
        y = max(area.top(), min(rect.y(), area.bottom() - rect.height() + 1))
        return QRect(x, y, rect.width(), rect.height())

    def apply_layout(self):
        dock = self.store["dock"]
        area = self._area()
        self._show_part(self.expanded)
        if self.expanded:
            if dock == "float":
                x, y = self.store["panel_pos"] or (area.right() - PANEL_W - 40, area.top() + 50)
                rect = QRect(x, y, PANEL_W, min(PANEL_H, area.height() - 2 * MARGIN))
            else:
                x = area.left() + MARGIN if dock == "left" else area.right() - PANEL_W - MARGIN + 1
                rect = QRect(x, area.top() + MARGIN, PANEL_W, area.height() - 2 * MARGIN)
        else:
            self.bubble.side = dock
            if dock == "float":
                x, y = self.store["bubble_pos"] or (area.right() - BUBBLE - 24, area.top() + 80)
                rect = QRect(x, y, BUBBLE, BUBBLE)
            else:
                cy = self.store["dock_y"] or area.center().y()
                x = area.left() if dock == "left" else area.right() - TAB_W + 1
                rect = QRect(x, cy - TAB_H // 2, TAB_W, TAB_H)
        self.setGeometry(self._clamp(rect, area))
        self.panel.update_dock_button(dock)
        self.update()

    def expand(self):
        if self.expanded:
            return
        if self.store["dock"] == "float":
            g, area = self.geometry(), self._area()
            x = g.right() - PANEL_W + 1 if g.center().x() > area.center().x() else g.left()
            self.store.settings["panel_pos"] = [x, g.top()]
        self.store["expanded"] = True
        self.apply_layout()
        self.ctl.focus_palette()

    def collapse(self, return_focus=True):
        if not self.expanded:
            return
        if self.store["dock"] == "float":
            g, area = self.geometry(), self._area()
            x = g.right() - BUBBLE + 1 if g.center().x() > area.center().x() else g.left()
            self.store.settings["bubble_pos"] = [x, g.top()]
        self.store["expanded"] = False
        self.apply_layout()
        if return_focus:
            self.ctl.return_focus()

    def toggle_dock(self):
        if self.store["dock"] == "float":
            area = self._area()
            side = "right" if self.geometry().center().x() >= area.center().x() else "left"
            self.dock_to(side, self.geometry().center().y())
        else:
            self.float_here()

    def dock_to(self, side, y=None):
        self.store.settings["dock"] = side
        self.store.settings["dock_y"] = y if y is not None else self.store["dock_y"]
        self.store.save()
        self.apply_layout()

    def float_here(self):
        g, area = self.geometry(), self._area()
        inward = -60 if self.store["dock"] == "right" else 60
        if self.expanded:
            self.store.settings["panel_pos"] = [g.x() + inward, area.top() + 50]
        else:
            self.store.settings["bubble_pos"] = [g.x() + inward - BUBBLE // 2, g.y()]
        self.store["dock"] = "float"
        self.apply_layout()

    # ------------------------------------------------------------------ dragging
    def begin_drag(self, gpos):
        self._drag = {"start": gpos, "offset": gpos - self.pos(), "moved": False}

    def drag_to(self, gpos):
        d = self._drag
        if d is None:
            return
        if not d["moved"]:
            if (gpos - d["start"]).manhattanLength() < 4:
                return
            d["moved"] = True
            if self.store["dock"] != "float":           # pulling it off the edge undocks it
                self.store.settings["dock"] = "float"
                self.bubble.side = "float"
                self.panel.update_dock_button("float")
                if self.expanded:
                    size = (PANEL_W, min(PANEL_H, self._area(gpos).height() - 2 * MARGIN))
                    d["offset"] = QPoint(min(d["offset"].x(), PANEL_W - 60), min(d["offset"].y(), 24))
                else:
                    size = (BUBBLE, BUBBLE)
                    d["offset"] = QPoint(BUBBLE // 2, BUBBLE // 2)
                self.resize(*size)
                self.update()
        self.move(gpos - d["offset"])

    def end_drag(self, gpos):
        """Finish a drag; returns False if the mouse never really moved (a click)."""
        d, self._drag = self._drag, None
        if d is None or not d["moved"]:
            return False
        area = self._area(gpos)
        if gpos.x() <= area.left() + SNAP:
            self.dock_to("left", gpos.y())
        elif gpos.x() >= area.right() - SNAP:
            self.dock_to("right", gpos.y())
        else:
            self.store.settings["dock"] = "float"
            self.store["panel_pos" if self.expanded else "bubble_pos"] = [self.x(), self.y()]
            self.apply_layout()
        return True

    # ------------------------------------------------------------------ showing
    def summon(self, page="search"):
        if not self.isVisible():
            self.show()
            self.ctl.after_show()
        if not self.expanded:
            self.store["expanded"] = True
            self.apply_layout()
        self.ctl.focus_palette()
        self.panel.show_page(page)

    def paintEvent(self, _e):
        if not self.expanded:
            return
        t = self.ctl.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(t.border, 1))
        p.setBrush(t.bg)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
