"""The τ app icon, drawn in code.  Used for the Dock and for the SymbolPad.app bundle."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QConicalGradient, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen


def app_icon(size=1024):
    """A square QImage of the icon, `size` pixels wide."""
    img = QImage(1024, 1024, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    body = QRectF(100, 100, 824, 824)                       # Apple's icon grid leaves a margin
    shape = QPainterPath()
    shape.addRoundedRect(body, 185, 185)
    fill = QLinearGradient(body.topLeft(), body.bottomLeft())
    fill.setColorAt(0, QColor(92, 146, 255))
    fill.setColorAt(1, QColor(38, 82, 222))
    p.fillPath(shape, fill)
    ring = QConicalGradient(body.center(), 90)
    for i in range(7):
        ring.setColorAt(i / 6, QColor.fromHsv((i * 60) % 360, 235, 255))
    p.setPen(QPen(ring, 26))
    p.drawPath(shape)
    font = QFont()
    font.setPixelSize(600)
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor("white"))
    p.drawText(body.adjusted(0, -40, 0, 0), Qt.AlignmentFlag.AlignCenter, "τ")
    p.end()
    if size == 1024:
        return img
    return img.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
