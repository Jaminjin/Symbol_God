"""Searchable index of symbols: the curated sets plus (almost) all of Unicode."""

from __future__ import annotations

import html.entities
import math
import re
import unicodedata
from dataclasses import dataclass

from . import symbol_data as data

# Huge blocks of ideographs/syllables that only clutter symbol search results.
_SKIP_PREFIXES = (
    "CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH", "TANGUT", "KHITAN SMALL SCRIPT",
    "NUSHU CHARACTER", "HANGUL SYLLABLE", "EGYPTIAN HIEROGLYPH", "CUNEIFORM", "ANATOLIAN HIEROGLYPH",
    "BAMUM", "YI SYLLABLE", "LINEAR A", "LINEAR B", "SIGNWRITING", "VARIATION SELECTOR", "TAG ",
    "BYZANTINE MUSICAL", "MEDEFAIDRIN", "DUPLOYAN", "MENDE KIKAKUI", "BRAILLE PATTERN",
    "SUTTON SIGNWRITING", "ZNAMENNY", "KAKTOVIK", "TODHRI", "GARAY", "SUNUWAR",
)
_SKIP_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp", "Zs", "Me"}
_COMBINING_BLOCKS = ((0x0300, 0x036F), (0x1AB0, 0x1AFF), (0x1DC0, 0x1DFF), (0x20D0, 0x20FF), (0xFE20, 0xFE2F))

# Blocks that are mostly useful symbols get a small ranking boost.
_USEFUL_BLOCKS = (
    (0x00A0, 0x00FF), (0x0370, 0x03FF), (0x2000, 0x206F), (0x2070, 0x209F), (0x20A0, 0x20CF),
    (0x2100, 0x218F), (0x2190, 0x23FF), (0x2500, 0x27FF), (0x2900, 0x2BFF), (0x1D400, 0x1D7FF),
)

# Words that say little about what a symbol looks like.
_GENERIC = {"SIGN", "SYMBOL", "MARK", "LETTER", "SMALL", "CAPITAL", "WITH", "AND", "OF", "THE",
            "DIGIT", "NUMBER", "FORM", "OPERATOR", "LATIN", "GREEK", "MATHEMATICAL", "BLACK", "WHITE"}

_CODEPOINT_RE = re.compile(r"^(?:u\+|0x|\\u|\\x|&#x)([0-9a-f]{1,6});?$|^([0-9a-f]{4,6})$", re.I)
_DECIMAL_RE = re.compile(r"^&#(\d{1,7});?$")


def is_combining(ch):
    return unicodedata.category(ch) in ("Mn", "Mc") and any(a <= ord(ch) <= b for a, b in _COMBINING_BLOCKS)


def display_text(ch):
    """What to draw for a character (combining marks sit on a dotted circle)."""
    return "◌" + ch if is_combining(ch) else ch


def code_of(ch):
    return "U+%04X" % ord(ch)


def _nice_name(name):
    return " ".join(w.capitalize() for w in name.split(" "))


@dataclass(slots=True)
class Symbol:
    char: str
    name: str          # display name, e.g. "Greek Small Letter Alpha"
    latex: tuple       # commands without the backslash
    keywords: tuple
    tier: int          # 3 = very common ... 0 = obscure
    hay: str           # " word word ... " (lowercase) for token matching
    phrases: str       # "|phrase|phrase|" (lowercase) for whole-query matching

    @property
    def code(self):
        return code_of(self.char)

    @property
    def display(self):
        return display_text(self.char)

    @property
    def mac_key(self):
        return data.MAC_KEYS.get(self.char, "")


class SymbolIndex:
    def __init__(self, include_all_unicode=True):
        self.keywords = data.keywords()
        self.latex = data.latex_commands()
        self.entities = {}
        for ent, val in html.entities.html5.items():
            if len(val) == 1 and ent.endswith(";"):
                self.entities.setdefault(val, []).append(ent[:-1])
        self.common = set(data.chars_of(data.COMMON))
        self.categories = []   # (key, title, icon, [chars])
        self.by_char: dict[str, Symbol] = {}
        self.symbols: list[Symbol] = []
        self.usage: dict[str, int] = {}

        for key, title, icon, chars in data.CATEGORIES:
            chars = [c for c in data.chars_of(chars) if self._add(c, tier=2)]
            self.categories.append((key, title, icon, list(dict.fromkeys(chars))))
        for ch in self.common:
            self._add(ch, tier=3)
        if include_all_unicode:
            self._add_all_unicode()
        self.symbols.sort(key=lambda s: ord(s.char))

    # ------------------------------------------------------------------ building
    def _add(self, ch, tier):
        sym = self.by_char.get(ch)
        if sym is not None:
            sym.tier = max(sym.tier, tier)
            return sym
        try:
            raw_name = unicodedata.name(ch)
        except (ValueError, TypeError):
            return None
        kws = tuple(self.keywords.get(ch, ()))
        latex = tuple(self.latex.get(ch, ()))
        entities = tuple(self.entities.get(ch, ()))
        words = set()
        for w in raw_name.lower().split():
            words.add(w)
            if "-" in w:
                words.update(p for p in w.split("-") if p)
        for phrase in kws:
            words.update(phrase.lower().split())
        words.update(c.lower() for c in latex)
        words.update(e.lower() for e in entities)
        phrases = {raw_name.lower(), *(k.lower() for k in kws), *(c.lower() for c in latex),
                   *(e.lower() for e in entities)}
        if is_combining(ch):
            tier = min(tier, 1)    # niche: never outrank ordinary symbols
        sym = Symbol(
            char=ch, name=_nice_name(raw_name), latex=latex, keywords=kws, tier=tier,
            hay=" " + " ".join(sorted(words)) + " ", phrases="|" + "|".join(sorted(phrases)) + "|",
        )
        self.by_char[ch] = sym
        self.symbols.append(sym)
        return sym

    def _add_all_unicode(self):
        for cp in range(0x20, 0x20000):
            ch = chr(cp)
            if ch in self.by_char:
                continue
            cat = unicodedata.category(ch)
            if cat in _SKIP_CATEGORIES:
                continue
            if cat in ("Mn", "Mc") and not is_combining(ch):
                continue
            name = unicodedata.name(ch, "")
            if not name or name.startswith(_SKIP_PREFIXES):
                continue
            tier = 1 if any(a <= cp <= b for a, b in _USEFUL_BLOCKS) else 0
            self._add(ch, tier)

    def hide(self, chars):
        """Leave out characters this Mac has no font for (they'd only show as boxes)."""
        hidden = set(chars)
        self.symbols = [s for s in self.symbols if s.char not in hidden]
        self.categories = [(k, t, i, [c for c in cs if c not in hidden]) for k, t, i, cs in self.categories]

    # ------------------------------------------------------------------ lookup
    def get(self, ch):
        return self.by_char.get(ch) or self._add(ch, tier=0)

    def category_chars(self, key):
        for k, _title, _icon, chars in self.categories:
            if k == key:
                return chars
        return []

    def drawable_chars(self):
        """Characters the handwriting recognizer should know about."""
        skip = {"scripts", "numbers", "accented", "combining", "punctuation", "mathletters"}
        chars = []
        for key, _t, _i, cs in self.categories:
            if key not in skip:
                chars.extend(cs)
        chars.extend(data.chars_of("— … • † ‡ § ¶ ¿ ¡ ‰ ½ ¼ ¾ ¬ ‖ ⁄ « »"))
        chars.extend("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
        chars.extend("!?#%&@*/\\()[]{}<>=+-~^|$")
        return list(dict.fromkeys(c for c in chars if not is_combining(c)))

    # ------------------------------------------------------------------ search
    def search(self, query, limit=600):
        q_raw = query.strip()
        if not q_raw:
            return []
        out = []

        direct = self._parse_codepoint(q_raw)
        if direct:
            out.append(direct)

        if q_raw.startswith("\\") and len(q_raw) > 1:
            out.extend(self._latex_search(q_raw[1:]))
            text = q_raw[1:]
        elif len(q_raw) == 1 and not (q_raw.isascii() and q_raw.isalnum()):
            # Typed/pasted a symbol: show it, then its relatives.
            out.append(self.get(q_raw))
            text = self._related_word(q_raw)
        elif len(q_raw) == 2 and is_combining(q_raw[1]):
            out.append(self.get(q_raw[1]))
            text = ""
        else:
            text = q_raw
        if text:
            out.extend(self._text_search(text))

        seen, result = set(), []
        for sym in out:
            if sym is not None and sym.char not in seen:
                seen.add(sym.char)
                result.append(sym)
                if len(result) >= limit:
                    break
        return result

    def _parse_codepoint(self, q):
        m = _CODEPOINT_RE.match(q)
        cp = None
        if m:
            digits = m.group(1) or m.group(2)
            if m.group(1) or any(c.isdigit() for c in digits):
                cp = int(digits, 16)
        else:
            m = _DECIMAL_RE.match(q)
            if m:
                cp = int(m.group(1))
        if cp is None or cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
            return None
        return self.get(chr(cp))

    def _latex_search(self, cmd):
        exact, prefix = [], []
        lc = cmd.lower()
        for sym in self.symbols:
            for c in sym.latex:
                if c == cmd:
                    exact.append((0, sym))
                elif c.lower() == lc:
                    exact.append((1, sym))
                elif c.lower().startswith(lc):
                    prefix.append((len(c), -sym.tier, sym))
        exact.sort(key=lambda t: t[0])
        prefix.sort(key=lambda t: (t[0], t[1]))
        return [s for _k, s in exact] + [t[2] for t in prefix]

    def _related_word(self, ch):
        try:
            words = unicodedata.name(ch).split()
        except ValueError:
            return ""
        for w in reversed(words):
            if w not in _GENERIC and len(w) > 2:
                return w.lower().rstrip("s") if w.endswith("S") and len(w) > 4 else w.lower()
        return ""

    def _text_search(self, text):
        q = text.lower()
        tokens = q.split()
        first = text[:1]
        scored = []
        for sym in self.symbols:
            hay = sym.hay
            score = 0.0
            weak = False
            for t in tokens:
                if f" {t} " in hay:
                    score += 3.0
                elif len(t) > 1 and f" {t}" in hay:
                    score += 2.0
                elif len(t) > 2 and t in hay:
                    score += 0.5
                    weak = True
                else:
                    break
            else:
                if len(q) > 1 and f"|{q}|" in sym.phrases:
                    score += 8.0
                if first.isupper() and "Capital" in sym.name:
                    score += 1.5
                elif first.islower() and " Small " in sym.name:
                    score += 0.6
                score += sym.tier * (0.6 if weak else 2.2) - len(sym.name) / 30.0
                n = self.usage.get(sym.char)
                if n:
                    score += min(4.0, 1.5 * math.log1p(n))
                scored.append((-score, ord(sym.char), sym))
        scored.sort(key=lambda t: (t[0], t[1]))
        return [s for _a, _b, s in scored]
