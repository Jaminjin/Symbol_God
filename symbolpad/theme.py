"""The looks SymbolPad can have (Liquid Glass or solid, light or dark, your own colour)
and the Qt stylesheet built from them."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

RADIUS = 20          # corner radius of the open palette


@dataclass(frozen=True)
class Theme:
    dark: bool          # light text on a dark background
    bg: QColor          # menus and tooltips; also the palette itself when it's solid
    panel: QColor       # what the palette paints over itself (see-through when it's glass)
    field: QColor       # search box, segmented control, pad
    raised: QColor      # the selected tab
    border: QColor
    text: QColor
    subtext: QColor
    hover: QColor
    accent: QColor
    accent_text: QColor  # text on top of the accent colour
    selected: QColor
    pad_line: QColor    # dashed outline of the drawing pad
    ink: QColor         # pen colour
    bubble: QColor      # the collapsed bubble and its τ
    bubble_text: QColor
    glass: str = ""     # "" (solid), "regular" or "clear" Liquid Glass behind the palette
    glass_dark: bool = True


WHITE, BLACK = QColor(255, 255, 255), QColor(0, 0, 0)

LIGHT = Theme(
    dark=False, bg=QColor(251, 251, 252), panel=QColor(251, 251, 252), field=QColor(239, 240, 243),
    raised=QColor(251, 251, 252), border=QColor(0, 0, 0, 34), text=QColor(28, 28, 32),
    subtext=QColor(108, 110, 118), hover=QColor(0, 0, 0, 16), accent=QColor(46, 108, 235), accent_text=WHITE,
    selected=QColor(46, 108, 235, 46), pad_line=QColor(172, 178, 190), ink=QColor(28, 28, 32),
    bubble=QColor(46, 108, 235), bubble_text=WHITE,
)
DARK = Theme(
    dark=True, bg=QColor(34, 35, 39), panel=QColor(34, 35, 39), field=QColor(48, 49, 55),
    raised=QColor(34, 35, 39), border=QColor(255, 255, 255, 30), text=QColor(240, 241, 245),
    subtext=QColor(158, 160, 170), hover=QColor(255, 255, 255, 22), accent=QColor(102, 148, 255),
    accent_text=WHITE, selected=QColor(102, 148, 255, 70), pad_line=QColor(104, 107, 118),
    ink=QColor(240, 241, 245), bubble=QColor(102, 148, 255), bubble_text=WHITE,
)
# On glass nearly everything is a see-through layer of white or black, so the
# blurred colours behind the palette come through, as they do in Launchpad.
GLASS_DARK = Theme(
    dark=True, bg=QColor(38, 39, 44), panel=QColor(0, 0, 0, 14), field=QColor(255, 255, 255, 34),
    raised=QColor(255, 255, 255, 62), border=QColor(255, 255, 255, 60), text=QColor(252, 252, 254),
    subtext=QColor(255, 255, 255, 178), hover=QColor(255, 255, 255, 30), accent=QColor(140, 178, 255),
    accent_text=QColor(20, 24, 34), selected=QColor(255, 255, 255, 58), pad_line=QColor(255, 255, 255, 120),
    ink=WHITE, bubble=QColor(0, 0, 0, 14), bubble_text=WHITE, glass="regular", glass_dark=True,
)
GLASS_LIGHT = Theme(
    dark=False, bg=QColor(250, 250, 252), panel=QColor(255, 255, 255, 14), field=QColor(255, 255, 255, 108),
    raised=QColor(255, 255, 255, 205), border=QColor(0, 0, 0, 40), text=QColor(22, 22, 26),
    subtext=QColor(0, 0, 0, 150), hover=QColor(0, 0, 0, 18), accent=QColor(30, 96, 230), accent_text=WHITE,
    selected=QColor(0, 0, 0, 30), pad_line=QColor(0, 0, 0, 96), ink=QColor(22, 22, 26),
    bubble=QColor(255, 255, 255, 14), bubble_text=QColor(22, 22, 26), glass="regular", glass_dark=False,
)

# (setting, name in the menu); None is a separator
LOOKS = [
    ("glass-dark", "Liquid Glass · dark, like Launchpad"),
    ("glass-light", "Liquid Glass · light"),
    ("glass-clear", "Liquid Glass · clear"),
    None,
    ("solid-system", "Solid · match macOS"),
    ("solid-light", "Solid · light"),
    ("solid-dark", "Solid · dark"),
]
DEFAULT_LOOK = "glass-dark"
# (colour, name in the menu)
COLORS = [
    ("#1b2540", "Midnight"), ("#2f6df6", "Blue"), ("#7b4ef0", "Purple"), ("#e8437f", "Pink"),
    ("#e23b3b", "Red"), ("#f28a1c", "Orange"), ("#f4c430", "Yellow"), ("#2fa866", "Green"),
    ("#17a2a8", "Teal"), ("#5d6470", "Graphite"), ("#f3ead8", "Cream"),
]
STRENGTHS = [(25, "Light"), (50, "Medium"), (75, "Strong"), (100, "Solid")]
# Roughly how bright each kind of glass looks before any colour goes on it.
_GLASS_BRIGHTNESS = {"dark": 0.30, "light": 0.88, "clear": 0.45}


def brightness(c: QColor):
    """0 (black) to 1 (white), the way the eye sees it."""
    return (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255


def mix(a: QColor, b: QColor, amount):
    """`a` moved `amount` (0..1) of the way towards `b`."""
    return QColor(*(round(x + (y - x) * amount) for x, y in ((a.red(), b.red()), (a.green(), b.green()),
                                                              (a.blue(), b.blue()))))


def with_alpha(c: QColor, alpha):
    return QColor(c.red(), c.green(), c.blue(), max(0, min(255, int(alpha))))


def over(top: QColor, bottom: QColor):
    """One see-through colour that looks the same as `top` painted over `bottom`."""
    a, b = top.alphaF(), bottom.alphaF()
    alpha = a + b * (1 - a)
    if alpha <= 0:
        return QColor(0, 0, 0, 0)
    channel = lambda x, y: round((x * a + y * b * (1 - a)) / alpha)
    return QColor(channel(top.red(), bottom.red()), channel(top.green(), bottom.green()),
                  channel(top.blue(), bottom.blue()), max(1, round(255 * alpha)))


def parse_color(text):
    """A QColor for "#rrggbb", or None if there's no (valid) colour."""
    if not text or not isinstance(text, str):
        return None
    c = QColor(text)
    return QColor(c.red(), c.green(), c.blue()) if c.isValid() else None


def system_is_dark():
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def build(look=DEFAULT_LOOK, color="", strength=50, system_dark=None):
    """The colours for a look, optionally with your own background colour.

    look      one of LOOKS
    color     "#rrggbb", or "" to keep the look's own colours
    strength  how much of that colour goes over the glass, 0-100 (a solid look
              is always fully that colour)
    """
    kind, _, tone = (look or DEFAULT_LOOK).partition("-")
    custom = parse_color(color)
    if kind == "glass":
        tone = tone if tone in _GLASS_BRIGHTNESS else "dark"
        amount = max(0, min(100, int(strength))) / 100 if custom is not None else 0.0
        shown = _GLASS_BRIGHTNESS[tone]
        if custom is not None:
            shown += (brightness(custom) - shown) * amount
        t = GLASS_LIGHT if shown >= 0.6 else GLASS_DARK        # dark or light text, whichever reads better
        dim = QColor(0, 0, 0, 96) if tone == "clear" else t.panel     # clear glass needs dimming to stay readable
        style = dict(glass="clear" if tone == "clear" else "regular", glass_dark=tone != "light")
        if custom is None:
            return replace(t, panel=dim, bubble=dim, **style)
        tinted = over(with_alpha(custom, round(255 * amount)), dim)
        return replace(t, bg=mix(t.bg, custom, amount), panel=tinted, bubble=tinted, **style, **_neutral_accent(t))
    if tone == "light":
        t = LIGHT
    elif tone == "dark":
        t = DARK
    else:
        t = DARK if (system_is_dark() if system_dark is None else system_dark) else LIGHT
    if custom is None:
        return t
    t = DARK if brightness(custom) < 0.6 else LIGHT
    return replace(t, bg=custom, panel=custom, raised=custom, bubble=custom, bubble_text=t.text,
                   field=mix(custom, WHITE, 0.14) if t.dark else mix(custom, BLACK, 0.08), **_neutral_accent(t))


def _neutral_accent(t: Theme):
    """On a coloured background a blue highlight can vanish, so highlight in white or black instead."""
    if t.dark:
        return dict(accent=QColor(255, 255, 255, 235), accent_text=QColor(24, 24, 28),
                    selected=QColor(255, 255, 255, 58), border=QColor(255, 255, 255, 60))
    return dict(accent=QColor(0, 0, 0, 210), accent_text=WHITE, selected=QColor(0, 0, 0, 34),
                border=QColor(0, 0, 0, 46))


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
    p.setColor(QPalette.ColorRole.HighlightedText, t.accent_text)
    return p


def stylesheet(t: Theme):
    c = {k: _rgba(getattr(t, k)) for k in ("bg", "field", "raised", "border", "text", "subtext", "hover",
                                          "accent", "accent_text", "selected")}
    accent_soft = _rgba(with_alpha(t.accent, 40))
    return f"""
    QWidget {{ color: {c['text']}; font-size: 13px; }}
    QLabel#title {{ font-weight: 700; font-size: 13px; }}
    QLabel#subtle {{ color: {c['subtext']}; font-size: 11px; }}
    QLabel#name {{ font-weight: 600; }}
    QLabel#preview {{ font-size: 30px; }}
    QLabel#hint {{ color: {c['subtext']}; font-size: 12px; }}
    QLineEdit#search {{
        background: {c['field']}; border: 1px solid transparent; border-radius: 11px;
        padding: 6px 10px; font-size: 14px; selection-background-color: {c['accent']};
        selection-color: {c['accent_text']};
    }}
    QLineEdit#search:focus {{ border: 1px solid {c['accent']}; }}
    QWidget#segments {{ background: {c['field']}; border-radius: 11px; }}
    QPushButton#segment {{
        background: transparent; border: none; border-radius: 9px; padding: 5px 0px;
        font-weight: 600; color: {c['subtext']};
    }}
    QPushButton#segment:checked {{ background: {c['raised']}; color: {c['text']}; }}
    QPushButton#segment:hover:!checked {{ color: {c['text']}; }}
    QToolButton#header {{
        background: transparent; border: none; border-radius: 6px; padding: 2px;
        font-size: 15px; color: {c['subtext']}; min-width: 24px; min-height: 24px;
    }}
    QToolButton#header:hover {{ background: {c['hover']}; color: {c['text']}; }}
    QToolButton#header::menu-indicator {{ image: none; width: 0px; }}
    QToolButton#category {{
        background: {c['field']}; border: none; border-radius: 9px; padding: 4px 10px;
        font-weight: 600;
    }}
    QToolButton#category:hover {{ background: {c['hover']}; }}
    QToolButton#category::menu-indicator {{ image: none; width: 0px; }}
    QToolButton#tile {{
        background: {c['field']}; border: none; border-radius: 8px; padding: 2px; font-size: 15px;
    }}
    QToolButton#tile:hover {{ background: {c['hover']}; }}
    QPushButton#link:disabled {{ background: {c['field']}; color: {c['subtext']}; }}
    QPushButton#small {{
        background: {c['field']}; border: none; border-radius: 9px; padding: 4px 10px;
    }}
    QPushButton#small:hover {{ background: {c['hover']}; }}
    QPushButton#small:disabled {{ color: {c['subtext']}; }}
    QPushButton#link {{
        background: {c['accent']}; color: {c['accent_text']}; border: none; border-radius: 9px;
        padding: 4px 10px; font-weight: 600;
    }}
    QPushButton#key {{
        background: {c['field']}; border: 1px solid {c['border']}; border-radius: 9px;
        padding: 6px 12px; font-size: 14px; font-weight: 600; min-width: 150px;
    }}
    QPushButton#key:hover {{ background: {c['hover']}; }}
    QPushButton#key:checked {{ border: 1px solid {c['accent']}; background: {accent_soft}; }}
    QRadioButton {{ spacing: 6px; }}
    QFrame#banner {{ background: {accent_soft}; border-radius: 11px; }}
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
    QMenu::icon {{ left: 6px; }}
    QToolTip {{
        background: {c['bg']}; color: {c['text']}; border: 1px solid {c['border']};
        padding: 4px 6px; border-radius: 6px;
    }}
    """
