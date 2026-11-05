"""Handwritten symbol recognition that needs no training data.

How it works
------------
Every symbol the recognizer knows is rendered from a few fonts and thinned to a
one-pixel "skeleton" - roughly the path a pen would take (see ``glyphs.py``).
A drawing and a template are then compared as clouds of points, where every
point also remembers the direction of the stroke passing through it:

1. both are scaled into the same box, keeping a softened aspect ratio,
2. a cheap grid-of-directions descriptor shortlists plausible templates,
3. an oriented chamfer distance - how far each point lies from the nearest
   point of the other shape, measured both ways - ranks the shortlist.

When you pick a symbol after drawing it, your drawing is kept as an extra
template, so recognition adapts to your handwriting the more you use it.
"""

from __future__ import annotations

import numpy as np

STEP = 0.035          # spacing of resampled points; a drawing spans ~1 unit
ASPECT_EXP = 0.5      # 0 = stretch every shape to a square, 1 = keep aspect exactly
ORIENT_W = 0.25       # how much stroke direction counts compared to position
NEIGHBOR_R = 0.075    # neighbourhood used to estimate local stroke direction
TRUNC = 0.45          # cap per-point distances so one stray mark can't dominate
GRID = 7              # coarse descriptor: GRID x GRID cells x 5 direction channels
COARSE_KEEP = 260     # templates that survive the coarse stage
COARSE_W = 0.5        # weight of the coarse similarity in the final score
USER_WEIGHT = 0.8     # your own drawings count a little more than font templates
DOT_SIZE = 0.06       # drawings smaller than this (fraction of the pad) are dots
DOT_CHARS = ("·", "•", ".", "⋅", "∙", "°", "∘", "◦")


# --------------------------------------------------------------------------- geometry
def _norm_params(pts):
    """Centre and per-axis scale that map the points into the unit box.

    The long side of the bounding box spans 1; the short side spans
    ratio ** ASPECT_EXP, so thin shapes stay thin-ish without being fragile.
    """
    mn, mx = pts.min(axis=0), pts.max(axis=0)
    size = np.maximum(mx - mn, 1e-9)
    long_side = size.max()
    ratio = np.maximum(size / long_side, 1e-3)
    scale = ratio ** ASPECT_EXP / (ratio * long_side)
    return (mn + mx) / 2.0, scale


def _resample(stroke, step):
    """Evenly spaced points along one stroke (a single point for dots)."""
    if len(stroke) > 1:
        seg = np.hypot(*np.diff(stroke, axis=0).T)
        keep = np.concatenate([[True], seg > 1e-9])
        stroke = stroke[keep]
    if len(stroke) < 2:
        return stroke[:1]
    seg = np.hypot(*np.diff(stroke, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    if cum[-1] < step * 0.6:
        return stroke.mean(axis=0, keepdims=True)
    n = max(int(round(cum[-1] / step)), 1)
    t = np.linspace(0.0, cum[-1], n + 1)
    return np.stack([np.interp(t, cum, stroke[:, 0]), np.interp(t, cum, stroke[:, 1])], axis=1)


def _orientations(pts):
    """Local stroke direction as a doubled-angle vector (length = how line-like).

    Uses the covariance of each point's neighbourhood, so it works the same for
    ordered pen strokes and unordered skeleton pixels; crossings and dots come
    out near (0, 0), i.e. "no particular direction".
    """
    d2 = ((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1)
    w = (d2 <= NEIGHBOR_R * NEIGHBOR_R).astype(np.float64)
    cnt = w.sum(1)
    mean = (w @ pts) / cnt[:, None]
    dx = pts[None, :, 0] - mean[:, 0:1]
    dy = pts[None, :, 1] - mean[:, 1:2]
    sxx, syy, sxy = (w * dx * dx).sum(1), (w * dy * dy).sum(1), (w * dx * dy).sum(1)
    tr = sxx + syy + 1e-12
    u = np.stack([(sxx - syy) / tr, 2.0 * sxy / tr], axis=1)
    u[cnt < 2] = 0.0
    return u, cnt


def _features(pts):
    """(n, 4) array: x, y and the weighted direction vector.  Isolated points
    (dots) are repeated so that a dot matters about as much as a short dash."""
    u, cnt = _orientations(pts)
    feat = np.hstack([pts, ORIENT_W * u]).astype(np.float32)
    isolated = cnt <= 1
    if isolated.any():
        feat = np.vstack([feat, np.repeat(feat[isolated], 3, axis=0)])
    return feat


def drawing_features(strokes):
    """Features for a pen drawing: a list of strokes, each a list of (x, y)."""
    strokes = [np.asarray(s, dtype=np.float64).reshape(-1, 2) for s in strokes if len(s)]
    if not strokes:
        return None
    centre, scale = _norm_params(np.concatenate(strokes))
    pts = np.concatenate([_resample((s - centre) * scale, STEP) for s in strokes])
    return _features(pts)


def pixel_features(xs, ys):
    """Features for skeleton/contour pixels of a rendered glyph."""
    pts = np.stack([xs, ys], axis=1).astype(np.float64)
    centre, scale = _norm_params(pts)
    pts = (pts - centre) * scale
    # thin out to roughly STEP spacing so templates aren't needlessly dense
    keys = np.floor(pts / (STEP * 0.7)).astype(np.int64)
    _, first = np.unique(keys[:, 0] * 1_000_003 + keys[:, 1], return_index=True)
    return _features(pts[np.sort(first)])


def descriptor(feat):
    """Coarse, fixed-length summary: where the ink is and which way it runs."""
    pts = feat[:, :2]
    u = feat[:, 2:4] / ORIENT_W
    mag = np.clip(np.hypot(u[:, 0], u[:, 1]), 0.0, 1.0)
    ch = np.stack([np.maximum(u[:, 0], 0), np.maximum(u[:, 1], 0),
                   np.maximum(-u[:, 0], 0), np.maximum(-u[:, 1], 0), 1.0 - mag], axis=1)
    g = (np.clip(pts, -0.55, 0.55) + 0.55) / 1.1 * (GRID - 1)
    i0 = np.floor(g).astype(np.int64)
    fr = g - i0
    i1 = np.minimum(i0 + 1, GRID - 1)
    hist = np.zeros((GRID, GRID, 5))
    for ix, wx in ((i0[:, 0], 1 - fr[:, 0]), (i1[:, 0], fr[:, 0])):
        for iy, wy in ((i0[:, 1], 1 - fr[:, 1]), (i1[:, 1], fr[:, 1])):
            np.add.at(hist, (iy, ix), (wx * wy)[:, None] * ch)
    p = np.pad(hist, ((1, 1), (1, 1), (0, 0)), mode="edge")
    hist = (p[:-2] + 2 * p[1:-1] + p[2:])[:, 1:-1] / 4
    p = np.pad(hist, ((0, 0), (1, 1), (0, 0)), mode="edge")
    hist = (p[:, :-2] + 2 * p[:, 1:-1] + p[:, 2:]) / 4
    v = np.sqrt(hist.ravel())
    return (v / (np.linalg.norm(v) + 1e-9)).astype(np.float32)


# --------------------------------------------------------------------------- matcher
class _Templates:
    """A growable list of (label, features, descriptor)."""

    def __init__(self):
        self.labels, self.feats, self.descs = [], [], []

    def add(self, label, feat):
        self.labels.append(label)
        self.feats.append(feat)
        self.descs.append(descriptor(feat))

    def __len__(self):
        return len(self.labels)


class Recognizer:
    def __init__(self):
        self._fonts = _Templates()       # rendered from installed fonts
        self._pens = _Templates()        # hand-drawn reference shapes shipped with the app
        self._user = _Templates()        # your own drawings
        self._priors: dict[str, float] = {}
        self._dirty = True

    @property
    def ready(self):
        return len(self._fonts) > 0

    def set_font_templates(self, labels, feats):
        self._fonts = _Templates()
        for label, feat in zip(labels, feats):
            self._fonts.add(label, feat)
        self._dirty = True

    def add_pen_template(self, char, strokes):
        feat = drawing_features(strokes)
        if feat is not None and len(feat) >= 2:
            self._pens.add(char, feat)
            self._dirty = True

    def add_user_drawing(self, char, strokes):
        feat = drawing_features(strokes)
        if feat is not None and len(feat) >= 2:
            self._user.add(char, feat)
            self._dirty = True

    def clear_user_drawings(self):
        self._user = _Templates()
        self._dirty = True

    def set_priors(self, priors):
        """{char: multiplier}; below 1 favours a symbol, above 1 penalises it."""
        self._priors = dict(priors)
        self._dirty = True

    def _pack(self):
        if not self._dirty:
            return
        groups = [(self._fonts, 1.0), (self._pens, 1.0), (self._user, USER_WEIGHT)]
        labels = [l for g, _w in groups for l in g.labels]
        feats = [f for g, _w in groups for f in g.feats]
        descs = [d for g, _w in groups for d in g.descs]
        self._lab = np.array(labels, dtype=object)
        self._counts = np.array([len(f) for f in feats], dtype=np.int64)
        self._starts = np.concatenate([[0], np.cumsum(self._counts)[:-1]]).astype(np.int64)
        self._points = np.concatenate(feats) if feats else np.zeros((0, 4), np.float32)
        self._desc = np.stack(descs) if descs else np.zeros((0, GRID * GRID * 5), np.float32)
        weight = np.concatenate([np.full(len(g), w) for g, w in groups])
        self._w = weight * np.array([self._priors.get(l, 1.0) for l in labels])
        self._dirty = False

    def rank(self, strokes, pad_size=None, top=24):
        """Best matching characters for a drawing, best first."""
        strokes = [s for s in strokes if len(s)]
        if not strokes or not self.ready:
            return []
        if pad_size:
            pts = np.concatenate([np.asarray(s, float).reshape(-1, 2) for s in strokes])
            if (pts.max(0) - pts.min(0)).max() < DOT_SIZE * pad_size:
                return list(DOT_CHARS)
        feat = drawing_features(strokes)
        if feat is None:
            return []
        self._pack()
        sim = self._desc @ descriptor(feat)
        keep = min(COARSE_KEEP, len(sim))
        idx = np.argpartition(-sim, keep - 1)[:keep]
        dist = self._chamfer(feat, idx) + COARSE_W * (1.0 - sim[idx])
        dist *= self._w[idx]
        order = np.argsort(dist)
        out, seen = [], set()
        for i in order:
            ch = self._lab[idx[i]]
            if ch not in seen:
                seen.add(ch)
                out.append(ch)
                if len(out) >= top:
                    break
        return out

    def _chamfer(self, feat, idx):
        counts = self._counts[idx]
        offs = np.concatenate([[0], np.cumsum(counts)[:-1]])
        gather = np.arange(counts.sum()) + np.repeat(self._starts[idx] - offs, counts)
        pts = self._points[gather]
        d2 = (feat * feat).sum(1)[:, None] + (pts * pts).sum(1)[None, :] - 2.0 * (feat @ pts.T)
        np.maximum(d2, 0.0, out=d2)
        drawing_to_template = np.minimum(np.sqrt(np.minimum.reduceat(d2, offs, axis=1)), TRUNC).mean(0)
        template_to_drawing = np.add.reduceat(np.minimum(np.sqrt(d2.min(0)), TRUNC), offs) / counts
        return drawing_to_template + template_to_drawing
