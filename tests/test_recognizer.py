"""Draw common symbols with a wobbly 'hand' and check the recognizer finds them."""

import math
import os
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from symbolpad import glyphs, pen_shapes  # noqa: E402
from symbolpad.recognizer import Recognizer  # noqa: E402
from symbolpad.symbols import SymbolIndex  # noqa: E402


def wobbly(shape, rng):
    """A shape drawn by hand: tilted, stretched, shaky and placed somewhere on the pad."""
    angle = math.radians(rng.uniform(-6, 6))
    sx, sy = rng.uniform(0.8, 1.2, 2)
    rot = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    m = rot @ np.array([[sx, rng.uniform(-0.12, 0.12)], [0, sy]])
    strokes = []
    for s in pen_shapes.to_strokes(shape):
        t = np.linspace(0, 1, len(s))[:, None]
        s = s + 0.015 * np.sin(2 * np.pi * 1.3 * t + rng.uniform(0, 6.3, 2)) + rng.normal(0, 0.003, s.shape)
        strokes.append(((s - 0.5) @ m.T + 0.5) * 160 + 30)
    return strokes


class RecognizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        chars = SymbolIndex().drawable_chars()
        labels, feats = glyphs.templates_from_renders(glyphs.render_all(chars))
        cls.fonts_only = Recognizer()
        cls.fonts_only.set_font_templates(labels, feats)

    def test_font_templates_alone_find_common_symbols(self):
        rng = np.random.default_rng(7)
        symbols = "→⇒∫∑∞≤≠≈±÷∂∇∀∃∈⊂∪∅αβθλπσωΩ"
        hits = 0
        for ch in symbols:
            top = self.fonts_only.rank(wobbly(pen_shapes.SHAPES[ch], rng), pad_size=220, top=5)
            hits += ch in top
        self.assertGreaterEqual(hits / len(symbols), 0.85, f"only {hits}/{len(symbols)} in the top 5")

    def test_tiny_drawings_are_dots(self):
        self.assertEqual(self.fonts_only.rank([[(100, 100), (101, 101)]], pad_size=220)[0], "·")

    def test_learns_from_your_drawings(self):
        rec = Recognizer()
        rec.set_font_templates(self.fonts_only._fonts.labels, self.fonts_only._fonts.feats)
        squiggle = [[(20, 100), (60, 40), (100, 160), (140, 40), (180, 160), (220, 100)]]
        rec.add_user_drawing("ℵ", squiggle)            # "this squiggle is how I write aleph"
        self.assertEqual(rec.rank(squiggle, pad_size=240)[0], "ℵ")


if __name__ == "__main__":
    unittest.main()
