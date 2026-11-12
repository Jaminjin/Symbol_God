"""Draws built-up maths: the preview on the Equation page and the pictures in its gallery."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QFontMetricsF, QIcon, QPainter, QPainterPath, QPen,
                           QPixmap, QTransform)
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import mathexpr as mx

SMALLEST = 0.5          # scripts inside scripts stop shrinking at half size


@lru_cache(maxsize=1)
def _family():
    for name in ("STIX Two Math", "STIXGeneral", "Cambria Math"):
        if name in QFontDatabase.families():
            return name
    return QFont().family()


def _font(size):
    font = QFont(_family())
    font.setPixelSize(max(1, round(size)))
    return font


def _italic(text):
    """Variables are written in italics; the maths font keeps those as characters of their own."""
    out = []
    for ch in text:
        if ch == "h":
            out.append("ℎ")
        elif "a" <= ch <= "z":
            out.append(chr(0x1D44E + ord(ch) - ord("a")))
        elif "A" <= ch <= "Z":
            out.append(chr(0x1D434 + ord(ch) - ord("A")))
        elif "α" <= ch <= "ω":
            out.append(chr(0x1D6FC + ord(ch) - ord("α")))
        else:
            out.append(ch)
    return "".join(out)


class Box:
    """Something already laid out: how wide, how far above and below the line, and how to draw it."""

    def __init__(self, w, up, down, paint):
        self.w, self.up, self.down, self.paint = w, up, down, paint

    @property
    def height(self):
        return self.up + self.down


def _text_box(text, size, pad_left=0.0, pad_right=0.0):
    font = _font(size)
    metrics = QFontMetricsF(font)
    tight = metrics.tightBoundingRect(text)
    width = metrics.horizontalAdvance(text)

    def paint(p, x, y):
        p.setFont(font)
        p.drawText(QPointF(x + pad_left, y), text)

    return Box(width + pad_left + pad_right, max(-tight.top(), metrics.xHeight()), max(tight.bottom(), 0.0), paint)


def _hole_box(size):
    side = size * 0.56

    def paint(p, x, y):
        pen = QPen(p.pen().color(), max(1.0, size * 0.045), Qt.PenStyle.DashLine)
        pen.setDashPattern([2, 2])
        p.save()
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(x + size * 0.06, y - side - size * 0.02, side, side), size * 0.08, size * 0.08)
        p.restore()

    return Box(side + size * 0.12, side + size * 0.04, size * 0.02, paint)


def _hbox(boxes):
    boxes = list(boxes)

    def paint(p, x, y):
        for box in boxes:
            box.paint(p, x, y)
            x += box.w

    return Box(sum(b.w for b in boxes), max((b.up for b in boxes), default=0.0),
               max((b.down for b in boxes), default=0.0), paint)


def _shift(box, dx, dy):
    return lambda p, x, y: box.paint(p, x + dx, y + dy)


def _line(p, size, x1, y1, x2, y2):
    p.save()
    p.setPen(QPen(p.pen().color(), max(1.0, size * 0.055), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                  Qt.PenJoinStyle.RoundJoin))
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    p.restore()


def _sym(node, size, base, spaced=(0.0, 0.0)):
    if node.kind == "hole":
        return _hole_box(size)
    if node.kind == "big":
        return _text_box(node.text, size * (1.45 if size >= base * 0.99 else 1.15), size * 0.04, size * 0.06)
    if node.kind == "id":
        return _text_box(_italic(node.text), size)
    return _text_box(node.text, size, spaced[0] * size, spaced[1] * size)


def _row(items, size, base):
    boxes = []
    roomy = size >= base * 0.8                      # scripts are set tight
    for i, item in enumerate(items):
        if isinstance(item, mx.Sym) and item.kind == "op":
            before = items[i - 1] if i else None
            binary = before is not None and not (isinstance(before, mx.Sym) and before.kind == "op")
            pad = (0.0, 0.0)
            if roomy and item.text in mx.RELATIONS:
                pad = (0.26, 0.26)
            elif roomy and item.text in mx.BINARY and binary and i + 1 < len(items):
                pad = (0.2, 0.2)
            elif item.text in ",;":
                pad = (0.0, 0.22)
            boxes.append(_sym(item, size, base, pad))
            continue
        box = layout(item, size, base)
        follows = i + 1 < len(items)
        if follows and mx._is_kind(item, "fn") and not isinstance(items[i + 1], mx.Fence):
            box = _hbox([box, Box(size * 0.17, 0, 0, lambda *_: None)])
        elif follows and mx._is_kind(item, "big"):
            box = _hbox([box, Box(size * 0.1, 0, 0, lambda *_: None)])
        boxes.append(box)
    return _hbox(boxes)


def _script(node, size, base):
    small = max(size * 0.7, base * SMALLEST)
    b = layout(node.base, size, base)
    sup = layout(node.sup, small, base) if node.sup is not None else None
    sub = layout(node.sub, small, base) if node.sub is not None else None
    rise = max(size * 0.4, b.up - small * 0.45) if sup else 0.0
    drop = max(size * 0.2, b.down + small * 0.12) if sub else 0.0
    if sup and sub:                                 # keep the two from touching
        clash = (sup.down - rise) + (sub.up - drop) + size * 0.08
        if clash > 0:
            rise, drop = rise + clash / 2, drop + clash / 2
    gap = size * 0.03
    lean = size * 0.3 if mx._is_kind(node.base, "big") else 0.0     # an integral sign slopes away at the bottom

    def paint(p, x, y):
        b.paint(p, x, y)
        if sup:
            sup.paint(p, x + b.w + gap, y - rise)
        if sub:
            sub.paint(p, x + b.w + gap - lean, y + drop)

    return Box(b.w + gap + max(sup.w if sup else 0, sub.w if sub else 0) + size * 0.04,
               max(b.up, rise + sup.up if sup else 0), max(b.down, drop + sub.down if sub else 0), paint)


def _stack(node, size, base):
    small = max(size * 0.7, base * SMALLEST)
    b = layout(node.base, size, base)
    over = layout(node.over, small, base) if node.over is not None else None
    under = layout(node.under, small, base) if node.under is not None else None
    gap = size * 0.1
    width = max(b.w, over.w if over else 0, under.w if under else 0)

    def paint(p, x, y):
        b.paint(p, x + (width - b.w) / 2, y)
        if over:
            over.paint(p, x + (width - over.w) / 2, y - b.up - gap - over.down)
        if under:
            under.paint(p, x + (width - under.w) / 2, y + b.down + gap + under.up)

    return Box(width, b.up + (gap + over.height if over else 0), b.down + (gap + under.height if under else 0), paint)


def _frac(node, size, base):
    inner = max(size * 0.86, base * SMALLEST)
    num, den = layout(node.num, inner, base), layout(node.den, inner, base)
    axis, gap, pad = size * 0.26, size * 0.14, size * 0.12
    width = max(num.w, den.w) + 2 * pad

    def paint(p, x, y):
        num.paint(p, x + (width - num.w) / 2, y - axis - gap - num.down)
        den.paint(p, x + (width - den.w) / 2, y - axis + gap + den.up)
        if node.bar:
            _line(p, size, x + pad * 0.4, y - axis, x + width - pad * 0.4, y - axis)

    return Box(width, axis + gap + num.height, gap + den.height - axis, paint)


def _root(node, size, base):
    body = layout(node.body, size, base)
    degree = layout(node.degree, max(size * 0.5, base * 0.4), base) if node.degree is not None else None
    top, hook = size * 0.16, size * 0.5
    lead = max(0.0, (degree.w - hook * 0.55) if degree else 0.0)
    up, down = body.up + top, body.down + size * 0.04

    def paint(p, x, y):
        x += lead
        path = QPainterPath(QPointF(x + size * 0.02, y - up * 0.42))
        path.lineTo(x + size * 0.12, y - up * 0.5)
        path.lineTo(x + hook * 0.58, y + down)
        path.lineTo(x + hook, y - up + size * 0.03)
        path.lineTo(x + hook + body.w + size * 0.08, y - up + size * 0.03)
        p.save()
        p.setPen(QPen(p.pen().color(), max(1.0, size * 0.055), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.restore()
        body.paint(p, x + hook + size * 0.04, y)
        if degree:
            degree.paint(p, x - lead + size * 0.02, y - up * 0.5 - degree.down - size * 0.04)

    return Box(lead + hook + body.w + size * 0.14, max(up, (up * 0.5 + degree.height + size * 0.04) if degree else 0),
               down, paint)


def _bracket(ch, size, up, down):
    """A bracket tall enough for what's inside: the ordinary character, stretched when it has to be."""
    if not ch:
        return Box(0, 0, 0, lambda *_: None)
    plain = _text_box(ch, size)
    if up + down <= plain.height * 1.15:
        return plain
    path = QPainterPath()
    path.addText(0, 0, _font(size), ch)
    bounds = path.boundingRect()
    tall = up + down + size * 0.1
    stretch = QTransform.fromScale(1.0, tall / bounds.height())
    path = stretch.map(path)
    bounds = path.boundingRect()
    width = QFontMetricsF(_font(size)).horizontalAdvance(ch)

    def paint(p, x, y):
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(p_color(p))
        p.translate(x, y - up - size * 0.05 - bounds.top())
        p.drawPath(path)
        p.restore()

    return Box(width, up + size * 0.05, down + size * 0.05, paint)


def p_color(p):
    return p.property("ink") or QColor("black")


def _fence(open_, close, body, size):
    up, down = max(body.up, size * 0.5), max(body.down, size * 0.12)
    return _hbox([_bracket(open_, size, up, down), body, _bracket(close, size, up, down)])


def _accent(node, size, base):
    body = layout(node.body, size, base)
    mark, gap, room = node.mark, size * 0.08, size * 0.24
    if mark == "underline":
        return Box(body.w, body.up, body.down + gap * 2,
                   lambda p, x, y: (body.paint(p, x, y), _line(p, size, x, y + body.down + gap, x + body.w, y + body.down + gap)))

    def paint(p, x, y):
        body.paint(p, x, y)
        mid, top = x + body.w / 2, y - body.up - gap
        half = body.w / 2 if mark in ("overline", "vec") else min(body.w * 0.4, size * 0.3)
        if mark in ("bar", "overline"):
            _line(p, size, mid - half, top - room * 0.3, mid + half, top - room * 0.3)
        elif mark == "hat":
            _line(p, size, mid - half * 0.8, top, mid, top - room * 0.8)
            _line(p, size, mid, top - room * 0.8, mid + half * 0.8, top)
        elif mark == "vec":
            half = max(half, size * 0.22)
            height = top - room * 0.45
            _line(p, size, mid - half, height, mid + half, height)
            _line(p, size, mid + half, height, mid + half - size * 0.13, height - size * 0.09)
            _line(p, size, mid + half, height, mid + half - size * 0.13, height + size * 0.09)
        elif mark == "tilde":
            path = QPainterPath(QPointF(mid - half, top - room * 0.2))
            path.cubicTo(mid - half * 0.4, top - room * 1.1, mid + half * 0.4, top + room * 0.5, mid + half, top - room * 0.5)
            p.save()
            p.setPen(QPen(p.pen().color(), max(1.0, size * 0.055), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
            p.restore()
        else:                                       # one dot or two
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(p_color(p))
            radius = size * 0.055
            for dx in ((0,) if mark == "dot" else (-size * 0.1, size * 0.1)):
                p.drawEllipse(QPointF(mid + dx, top - room * 0.4), radius, radius)
            p.restore()

    return Box(max(body.w, size * 0.44) if mark == "vec" else body.w, body.up + gap + room, body.down,
               lambda p, x, y: paint(p, x + (max(body.w, size * 0.44) - body.w) / 2 if mark == "vec" else x, y))


def _matrix(node, size, base):
    cells = [[layout(cell, size, base) for cell in row] for row in node.rows]
    columns = max(len(row) for row in cells)
    widths = [max((row[c].w for row in cells if c < len(row)), default=0.0) for c in range(columns)]
    ups = [max(max(b.up for b in row), size * 0.5) for row in cells]
    downs = [max(max(b.down for b in row), size * 0.15) for row in cells]
    column_gap, row_gap, axis = size * 0.7, size * 0.3, size * 0.26
    total = sum(ups) + sum(downs) + row_gap * (len(cells) - 1)
    width = sum(widths) + column_gap * (columns - 1)

    def paint(p, x, y):
        top = y - axis - total / 2
        for r, row in enumerate(cells):
            line = top + ups[r]
            left = x
            for c, box in enumerate(row):
                box.paint(p, left if node.align == "left" else left + (widths[c] - box.w) / 2, line)
                left += widths[c] + column_gap
            top = line + downs[r] + row_gap

    table = Box(width, total / 2 + axis, total / 2 - axis, paint)
    if node.open or node.close:
        pad = Box(size * 0.08, 0, 0, lambda *_: None)
        return _fence(node.open, node.close, _hbox([pad, table, pad]), size)
    return table


def layout(node, size, base=None):
    """Lay a tree from mathexpr out at `size` pixels."""
    base = base or size
    if node is None:
        return Box(0, 0, 0, lambda *_: None)
    if isinstance(node, mx.Sym):
        return _sym(node, size, base)
    if isinstance(node, mx.Row):
        return _row(node.items, size, base)
    if isinstance(node, mx.Script):
        return _script(node, size, base)
    if isinstance(node, mx.Stack):
        return _stack(node, size, base)
    if isinstance(node, mx.Frac):
        return _frac(node, size, base)
    if isinstance(node, mx.Root):
        return _root(node, size, base)
    if isinstance(node, mx.Fence):
        return _fence(node.open, node.close, layout(node.body, size, base), size)
    if isinstance(node, mx.Accent):
        return _accent(node, size, base)
    if isinstance(node, mx.Matrix):
        return _matrix(node, size, base)
    raise TypeError(node)


class _Painter(QPainter):
    """A painter that remembers its ink colour (filled shapes need it as well as the pen)."""

    def __init__(self, device, color):
        super().__init__(device)
        self._ink = QColor(color)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setPen(self._ink)

    def property(self, name):
        return self._ink if name == "ink" else None


def draw(device, node, color, rect, size, smallest=9.0):
    """Draw the maths in the middle of `rect`, shrunk if it has to be to fit."""
    box = layout(node, size)
    if box.w <= 0:
        return
    scale = min(1.0, rect.width() / box.w, rect.height() / max(box.height, 1.0))
    if scale < 1.0:
        size = max(smallest, size * scale * 0.98)
        box = layout(node, size)
    p = _Painter(device, color)
    p.setClipRect(rect)
    box.paint(p, rect.left() + max(0.0, (rect.width() - box.w) / 2), rect.top() + (rect.height() - box.height) / 2 + box.up)
    p.end()


def icon(text, color, width=64, height=30, size=17):
    """A small picture of some maths, for buttons and menus."""
    ratio = 2
    pix = QPixmap(width * ratio, height * ratio)
    pix.setDevicePixelRatio(ratio)
    pix.fill(Qt.GlobalColor.transparent)
    draw(pix, mx.parse(text), color, QRectF(1, 1, width - 2, height - 2), size, smallest=6.0)
    return QIcon(pix)


class MathView(QWidget):
    """The preview: what you've typed, built up the way it will look in Word."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.node, self.theme, self.hint = None, None, ""
        self.setMinimumHeight(54)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_node(self, node):
        self.node = node
        self.update()

    def paintEvent(self, _e):
        t = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(t.field if t else QColor(128, 128, 128, 40))
        p.drawRoundedRect(QRectF(self.rect()), 11, 11)
        inner = QRectF(self.rect()).adjusted(12, 8, -12, -8)
        if self.node is None or mx.is_empty(self.node):
            p.setPen(t.subtext if t else QColor(128, 128, 128))
            p.drawText(inner, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), self.hint)
            p.end()
            return
        p.end()
        draw(self, self.node, t.text if t else QColor("black"), inner, min(34.0, inner.height() * 0.5))
