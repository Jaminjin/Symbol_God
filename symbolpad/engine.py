"""Owns the drawing recognizer: builds (or loads) templates and learns from your picks."""

from __future__ import annotations

import threading
import traceback

from PySide6.QtCore import QObject, Signal

from . import glyphs, pen_shapes
from .recognizer import Recognizer

# Ranking nudges: common math symbols win ties, plain letters/digits lose them.
PRIOR_COMMON, PRIOR_CURATED, PRIOR_LETTER = 0.9, 0.96, 1.08


class DrawingEngine(QObject):
    ready = Signal()
    _built = Signal(object, object, str)

    def __init__(self, index, store):
        super().__init__()
        self.index = index
        self.store = store
        self.recognizer = Recognizer()
        self._built.connect(self._on_built)
        self.chars = index.drawable_chars()
        self.recognizer.set_priors(self._priors())
        for ch, shape in pen_shapes.SHAPES.items():
            self.recognizer.add_pen_template(ch, pen_shapes.to_strokes(shape))
        for ch, drawings in store.drawings.items():
            for strokes in drawings:
                self.recognizer.add_user_drawing(ch, strokes)

    @property
    def is_ready(self):
        return self.recognizer.ready

    def _priors(self):
        priors = {}
        for ch in self.chars:
            sym = self.index.by_char.get(ch)
            if ch.isascii() and ch.isalnum():
                priors[ch] = PRIOR_LETTER
            elif sym is not None and sym.tier >= 3:
                priors[ch] = PRIOR_COMMON
            elif sym is not None and sym.tier == 2:
                priors[ch] = PRIOR_CURATED
        return priors

    def start(self):
        """Load cached templates, or render fonts now and process them in the background."""
        key = glyphs.cache_key(self.chars)
        cached = glyphs.load_cache(self.store.cache_path, key)
        if cached is not None:
            self.recognizer.set_font_templates(*cached)
            self.ready.emit()
            return
        records = glyphs.render_all(self.chars)          # Qt rendering: main thread, ~0.3 s
        threading.Thread(target=self._build, args=(records, key), daemon=True).start()

    def _build(self, records, key):
        try:
            labels, feats = glyphs.templates_from_renders(records)
            glyphs.save_cache(self.store.cache_path, key, labels, feats)
        except Exception:
            traceback.print_exc()
            return
        self._built.emit(labels, feats, key)

    def _on_built(self, labels, feats, _key):
        self.recognizer.set_font_templates(labels, feats)
        self.ready.emit()

    def rank(self, strokes, pad_size, top=24):
        return self.recognizer.rank(strokes, pad_size=pad_size, top=top)

    def learn(self, ch, strokes, pad_size):
        """Keep this drawing as an example of `ch` (in 0..1 pad coordinates)."""
        if not strokes:
            return
        scaled = [[(x / pad_size, y / pad_size) for x, y in s] for s in strokes]
        self.recognizer.add_user_drawing(ch, scaled)
        self.store.add_drawing(ch, scaled)

    def forget_drawings(self):
        self.recognizer.clear_user_drawings()
        self.store.clear_drawings()
