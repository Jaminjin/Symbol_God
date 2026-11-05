"""Light and dark colours, and the Qt stylesheet built from them."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette


@dataclass(frozen=True)
class Theme:
    dark: bool
    bg: QColor          # panel background
    field: QColor       # search box, segmented control, pad
    border: QColor
    text: QColor
    subtext: QColor
    hover: QColor
    accent: QColor
    selected: QColor
    pad_line: QColor    # dashed outline of the drawing pad
    ink: QColor         # pen colour


LIGHT = Theme(
    dark=False, bg=QColor(251, 251, 252), field=QColor(239, 240, 243), border=QColor(0, 0, 0, 34),
    text=QColor(28, 28, 32), subtext=QColor(108, 110, 118), hover=QColor(0, 0, 0, 16),
    accent=QColor(46, 108, 235), selected=QColor(46, 108, 235, 46), pad_line=QColor(172, 178, 190),
    ink=QColor(28, 28, 32),
)
DARK = Theme(
    dark=True, bg=QColor(34, 35, 39), field=QColor(48, 49, 55), border=QColor(255, 255, 255, 30),
    text=QColor(240, 241, 245), subtext=QColor(158, 160, 170), hover=QColor(255, 255, 255, 22),
    accent=QColor(102, 148, 255), selected=QColor(102, 148, 255, 70), pad_line=QColor(104, 107, 118),
    ink=QColor(240, 241, 245),
)


def glassy(t: Theme):
    """The same theme with see-through fields, so the glass behind shows."""
    f = t.field
    return replace(t, field=QColor(f.red(), f.green(), f.blue(), 150 if t.dark else 130))


def glass_tint(t: Theme):
    """How much colour to lay over the glass (keeps text readable on busy backgrounds)."""
    return QColor(30, 31, 36, 110) if t.dark else QColor(255, 255, 255, 95)


def pick(setting):
    if setting == "light":
        return LIGHT
    if setting == "dark":
        return DARK
    return DARK if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else LIGHT


def _rgba(c: QColor):
    return f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha()})"


def palette(t: Theme):
    p = QPalette()
    for role, color in ((QPalette.ColorRole.Window, t.bg), (QPalette.ColorRole.Base, t.field),
                        (QPalette.ColorRole.Text, t.text), (QPalette.ColorRole.WindowText, t.text),
                        (QPalette.ColorRole.ButtonText, t.text), (QPalette.ColorRole.Button, t.field),
                        (QPalette.ColorRole.Highlight, t.accent), (QPalette.ColorRole.ToolTipBase, t.bg),
                        (QPalette.ColorRole.ToolTipText, t.text), (QPalette.ColorRole.PlaceholderText, t.subtext)):
        p.setColor(role, color)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    return p


def stylesheet(t: Theme):
    c = {k: _rgba(getattr(t, k)) for k in ("bg", "field", "border", "text", "subtext", "hover", "accent",
                                          "selected")}
    accent_soft = _rgba(QColor(t.accent.red(), t.accent.green(), t.accent.blue(), 34))
    return f"""
    QWidget {{ color: {c['text']}; font-size: 13px; }}
    QLabel#title {{ font-weight: 700; font-size: 13px; }}
    QLabel#subtle {{ color: {c['subtext']}; font-size: 11px; }}
    QLabel#name {{ font-weight: 600; }}
    QLabel#preview {{ font-size: 30px; }}
    QLabel#hint {{ color: {c['subtext']}; font-size: 12px; }}
    QLineEdit#search {{
        background: {c['field']}; border: 1px solid transparent; border-radius: 9px;
        padding: 6px 10px; font-size: 14px; selection-background-color: {c['accent']};
    }}
    QLineEdit#search:focus {{ border: 1px solid {c['accent']}; }}
    QWidget#segments {{ background: {c['field']}; border-radius: 9px; }}
    QPushButton#segment {{
        background: transparent; border: none; border-radius: 7px; padding: 5px 0px;
        font-weight: 600; color: {c['subtext']};
    }}
    QPushButton#segment:checked {{ background: {c['bg']}; color: {c['text']}; }}
    QPushButton#segment:hover:!checked {{ color: {c['text']}; }}
    QToolButton#header {{
        background: transparent; border: none; border-radius: 6px; padding: 2px;
        font-size: 15px; color: {c['subtext']}; min-width: 24px; min-height: 24px;
    }}
    QToolButton#header:hover {{ background: {c['hover']}; color: {c['text']}; }}
    QToolButton#header::menu-indicator {{ image: none; width: 0px; }}
    QToolButton#category {{
        background: {c['field']}; border: none; border-radius: 7px; padding: 4px 10px;
        font-weight: 600;
    }}
    QToolButton#category:hover {{ background: {c['hover']}; }}
    QToolButton#category::menu-indicator {{ image: none; width: 0px; }}
    QPushButton#small {{
        background: {c['field']}; border: none; border-radius: 7px; padding: 4px 10px;
    }}
    QPushButton#small:hover {{ background: {c['hover']}; }}
    QPushButton#small:disabled {{ color: {c['subtext']}; }}
    QPushButton#link {{
        background: {c['accent']}; color: white; border: none; border-radius: 7px;
        padding: 4px 10px; font-weight: 600;
    }}
    QFrame#banner {{ background: {accent_soft}; border-radius: 9px; }}
    QListView {{ background: transparent; border: none; outline: none; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px 0px 2px 0px; }}
    QScrollBar::handle:vertical {{ background: rgba(128,128,128,110); border-radius: 3px; min-height: 28px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QScrollBar:horizontal {{ height: 0px; }}
    QMenu {{
        background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 4px;
    }}
    QMenu::item {{ padding: 5px 22px 5px 22px; border-radius: 5px; }}
    QMenu::item:selected {{ background: {c['selected']}; }}
    QMenu::item:disabled {{ color: {c['subtext']}; }}
    QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 6px; }}
    QMenu::indicator {{ width: 12px; height: 12px; left: 6px; }}
    QToolTip {{
        background: {c['bg']}; color: {c['text']}; border: 1px solid {c['border']};
        padding: 4px 6px; border-radius: 6px;
    }}
    """
