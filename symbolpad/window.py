"""The palette window: a floating box or side panel that shrinks to a bubble."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QLineF, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QActionGroup, QBrush, QColor, QConicalGradient, QGuiApplication, QIcon, QKeySequence,
                           QPainter, QPen, QPixmap, QRegion, QShortcut)
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
                               QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget, QWidgetAction)

from . import macos, mathexpr, mathview, theme
from .mathview import MathView
from .symbols import code_of, display_text
from .theme import RADIUS
from .widgets import TAB_RADIUS, Bubble, DrawPad, InfoBar, MediaView, SymbolGrid

PANEL_W, PANEL_H = 384, 620      # size of the open palette until you resize it
MIN_W, MIN_H = 300, 400          # ... and the smallest you can make it
BUBBLE = 56
TAB_W, TAB_H = 30, 86
SNAP = 36            # cursor this close to a screen edge docks the palette there
MARGIN = 8
PAD_SIDE, PAD_TOP = 12, 8        # empty space between the palette's border and what's in it
EDGE, CORNER = 6, 24             # how near the border (and its corners) a drag resizes the palette
PAGES = ("search", "draw", "equation")
SHOW_IN = [("menu", "Menu bar"), ("dock", "Dock"), ("both", "Menu bar and Dock")]


def swatch(color):
    """A little round sample of a colour, for menus."""
    pix = QPixmap(28, 28)
    pix.setDevicePixelRatio(2)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(128, 128, 128, 150), 1))
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(1, 1, 12, 12))
    p.end()
    return QIcon(pix)


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
        root.setContentsMargins(PAD_SIDE, PAD_TOP, PAD_SIDE, PAD_SIDE)
        root.setSpacing(8)
        root.addWidget(self._build_header())
        root.addWidget(self._build_banner())
        root.addWidget(self._build_segments())
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_search_page())
        self.pages.addWidget(self._build_draw_page())
        self.pages.addWidget(self._build_equation_page())
        root.addWidget(self.pages, 1)
        self.media = MediaView()
        self.media.hide()
        self.media.menu_requested.connect(self._media_menu)
        root.addWidget(self.media)

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
        title = QLabel("τ  SymbolPad")
        title.setObjectName("title")
        row.addWidget(title)
        row.addStretch(1)
        self.dock_btn = self._header_button("◨", "")
        self.settings_btn = self._header_button("⚙", "Settings")
        shrink = self._header_button("–", "Shrink to a bubble")
        self.close_btn = self._header_button("✕", "Hide")
        for b in (self.dock_btn, self.settings_btn, shrink, self.close_btn):
            row.addWidget(b)
        self.dock_btn.clicked.connect(self.window_.toggle_dock)
        self.settings_btn.clicked.connect(self._open_settings)
        shrink.clicked.connect(lambda: self.window_.collapse())     # (clicked's bool isn't return_focus)
        self.close_btn.clicked.connect(self.ctl.hide_palette)
        return header

    def update_hints(self):
        """Say how to get the palette back, which depends on your shortcut and where the τ icon is."""
        ways = [self.ctl.open_label] if self.ctl.open_label else []
        ways.append({"dock": "the τ in the Dock", "both": "the τ in the menu bar or Dock"}.get(
            self.store["show_in"], "the τ in the menu bar"))
        self.close_btn.setToolTip("Hide; bring it back with " + " or ".join(ways))

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
        self.equation_tab = QPushButton("x²  Equation")
        group = QButtonGroup(self)
        for b, page in ((self.search_tab, "search"), (self.draw_tab, "draw"), (self.equation_tab, "equation")):
            b.setObjectName("segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, p=page: self.show_page(p))
            group.addButton(b)
            row.addWidget(b)
        self.search_tab.setToolTip("Search by name, LaTeX (\\alpha) or code (U+03B1)   ⌘F")
        self.draw_tab.setToolTip("Draw the symbol and pick it from the matches   ⌘D")
        self.equation_tab.setToolTip("Build powers, subscripts, fractions, roots and more   ⌘E")
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

    def _build_equation_page(self):
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)
        self.eq_input = QLineEdit()
        self.eq_input.setObjectName("search")
        self.eq_input.setPlaceholderText("Type it:  6^2   Cl_2   (a+b)/c   sqrt(x)")
        self.eq_input.setClearButtonEnabled(True)
        self.eq_input.installEventFilter(self)
        self.eq_input.textChanged.connect(lambda _t: self.refresh_equation())
        self.eq_view = MathView()
        self.eq_view.hint = "^ raises, _ lowers, / makes a fraction.\nOr start from one of the buttons below."
        tiles = QGridLayout()
        tiles.setSpacing(4)
        self.eq_tiles = []
        for i, (name, picture, _items) in enumerate(mathexpr.GALLERY):
            tile = self._tile(name)
            tile.clicked.connect(lambda _=False, b=tile, n=i: self._open_gallery(b, n))
            tiles.addWidget(tile, i // 6, i % 6)
            self.eq_tiles.append((tile, picture))
        self.eq_recent_btn = self._tile("Equations you've used")
        self.eq_recent_btn.setText("◷")
        self.eq_recent_btn.clicked.connect(self._recent_equations)
        tiles.addWidget(self.eq_recent_btn, 1, 5)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.eq_text_btn = QPushButton()
        self.eq_math_btn = QPushButton("Equation")
        self.eq_copy_btn = QPushButton("Copy")
        for b in (self.eq_text_btn, self.eq_math_btn, self.eq_copy_btn):
            b.setObjectName("small")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eq_text_btn.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.eq_math_btn.setToolTip("Paste it into Word as a real equation")
        self.eq_copy_btn.setToolTip("Copy it: pastes as an equation in Word, as plain characters elsewhere")
        self.eq_text_btn.clicked.connect(lambda: self.insert_equation(as_text=True))
        self.eq_math_btn.clicked.connect(lambda: self.insert_equation(as_text=False))
        self.eq_copy_btn.clicked.connect(lambda: self.ctl.copy_maths(self.eq_input.text()))
        row.addWidget(self.eq_text_btn, 1)
        row.addWidget(self.eq_math_btn)
        row.addWidget(self.eq_copy_btn)
        col.addWidget(self.eq_input)
        col.addWidget(self.eq_view, 1)
        col.addLayout(tiles)
        col.addLayout(row)
        return page

    def _tile(self, tip, width=40, height=22):
        tile = QToolButton()
        tile.setObjectName("tile")
        tile.setToolTip(tip)
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setIconSize(QSize(width, height))
        tile.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        tile.setFixedHeight(height + 10)
        tile.setMinimumWidth(width + 2)
        return tile

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
        self.eq_view.theme = theme
        self.eq_view.update()
        for tile, picture in self.eq_tiles:
            tile.setIcon(mathview.icon(picture, theme.text, 40, 22, 14))

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
        self.refresh_equation()

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

    # ------------------------------------------------------------------ equations
    def refresh_equation(self):
        """Redraw the preview and say what each button will put into Word."""
        tree = mathexpr.parse(self.eq_input.text())
        text, exact = mathexpr.to_text(tree)
        empty = mathexpr.is_empty(tree)
        self.eq_view.set_node(tree)
        for b in (self.eq_text_btn, self.eq_math_btn, self.eq_copy_btn):
            b.setEnabled(not empty)
        shown = text if len(text) <= 16 else text[:15] + "…"
        self.eq_text_btn.setText("As text" if empty else f"As text  {shown}")
        self.eq_text_btn.setToolTip("" if empty else f"Type it with ordinary characters, in any app:  {text}"
                                    + ("" if exact else "\n(plain characters can't stack this one; an equation can)"))
        # Enter does whichever shows it properly: plain characters when they can, otherwise an equation.
        for b, main in ((self.eq_text_btn, exact), (self.eq_math_btn, not exact and not empty)):
            name = "link" if main else "small"
            if b.objectName() != name:
                b.setObjectName(name)
                b.style().unpolish(b)
                b.style().polish(b)

    def insert_equation(self, as_text=None, other=False):
        source = self.eq_input.text().strip()
        tree = mathexpr.parse(source)
        if mathexpr.is_empty(tree):
            return
        if as_text is None:
            as_text = mathexpr.to_text(tree)[1] != other
        self.ctl.insert_maths(source, as_text)
        self.eq_input.selectAll()

    def _next_hole(self, backward=False):
        """Tab jumps to the next empty slot (□), ready to be typed over."""
        line, text = self.eq_input, self.eq_input.text()
        if backward:
            at = text.rfind(mathexpr.HOLE, 0, max(0, line.selectionStart() if line.hasSelectedText() else line.cursorPosition()))
            at = text.rfind(mathexpr.HOLE) if at < 0 else at
        else:
            at = text.find(mathexpr.HOLE, line.selectionEnd() if line.hasSelectedText() else line.cursorPosition())
            at = text.find(mathexpr.HOLE) if at < 0 else at
        if at >= 0:
            line.setSelection(at, 1)

    def use_template(self, template):
        """Put a structure into the line.  Whatever was selected goes into its first slot."""
        line = self.eq_input
        chosen = line.selectedText()
        hole_at = template.find(mathexpr.HOLE)
        if chosen and chosen != mathexpr.HOLE and hole_at >= 0:
            if len(chosen) > 1 and template[hole_at - 1:hole_at] != "(" and not (chosen[0] in "([{|" and chosen[-1] in ")]}|"):
                chosen = f"({chosen})"
            template = template.replace(mathexpr.HOLE, chosen, 1)
            hole_at = template.find(mathexpr.HOLE)
        start = line.selectionStart() if line.hasSelectedText() else line.cursorPosition()
        line.insert(template)
        line.setFocus()
        if hole_at >= 0:
            line.setSelection(start + hole_at, 1)

    def _open_gallery(self, button, n):
        """The choices under one of the structure buttons, drawn the way they'll look."""
        name, _picture, items = mathexpr.GALLERY[n]
        menu = QMenu(self)
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setSpacing(4)
        color = self.ctl.theme.text
        row = column = 0
        for template in items:
            if template is None or column == 3:
                row, column = row + 1, 0
            if template is None:
                continue
            tile = self._tile(f"{name}:  {template}", 84, 40)
            tile.setIcon(mathview.icon(template, color, 84, 40, 17))
            tile.clicked.connect(lambda _=False, t=template: (menu.close(), self.use_template(t)))
            grid.addWidget(tile, row, column)
            column += 1
        action = QWidgetAction(menu)
        action.setDefaultWidget(holder)
        menu.addAction(action)
        menu.exec(button.mapToGlobal(QPoint(0, button.height() + 2)))

    def _recent_equations(self):
        menu = QMenu(self)
        used = self.store["equations"] or []
        for source in used:
            action = menu.addAction(source if len(source) <= 34 else source[:33] + "…")
            action.triggered.connect(lambda _=False, t=source: (self.eq_input.setText(t), self.eq_input.setFocus()))
        if not used:
            menu.addAction("Equations you insert are kept here").setEnabled(False)
        menu.exec(self.eq_recent_btn.mapToGlobal(QPoint(0, self.eq_recent_btn.height() + 2)))

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

    # ------------------------------------------------------------------ GIF display
    def load_media(self, path):
        self.media.load(path)
        self.media.refit(self.width() - 2 * PAD_SIDE, self.height())
        self.refresh_media()

    def refresh_media(self):
        """Show the GIF under the symbols; the Draw page needs that room for the pad."""
        self.media.setVisible(bool(self.store["media_on"]) and self.media.has_content
                              and self.pages.currentIndex() == 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.media.refit(self.width() - 2 * PAD_SIDE, self.height())

    def _media_menu(self, global_pos):
        menu = QMenu(self)
        menu.addAction("Choose a different GIF…").triggered.connect(self.ctl.choose_media)
        menu.addAction("Hide GIF").triggered.connect(lambda: self.ctl.set_media(False))
        menu.exec(global_pos)

    # ------------------------------------------------------------------ pages & keys
    def show_page(self, page, focus=True):
        page = page if page in PAGES else "search"
        self.store.settings["page"] = page
        self.pages.setCurrentIndex(PAGES.index(page))
        self.refresh_media()
        self.search_tab.setChecked(page == "search")
        self.draw_tab.setChecked(page == "draw")
        self.equation_tab.setChecked(page == "equation")
        self.info.setVisible(page != "equation")        # that bar describes one symbol, not an equation
        if page == "equation":
            if focus:
                self.eq_input.setFocus()
                self.eq_input.selectAll()
        elif page == "draw":
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
        elif self.pages.currentIndex() == 2 and self.eq_input.text():
            self.eq_input.clear()
        else:
            self.ctl.return_focus()

    def eventFilter(self, obj, e):
        if obj is getattr(self, "eq_input", None) and e.type() == QEvent.Type.KeyPress:
            key = e.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):         # ⌘Enter = the other way of inserting
                self.insert_equation(other=bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier))
                return True
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                self._next_hole(backward=key == Qt.Key.Key_Backtab)
                return True
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
            for option in options:
                if option is None:
                    sub.addSeparator()
                    continue
                value, label = option
                a = sub.addAction(label)
                a.setCheckable(True)
                a.setChecked(value == current)
                group.addAction(a)
                a.triggered.connect(lambda _=False, v=value: apply(v))

        def check(label, on, apply):
            a = menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(bool(on))
            a.toggled.connect(apply)

        radio(menu.addMenu("When I pick a symbol"),
              [("type", "Type it into the app I was using"),
               ("paste", "Paste it in (uses the clipboard briefly)"),
               ("copy", "Only copy it")],
              store["insert_method"], lambda v: ctl.set_setting("insert_method", v))
        check("Shrink to a bubble after inserting", store["collapse_after_insert"],
              lambda on: ctl.set_setting("collapse_after_insert", on))
        menu.addAction(f"Shortcuts…    {ctl.open_label or 'none set'}").triggered.connect(ctl.edit_shortcuts)
        radio(menu.addMenu("Show the τ icon in"), SHOW_IN, store["show_in"],
              lambda v: ctl.set_setting("show_in", v))
        menu.addSeparator()
        radio(menu.addMenu("Look"), theme.LOOKS, store["look"], lambda v: ctl.set_setting("look", v))
        self._color_menu(menu.addMenu("Background colour"))
        check("RGB border", store["rgb_border"], lambda on: ctl.set_setting("rgb_border", on))
        check("Show GIF", store["media_on"], ctl.set_media)
        menu.addAction("Choose GIF…").triggered.connect(ctl.choose_media)
        reset = menu.addAction("Reset window size")
        reset.setEnabled(bool(store["panel_size"]))
        reset.triggered.connect(self.window_.reset_size)
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

    def _color_menu(self, sub):
        ctl, store = self.ctl, self.store
        current = (store["bg_color"] or "").lower()
        presets = [value for value, _name in theme.COLORS]
        tick = "    ✓"
        sub.addAction("None" + ("" if current else tick)).triggered.connect(lambda: ctl.set_setting("bg_color", ""))
        sub.addSeparator()
        for value, name in theme.COLORS:
            a = sub.addAction(swatch(value), name + (tick if value == current else ""))
            a.triggered.connect(lambda _=False, v=value: ctl.set_setting("bg_color", v))
        sub.addSeparator()
        if current and current not in presets:
            sub.addAction(swatch(current), "Custom…" + tick).triggered.connect(ctl.choose_bg_color)
        else:
            sub.addAction("Custom…").triggered.connect(ctl.choose_bg_color)
        if theme.build(store["look"]).glass:              # on glass the colour is a tint: choose how strong
            sub.addSeparator()
            group = QActionGroup(sub)
            for value, name in theme.STRENGTHS:
                a = sub.addAction(f"{name} tint")
                a.setCheckable(True)
                a.setChecked(value == store["bg_strength"])
                a.setEnabled(bool(current))
                group.addAction(a)
                a.triggered.connect(lambda _=False, v=value: ctl.set_setting("bg_strength", v))


class Grip(QWidget):
    """An invisible strip along an edge or corner of the open palette; drag it to resize."""

    CURSORS = {"l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
               "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
               "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
               "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor}
    # The part of each corner square that lies over the palette's contents, which must stay clickable.
    INSIDE = {"tl": QRect(PAD_SIDE, PAD_TOP, CORNER - PAD_SIDE, CORNER - PAD_TOP),
              "tr": QRect(0, PAD_TOP, CORNER - PAD_SIDE, CORNER - PAD_TOP),
              "bl": QRect(PAD_SIDE, 0, CORNER - PAD_SIDE, CORNER - PAD_SIDE),
              "br": QRect(0, 0, CORNER - PAD_SIDE, CORNER - PAD_SIDE)}

    def __init__(self, window, edges):
        super().__init__(window)
        self.window_, self.edges = window, edges
        self.setCursor(self.CURSORS[edges])
        if edges in self.INSIDE:
            self.setMask(QRegion(0, 0, CORNER, CORNER).subtracted(QRegion(self.INSIDE[edges])))
        self.hide()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.window_.begin_resize(self.edges, e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        self.window_.resize_to(e.globalPosition().toPoint())

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.window_.end_resize()

    def paintEvent(self, _e):
        if self.edges != "br":
            return
        p = QPainter(self)                      # two little lines in the corner: "drag here to resize"
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.window_.ctl.theme.subtext, 1.3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        for a in (12, 16):
            p.drawLine(QLineF(CORNER - a, CORNER - 7, CORNER - 7, CORNER - a))


class PaletteWindow(QWidget):
    changed = Signal()                  # shown, hidden, opened or shrunk

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
        self.grips = {edges: Grip(self, edges) for edges in ("l", "r", "t", "b", "tl", "tr", "bl", "br")}
        self._drag = None
        self._resizing = None
        self._shortcuts()
        self.hue = 0.0                                  # where the RGB border's colours start
        self._rgb_timer = QTimer(self, interval=33, timeout=self._spin_rgb)
        self.set_rgb(self.store["rgb_border"])

    # ------------------------------------------------------------------ RGB border
    @property
    def rgb_on(self):
        return self._rgb_timer.isActive()

    def set_rgb(self, on):
        if on:
            self._rgb_timer.start()
        else:
            self._rgb_timer.stop()
        self.update()
        self.bubble.update()

    def _spin_rgb(self):
        if not self.isVisible():
            return
        self.hue = (self.hue + 3) % 360
        if self.expanded:          # repaint just the edge, not the whole panel
            r = self.rect()
            self.update(QRegion(r).subtracted(QRegion(r.adjusted(10, 10, -10, -10))))
        else:
            self.bubble.update()

    def rainbow(self, rect):
        """A brush that runs through every colour around the centre of `rect`."""
        g = QConicalGradient(QRectF(rect).center(), self.hue)
        for i in range(7):
            g.setColorAt(i / 6, QColor.fromHsv((i * 60) % 360, 235, 255))
        return QBrush(g)

    def resizeEvent(self, e):
        self.bubble.setGeometry(self.rect())
        self.panel.setGeometry(self.rect())
        self._place_grips()
        super().resizeEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        self.changed.emit()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.changed.emit()

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
        self.bubble.update()
        self.grips["br"].update()

    def glass_shape(self):
        """Corner radius and margin of the glass behind the palette, for the form it's in now."""
        if self.expanded:
            return RADIUS, 0
        if self.store["dock"] == "float":
            return (BUBBLE - 6) / 2, 3                  # the bubble is a circle drawn 3 points in
        return TAB_RADIUS, 0

    # ------------------------------------------------------------------ size
    def min_size(self):
        """The smallest the open palette can be made without squashing what's in it."""
        hint = self.panel.minimumSizeHint()
        height = hint.height()
        media = self.panel.media
        if not media.isHidden():            # the GIF shrinks along with the palette, down to its smallest
            height -= max(0, media.height() - media.SMALLEST)
        return QSize(max(MIN_W, hint.width()), max(MIN_H, height))

    def panel_size(self, area=None):
        """Width and height of the open palette: yours if you've resized it, never bigger than the screen."""
        area = area if area is not None else self._area()
        try:
            w, h = (int(v) for v in self.store["panel_size"])
        except (TypeError, ValueError):
            w, h = PANEL_W, PANEL_H
        smallest = self.min_size()
        return (min(max(w, smallest.width()), max(smallest.width(), area.width() - 2 * MARGIN)),
                min(max(h, smallest.height()), max(smallest.height(), area.height() - 2 * MARGIN)))

    def _place_grips(self):
        """Put the resize strips along the border (only the free edge when docked)."""
        w, h, dock = self.width(), self.height(), self.store["dock"]
        if dock == "float":
            spots = {"l": (0, CORNER, EDGE, h - 2 * CORNER), "r": (w - EDGE, CORNER, EDGE, h - 2 * CORNER),
                     "t": (CORNER, 0, w - 2 * CORNER, EDGE), "b": (CORNER, h - EDGE, w - 2 * CORNER, EDGE),
                     "tl": (0, 0, CORNER, CORNER), "tr": (w - CORNER, 0, CORNER, CORNER),
                     "bl": (0, h - CORNER, CORNER, CORNER), "br": (w - CORNER, h - CORNER, CORNER, CORNER)}
        elif dock == "left":
            spots = {"r": (w - EDGE, 0, EDGE, h)}
        else:
            spots = {"l": (0, 0, EDGE, h)}
        for edges, grip in self.grips.items():
            if self.expanded and edges in spots:
                grip.setGeometry(*spots[edges])
                grip.show()
                grip.raise_()
            else:
                grip.hide()

    def begin_resize(self, edges, gpos):
        self._resizing = {"edges": edges, "start": gpos, "geo": self.geometry()}

    def resize_to(self, gpos):
        r = self._resizing
        if r is None:
            return
        g, edges, d = r["geo"], r["edges"], gpos - r["start"]
        area, smallest = self._area(g.center()), self.min_size()
        left, top, right, bottom = g.left(), g.top(), g.left() + g.width(), g.top() + g.height()
        if "l" in edges:
            left = max(area.left(), min(left + d.x(), right - smallest.width()))
        if "r" in edges:
            right = min(area.right() + 1, max(right + d.x(), left + smallest.width()))
        if "t" in edges:
            top = max(area.top(), min(top + d.y(), bottom - smallest.height()))
        if "b" in edges:
            bottom = min(area.bottom() + 1, max(bottom + d.y(), top + smallest.height()))
        self.setGeometry(left, top, right - left, bottom - top)

    def end_resize(self):
        """Remember the new size, so the palette comes back to it from the bubble and next time."""
        if self._resizing is None:
            return
        self._resizing = None
        size = list(self.panel_size())
        size[0] = self.width()
        if self.store["dock"] == "float":
            size[1] = self.height()
            self.store.settings["panel_pos"] = [self.x(), self.y()]
        self.store["panel_size"] = size
        macos.refresh_shadow(self)

    def reset_size(self):
        self.store["panel_size"] = None
        self.apply_layout()

    def _shortcuts(self):
        def add(seq, fn):
            QShortcut(QKeySequence(seq), self).activated.connect(fn)

        add("Ctrl+F", self.panel.focus_search)          # Ctrl means ⌘ on macOS
        add("Ctrl+D", lambda: self.panel.show_page("draw"))
        add("Ctrl+E", lambda: self.panel.show_page("equation"))
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
            w, h = self.panel_size(area)
            if dock == "float":
                x, y = self.store["panel_pos"] or (area.right() - w - 40, area.top() + 50)
                rect = QRect(x, y, w, h)
            else:
                x = area.left() + MARGIN if dock == "left" else area.right() - w - MARGIN + 1
                rect = QRect(x, area.top() + MARGIN, w, area.height() - 2 * MARGIN)
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
        self._place_grips()
        self.panel.update_dock_button(dock)
        self.update()
        self.ctl.update_glass()
        self.changed.emit()

    def expand(self):
        if self.expanded:
            return
        if self.store["dock"] == "float":
            g, area = self.geometry(), self._area()
            w = self.panel_size(area)[0]
            x = g.right() - w + 1 if g.center().x() > area.center().x() else g.left()
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
                    size = self.panel_size(self._area(gpos))
                    d["offset"] = QPoint(min(d["offset"].x(), size[0] - 60), min(d["offset"].y(), 24))
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
    def summon(self, page=None):
        """Bring the palette forward, on the page you name or the one you were last using."""
        if not self.isVisible():
            self.show()
            self.ctl.after_show()
        if not self.expanded:
            self.store["expanded"] = True
            self.apply_layout()
        self.ctl.focus_palette()
        self.panel.show_page(page or self.store["page"])

    def paintEvent(self, _e):
        if not self.expanded:
            return
        t = self.ctl.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        body = QRectF(self.rect())
        if t.glass and not self.ctl.glass_kind:          # glass isn't available here: fall back to solid
            p.setBrush(t.bg)
            p.drawRoundedRect(body, RADIUS, RADIUS)
        # Over glass this is only a faint tint (or your colour); macOS draws the glass underneath.
        p.setBrush(t.panel)
        p.drawRoundedRect(body, RADIUS, RADIUS)
        if self.rgb_on:
            p.setPen(QPen(self.rainbow(self.rect()), 3))
            inset = 1.5
        elif self.ctl.glass_kind == "glass":
            return                                       # real glass has its own bright rim
        else:
            p.setPen(QPen(t.border, 1))
            inset = 0.5
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(body.adjusted(inset, inset, -inset, -inset), RADIUS - inset, RADIUS - inset)
