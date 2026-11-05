"""Render symbols from installed fonts and turn them into recognizer templates.

Rendering needs Qt (call it on the main thread); turning the bitmaps into
templates is pure numpy and can run in a worker thread.  The result is cached
on disk, so this work only happens on the very first launch.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QImage, QPainter, QPainterPath

from . import recognizer as rec

CACHE_VERSION = 3
SIZE = 56            # each glyph is rendered so its longest side is SIZE px
FONT_PX = 100
FONTS_PER_SYMBOL = 3
# Fonts that ship with macOS.  Several styles per symbol = more ways to match.
SYMBOL_FONTS = ("Arial Unicode MS", "STIX Two Math", "Apple Symbols", "Menlo", "Lucida Grande",
                "Helvetica Neue", "STIXGeneral")
LETTER_FONTS = ("Noteworthy", "Chalkboard SE", "Helvetica Neue", "Arial Unicode MS")
THICK_EM = 0.1       # strokes thicker than this (half-width, in em) are "filled shapes"


def _fonts_for(ch, families):
    order = LETTER_FONTS if ch.isascii() and ch.isalnum() else SYMBOL_FONTS
    picked = []
    for family in order:
        if family not in families:
            continue
        font = QFont(family)
        font.setPixelSize(FONT_PX)
        font.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
        if QFontMetricsF(font).inFontUcs4(ord(ch)):
            picked.append(font)
            if len(picked) == FONTS_PER_SYMBOL:
                break
    if not picked:                      # let Qt find any font that has it
        font = QFont()
        font.setPixelSize(FONT_PX)
        picked.append(font)
    return picked


def render_glyph(ch, font):
    """Bitmap of one glyph scaled so its longest side is SIZE px.

    Returns (mask, longest_side_in_em, (width_em, height_em)) or None.
    """
    path = QPainterPath()
    path.addText(0, 0, font, ch)
    r = path.boundingRect()
    longest = max(r.width(), r.height())
    if longest <= 0.5:
        return None
    s = (SIZE - 1) / longest
    w, h = int(np.ceil(r.width() * s)) + 5, int(np.ceil(r.height() * s)) + 5
    img = QImage(w, h, QImage.Format.Format_Grayscale8)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(2.5, 2.5)
    p.scale(s, s)
    p.translate(-r.left(), -r.top())
    p.fillPath(path, QColor(255, 255, 255))
    p.end()
    buf = np.frombuffer(img.constBits(), np.uint8, count=img.bytesPerLine() * h)
    mask = buf.reshape(h, img.bytesPerLine())[:, :w] > 96
    if not mask.any():
        return None
    return mask, longest / FONT_PX, (r.width() / FONT_PX, r.height() / FONT_PX)


def render_all(chars):
    """[(char, mask, longest_em, (w_em, h_em)), ...] for every font of every char."""
    families = set(QFontDatabase.families())
    records = []
    for ch in chars:
        for font in _fonts_for(ch, families):
            r = render_glyph(ch, font)
            if r is not None:
                records.append((ch, *r))
    return records


def unrenderable(chars, font):
    """Characters Qt draws as the striped "no glyph" box (or as nothing) in `font`.

    Some fonts claim characters they can't really draw, so this checks what
    actually comes out.  Main thread only; about 1 s per 20,000 characters.
    """
    from PySide6.QtCore import QRect, Qt
    from .symbols import display_text

    font = QFont(font)
    font.setPixelSize(22)
    img = QImage(40, 40, QImage.Format.Format_Grayscale8)

    def digest(text):
        img.fill(0)
        p = QPainter(img)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRect(0, 0, 40, 40), Qt.AlignmentFlag.AlignCenter, text)
        p.end()
        return hashlib.md5(bytes(img.constBits())).digest()

    bad = {digest("͸"), digest("\U0010FFFD"), digest("")}    # unassigned, never assigned, blank
    return [c for c in chars if digest(display_text(c)) in bad]


# --------------------------------------------------------------------------- bitmaps
def _stack(masks, size=SIZE + 8):
    out = np.zeros((len(masks), size, size), dtype=bool)
    for i, m in enumerate(masks):
        h, w = m.shape
        out[i, :h, :w] = m[:size, :size]
    return out


def _erode(b):
    p = np.pad(b, ((0, 0), (1, 1), (1, 1)))
    return b & p[:, :-2, 1:-1] & p[:, 2:, 1:-1] & p[:, 1:-1, :-2] & p[:, 1:-1, 2:]


def erosion_depth(stack, limit=30):
    """How many erosions each bitmap survives (= half its thickest stroke)."""
    depth = np.zeros(len(stack), dtype=np.int64)
    cur = stack.copy()
    for d in range(1, limit + 1):
        cur = _erode(cur)
        alive = cur.any(axis=(1, 2))
        depth[alive] = d
        if not alive.any():
            break
    return depth


def thin(stack):
    """Zhang-Suen thinning, vectorised over a batch of bitmaps."""
    img = stack.copy()
    while True:
        changed = False
        for step in (0, 1):
            p = np.pad(img, ((0, 0), (1, 1), (1, 1)))
            n, ne, e, se = p[:, :-2, 1:-1], p[:, :-2, 2:], p[:, 1:-1, 2:], p[:, 2:, 2:]
            s, sw, w, nw = p[:, 2:, 1:-1], p[:, 2:, :-2], p[:, 1:-1, :-2], p[:, :-2, :-2]
            ring = (n, ne, e, se, s, sw, w, nw, n)
            count = sum(x.astype(np.uint8) for x in ring[:8])
            transitions = sum((~ring[i] & ring[i + 1]).astype(np.uint8) for i in range(8))
            if step == 0:
                cond = ~(n & e & s) & ~(e & s & w)
            else:
                cond = ~(n & e & w) & ~(n & s & w)
            kill = img & (count >= 2) & (count <= 6) & (transitions == 1) & cond
            if kill.any():
                img &= ~kill
                changed = True
        if not changed:
            return img


def templates_from_renders(records):
    """Turn rendered glyphs into recognizer features.  Pure numpy."""
    keep = []
    for rec_ in records:
        ch, mask, longest, (w_em, h_em) = rec_
        aspect = (w_em + 1e-6) / (h_em + 1e-6)
        if longest < 0.17 and 0.4 < aspect < 2.5:
            continue                       # dots: handled by the size check instead
        keep.append(rec_)
    if not keep:
        return [], []
    stack = _stack([r[1] for r in keep])
    depth = erosion_depth(stack)
    depth_em = depth * np.array([r[2] for r in keep]) / (SIZE - 1)
    thick = depth_em >= THICK_EM

    pixels = np.zeros_like(stack)
    pixels[thick] = stack[thick] & ~_erode(stack[thick])          # outline of filled shapes
    thin_idx = np.flatnonzero(~thick)
    thin_idx = thin_idx[np.argsort(depth[thin_idx])]               # similar thickness together
    for start in range(0, len(thin_idx), 256):
        chunk = thin_idx[start:start + 256]
        pixels[chunk] = thin(stack[chunk])

    labels, feats, descs = [], [], []
    for i, (ch, *_rest) in enumerate(keep):
        ys, xs = np.nonzero(pixels[i])
        if len(xs) < 2:
            continue
        f = rec.pixel_features(xs, ys)
        d = rec.descriptor(f)
        if any(lab == ch and float(dd @ d) > 0.985 for lab, dd in zip(labels[-3:], descs[-3:])):
            continue                       # this font's glyph looks like one we already have
        labels.append(ch)
        feats.append(f)
        descs.append(d)
    return labels, feats


# --------------------------------------------------------------------------- cache
def cache_key(chars):
    families = sorted(set(QFontDatabase.families()) & set(SYMBOL_FONTS + LETTER_FONTS))
    params = (CACHE_VERSION, rec.STEP, rec.ASPECT_EXP, rec.ORIENT_W, rec.NEIGHBOR_R, SIZE, THICK_EM)
    raw = repr((params, families, "".join(chars))).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def load_cache(path: Path, key):
    try:
        with np.load(path, allow_pickle=False) as z:
            if str(z["key"]) != key:
                return None
            counts = z["counts"]
            points = z["points"]
            labels = [str(x) for x in z["labels"]]
    except (OSError, KeyError, ValueError):
        return None
    feats = np.split(points, np.cumsum(counts)[:-1])
    return labels, feats


def save_cache(path: Path, key, labels, feats):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, key=np.array(key), labels=np.array(labels),
                        counts=np.array([len(f) for f in feats]), points=np.concatenate(feats))
    tmp.replace(path)
