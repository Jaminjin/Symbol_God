"""Reusable widgets: symbol grid, drawing pad, info bar, toast and the bubble."""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImageReader, QMovie, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QListView, QPushButton, QSizePolicy,
                               QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

from .symbols import code_of, display_text, is_combining

CHAR_ROLE = Qt.ItemDataRole.UserRole


# --------------------------------------------------------------------------- symbol grid
class SymbolModel(QAbstractListModel):
    def __init__(self, index):
        super().__init__()
        self.symbol_index = index
        self.chars: list[str] = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.chars)

    def data(self, idx, role=Qt.ItemDataRole.DisplayRole):
        if not idx.isValid():
            return None
        ch = self.chars[idx.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return display_text(ch)
        if role == CHAR_ROLE:
            return ch
        if role == Qt.ItemDataRole.ToolTipRole:
            sym = self.symbol_index.get(ch)
            return f"{sym.name}  ·  {code_of(ch)}" if sym else code_of(ch)
        return None

    def set_chars(self, chars):
        self.beginResetModel()
        self.chars = list(chars)
        self.endResetModel()


class SymbolDelegate(QStyledItemDelegate):
    def __init__(self, view, cell, font_px):
        super().__init__(view)
        self.cell = cell
        self.font_px = font_px
        self.theme = None

    def sizeHint(self, option, index):
        return QSize(self.cell, self.cell)

    def paint(self, p, option, index):
        t = self.theme
        r = QRectF(option.rect).adjusted(2, 2, -2, -2)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        if option.state & QStyle.StateFlag.State_Selected:
            p.setBrush(t.selected)
            p.drawRoundedRect(r, 8, 8)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            p.setBrush(t.hover)
            p.drawRoundedRect(r, 8, 8)
        text = index.data()
        font = QFont(option.font)
        font.setPixelSize(self.font_px)
        width = QFontMetrics(font).horizontalAdvance(text)
        if width > r.width() - 4:                      # long arrows, ligatures ...
            font.setPixelSize(max(9, int(self.font_px * (r.width() - 4) / width)))
        p.setFont(font)
        p.setPen(t.text)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
        p.restore()


class SymbolGrid(QListView):
    picked = Signal(str)                 # clicked, or Enter pressed
    hovered = Signal(str)                # "" when the mouse leaves
    current = Signal(str)                # keyboard selection changed
    typed = Signal(str)                  # letters typed while the grid has focus
    menu_requested = Signal(str, QPoint)

    def __init__(self, index, cell=40, font_px=22, single_row=False, parent=None):
        super().__init__(parent)
        self.cell = cell
        self.symbols = SymbolModel(index)
        self.setModel(self.symbols)
        self.delegate = SymbolDelegate(self, cell, font_px)
        self.setItemDelegate(self.delegate)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(not single_row)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setGridSize(QSize(cell, cell))
        self.setDragEnabled(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(cell // 2)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if single_row:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setFixedHeight(cell + 2)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.clicked.connect(lambda i: self.picked.emit(i.data(CHAR_ROLE)))
        self.entered.connect(lambda i: self.hovered.emit(i.data(CHAR_ROLE)))

    def set_theme(self, theme):
        self.delegate.theme = theme
        self.viewport().update()

    def set_chars(self, chars):
        self.symbols.set_chars(chars)
        if chars:
            self.setCurrentIndex(self.symbols.index(0))
        self.scrollToTop()

    def chars(self):
        return self.symbols.chars

    def current_char(self):
        i = self.currentIndex()
        return i.data(CHAR_ROLE) if i.isValid() else None

    def currentChanged(self, cur, prev):
        super().currentChanged(cur, prev)
        if cur.isValid():
            self.current.emit(cur.data(CHAR_ROLE))

    def resizeEvent(self, e):
        # stretch cells a little so the grid fills the width evenly
        if self.isWrapping():
            width = self.viewport().width()
            cols = max(1, width // self.cell)
            self.setGridSize(QSize(width // cols, self.cell))
        super().resizeEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            ch = self.current_char()
            if ch:
                self.picked.emit(ch)
            return
        text = e.text()
        command = e.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        if text and text.isprintable() and not command:
            self.typed.emit(text)       # instead of Qt's jump-to-item type-ahead
            return
        super().keyPressEvent(e)

    def leaveEvent(self, e):
        self.hovered.emit("")
        super().leaveEvent(e)

    def _context_menu(self, pos):
        i = self.indexAt(pos)
        if i.isValid():
            self.menu_requested.emit(i.data(CHAR_ROLE), self.viewport().mapToGlobal(pos))


# --------------------------------------------------------------------------- drawing pad
class DrawPad(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.strokes: list[list[tuple[float, float]]] = []
        self._current = None
        self.theme = None
        self.message = "Draw a symbol here"
        self.setMinimumHeight(170)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def pad_size(self):
        return float(min(self.width(), self.height()))

    def undo(self):
        if self.strokes:
            self.strokes.pop()
            self.update()
            self.changed.emit()

    def clear(self):
        if self.strokes or self._current:
            self.strokes, self._current = [], None
            self.update()
            self.changed.emit()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            p = e.position()
            self._current = [(p.x(), p.y())]
            self.update()

    def mouseMoveEvent(self, e):
        if self._current is not None:
            p = e.position()
            lx, ly = self._current[-1]
            if (p.x() - lx) ** 2 + (p.y() - ly) ** 2 >= 1.5:
                self._current.append((p.x(), p.y()))
                self.update()

    def mouseReleaseEvent(self, e):
        if self._current is not None:
            self.strokes.append(self._current)
            self._current = None
            self.update()
            self.changed.emit()

    def paintEvent(self, _e):
        t = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(t.field)
        p.drawRoundedRect(r, 12, 12)
        dash = QPen(t.pad_line, 1.4, Qt.PenStyle.CustomDashLine)
        dash.setDashPattern([4, 4])
        p.setPen(dash)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 12, 12)
        strokes = self.strokes + ([self._current] if self._current else [])
        if not strokes:
            font = p.font()
            font.setPixelSize(17)
            p.setFont(font)
            p.setPen(t.subtext)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.message)
            return
        p.setPen(QPen(t.ink, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for s in strokes:
            if len(s) == 1:
                p.drawPoint(QPointF(*s[0]))
                continue
            path = QPainterPath(QPointF(*s[0]))
            for (x0, y0), (x1, y1) in zip(s[:-1], s[1:]):        # smooth through midpoints
                path.quadTo(QPointF(x0, y0), QPointF((x0 + x1) / 2, (y0 + y1) / 2))
            path.lineTo(QPointF(*s[-1]))
            p.drawPath(path)


# --------------------------------------------------------------------------- GIF display
class MediaView(QWidget):
    """A GIF that replays forever (or a still picture) in the panel's spare space."""

    menu_requested = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._movie = None
        self._still = None
        self._aspect = 16 / 9
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: self.menu_requested.emit(self.mapToGlobal(pos)))

    @property
    def has_content(self):
        return self._movie is not None or self._still is not None

    def load(self, path):
        """Show the file at `path` (None clears it).  Returns False if it can't be read."""
        if self._movie is not None:
            self._movie.stop()
            self._movie.deleteLater()
        self._movie = self._still = None
        if path is None:
            self.update()
            return False
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        if not reader.canRead():
            return False
        if reader.supportsAnimation():
            size = reader.size()
            if size.isValid() and size.height() > 0:
                self._aspect = size.width() / size.height()
            self._movie = QMovie(str(path))
            self._movie.setParent(self)
            self._movie.frameChanged.connect(lambda _frame: self.update())
            self._movie.finished.connect(self._movie.start)      # some GIFs only play once by themselves
            self._movie.start()
            if not self.isVisible():
                self._movie.setPaused(True)
        else:
            self._still = QPixmap.fromImage(reader.read())
            if self._still.isNull():
                self._still = None
                return False
            self._aspect = self._still.width() / self._still.height()
        self.update()
        return True

    def refit(self, width, panel_height):
        """As tall as the picture needs at this width, leaving most of the panel for symbols."""
        tallest = max(80, int(panel_height * 0.3))
        self.setFixedHeight(max(80, min(int(width / self._aspect), tallest)))

    def showEvent(self, e):
        super().showEvent(e)
        if self._movie is not None:
            self._movie.setPaused(False)

    def hideEvent(self, e):
        super().hideEvent(e)
        if self._movie is not None:
            self._movie.setPaused(True)      # no point animating what nobody can see

    def paintEvent(self, _e):
        pix = self._movie.currentPixmap() if self._movie is not None else self._still
        if pix is None or pix.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        size = pix.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        rect = QRect(QPoint((self.width() - size.width()) // 2, (self.height() - size.height()) // 2), size)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(rect), 10, 10)
        p.setClipPath(clip)
        p.drawPixmap(rect, pix)


# --------------------------------------------------------------------------- info bar
class InfoBar(QWidget):
    favorite_clicked = Signal(str)
    copy_clicked = Signal(str)

    def __init__(self, index, store, parent=None):
        super().__init__(parent)
        self.index, self.store = index, store
        self.char = None
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 0, 0, 0)
        row.setSpacing(10)
        self.preview = QLabel()
        self.preview.setObjectName("preview")         # big glyph; size comes from the stylesheet
        self.preview.setFixedSize(46, 46)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QVBoxLayout()
        text.setSpacing(1)
        self.name = QLabel()
        self.name.setObjectName("name")
        self.detail = QLabel()
        self.detail.setObjectName("subtle")
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        for label in (self.name, self.detail):       # long names get cut, never widen the panel
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text.addStretch(1)
        text.addWidget(self.name)
        text.addWidget(self.detail)
        text.addStretch(1)
        self.fav = QPushButton("☆")
        self.fav.setObjectName("small")
        self.fav.setFixedWidth(34)
        self.fav.setToolTip("Add to / remove from Favorites")
        self.copy = QPushButton("Copy")
        self.copy.setObjectName("small")
        self.copy.setToolTip("Copy to the clipboard without inserting")
        row.addWidget(self.preview)
        row.addLayout(text, 1)
        row.addWidget(self.fav)
        row.addWidget(self.copy)
        self.fav.clicked.connect(lambda: self.char and self.favorite_clicked.emit(self.char))
        self.copy.clicked.connect(lambda: self.char and self.copy_clicked.emit(self.char))
        self.show_char(None)

    def _elide(self):
        width = max(60, self.name.width())
        self.name.setText(QFontMetrics(self.name.font()).elidedText(self._full_name, Qt.TextElideMode.ElideRight,
                                                                    width))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.char:
            self._elide()

    def show_char(self, ch):
        self.char = ch or None
        enabled = self.char is not None
        self.fav.setEnabled(enabled)
        self.copy.setEnabled(enabled)
        if not enabled:
            self.preview.setText("")
            self.name.setText("Pick a symbol to insert it")
            self.detail.setText("Hover to see its name · right-click for more")
            self.fav.setText("☆")
            return
        sym = self.index.get(ch)
        self.preview.setText(display_text(ch))
        self._full_name = sym.name if sym else "Unknown character"
        self._elide()
        self.name.setToolTip(self._full_name)
        bits = [code_of(ch)]
        if sym and sym.latex:
            bits.append("\\" + sym.latex[0])
        if sym and sym.mac_key:
            bits.append("Mac: " + sym.mac_key)
        if is_combining(ch):
            bits.append("goes on the letter before it")
        self.detail.setText("  ·  ".join(bits))
        self.fav.setText("★" if self.store.is_favorite(ch) else "☆")


# --------------------------------------------------------------------------- toast
class Toast(QWidget):
    """A small message that appears for a moment without taking focus."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.text = ""
        self.theme = None
        self._timer = QTimer(self, singleShot=True, timeout=self.hide)

    def show_message(self, text, anchor: QRect, below=False, ms=2200):
        self.text = text
        font = self.font()
        font.setPixelSize(13)
        self.setFont(font)
        fm = QFontMetrics(font)
        w, h = fm.horizontalAdvance(text) + 28, fm.height() + 16
        self.resize(w, h)
        x = anchor.center().x() - w // 2
        y = anchor.bottom() + 8 if below else anchor.bottom() - h - 14
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen is not None:
            x = max(screen.left() + 4, min(x, screen.right() - w - 4))
            y = max(screen.top() + 4, min(y, screen.bottom() - h - 4))
        self.move(x, y)
        self.show()
        self.update()
        self._timer.start(ms)

    def paintEvent(self, _e):
        t = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(250, 250, 252) if t and t.dark else QColor(36, 37, 42)
        fg = QColor(28, 28, 32) if t and t.dark else QColor(246, 246, 248)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        p.setPen(fg)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)


# --------------------------------------------------------------------------- bubble
class Bubble(QWidget):
    """The collapsed palette: a round button, or a tab when docked to a screen edge."""

    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.side = "float"
        self.theme = None
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("SymbolPad: click to open, drag to move")

    def enterEvent(self, _e):
        self._hover = True
        self.update()

    def leaveEvent(self, _e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.window_.begin_drag(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        self.window_.drag_to(e.globalPosition().toPoint())

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if not self.window_.end_drag(e.globalPosition().toPoint()):
                self.window_.expand()

    def paintEvent(self, _e):
        t = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent = t.accent.lighter(112) if self._hover else t.accent
        r = QRectF(self.rect())
        if self.window_.rgb_on:
            p.setPen(QPen(self.window_.rainbow(self.rect()), 3))
        else:
            p.setPen(QPen(QColor(255, 255, 255, 70), 1))
        p.setBrush(accent)
        if self.side == "float":
            p.drawEllipse(r.adjusted(3, 3, -3, -3))
            glyph_rect = r
        else:
            # tab hugging the screen edge: round only the inner corners
            path = QPainterPath()
            radius = 12
            if self.side == "right":
                body = r.adjusted(0.5, 0.5, radius, -0.5)
            else:
                body = r.adjusted(-radius, 0.5, -0.5, -0.5)
            path.addRoundedRect(body, radius, radius)
            p.setClipRect(r)
            p.drawPath(path)
            glyph_rect = r
        font = p.font()
        font.setPixelSize(22 if self.side == "float" else 18)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("white"))
        p.drawText(glyph_rect, Qt.AlignmentFlag.AlignCenter, "τ")
