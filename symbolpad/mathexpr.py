"""Maths typed on one line (6^2, Cl_2, (a+b)/c, sqrt(x)) turned into built-up maths.

`parse` reads the line into a small tree.  `to_mathml` writes that tree as MathML, which Word turns
into a real equation when it's pasted; `to_text` writes it with ordinary characters (6², Cl₂, ½)
for everywhere else, and says whether those characters show it exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from .symbol_data import latex_commands

HOLE = "□"          # an empty slot, waiting to be filled in


# --------------------------------------------------------------------------- the tree
@dataclass
class Sym:
    text: str
    kind: str       # "num", "id", "op", "text", "fn" (sin, lim), "big" (∑, ∫) or "hole"


@dataclass
class Row:
    items: list = field(default_factory=list)


@dataclass
class Script:       # x², x₂
    base: object
    sub: object = None
    sup: object = None


@dataclass
class Stack:        # something written right under or over the base: sum limits, lim, labelled arrows
    base: object
    under: object = None
    over: object = None


@dataclass
class Frac:
    num: object
    den: object
    bar: bool = True


@dataclass
class Root:
    body: object
    degree: object = None


@dataclass
class Fence:        # brackets that grow with what's inside
    open: str
    close: str
    body: object


@dataclass
class Accent:
    body: object
    mark: str       # a key of ACCENTS


@dataclass
class Matrix:
    rows: list
    open: str = ""
    close: str = ""
    align: str = "center"


def hole():
    return Sym(HOLE, "hole")


# --------------------------------------------------------------------------- words it knows
FUNCTIONS = ("arcsin arccos arctan sinh cosh tanh coth sech csch sin cos tan csc sec cot "
             "log ln lg exp det gcd lcm").split()
LIMIT_FUNCTIONS = "limsup liminf lim max min".split()       # what's under them is written underneath
GREEK = dict(alpha="α", beta="β", gamma="γ", delta="δ", epsilon="ε", zeta="ζ", eta="η", theta="θ",
             iota="ι", kappa="κ", lambda_="λ", mu="μ", nu="ν", xi="ξ", pi="π", rho="ρ", sigma="σ",
             tau="τ", upsilon="υ", phi="φ", chi="χ", psi="ψ", omega="ω", Gamma="Γ", Delta="Δ",
             Theta="Θ", Lambda="Λ", Xi="Ξ", Pi="Π", Sigma="Σ", Phi="Φ", Psi="Ψ", Omega="Ω")
GREEK["lambda"] = GREEK.pop("lambda_")
WORD_SYMBOLS = dict(GREEK, inf="∞", infinity="∞", oo="∞", partial="∂", nabla="∇", hbar="ℏ",
                    times="×", cdot="·", degree="°")
BIG = dict(int="∫", iint="∬", iiint="∭", oint="∮", sum="∑", prod="∏", bigcup="⋃", bigcap="⋂")
STACKING_BIG = "∑∏∐⋃⋂⋁⋀⨁⨂"          # limits go above and below these; beside integrals
BIG_CHARS = "∫∬∭∮∯∰" + STACKING_BIG
# name: (the mark in MathML, the combining character for plain text, drawn under?)
ACCENTS = {
    "hat": ("^", "̂", False), "bar": ("¯", "̄", False), "vec": ("→", "⃗", False),
    "dot": ("˙", "̇", False), "ddot": ("¨", "̈", False), "tilde": ("~", "̃", False),
    "overline": ("¯", "̅", False), "underline": ("_", "̲", True),
}
MATRICES = {"matrix": ("", ""), "pmatrix": ("(", ")"), "bmatrix": ("[", "]"), "vmatrix": ("|", "|")}
WRAPPERS = {"abs": ("|", "|"), "norm": ("‖", "‖"), "floor": ("⌊", "⌋"), "ceil": ("⌈", "⌉")}
ALWAYS_COMMANDS = ("sqrt", "cbrt", "root")                   # the rest only count when ( or { follows
COMMANDS = ALWAYS_COMMANDS + ("frac", "binom", "over", "under", "cases") + tuple(ACCENTS) + tuple(MATRICES) \
    + tuple(WRAPPERS)
ROOT_CHARS = {"√": None, "∛": "3", "∜": "4"}
OPERATORS = [("<=>", "⇔"), ("<->", "↔"), ("...", "…"), ("->", "→"), ("=>", "⇒"), ("<=", "≤"), (">=", "≥"),
             ("!=", "≠"), ("~=", "≈"), ("~~", "≈"), ("+-", "±"), ("-+", "∓"), (":=", "≔"), ("||", "‖"),
             ("*", "×"), ("-", "−"), ("'", "′")]
OPENERS = {"(": ")", "[": "]", "\\{": "\\}", "⌊": "⌋", "⌈": "⌉", "⟨": "⟩"}
CLOSERS = tuple(OPENERS.values())
RELATIONS = set("=<>≤≥≠≈≡∼≅∝→←↔⇒⇔⇌∈∉⊂⊆≔")
BINARY = set("+−±∓×·÷")

_WORDS = {}
for _w in FUNCTIONS:
    _WORDS[_w] = ("fn", _w)
for _w in LIMIT_FUNCTIONS:
    _WORDS[_w] = ("fn", _w)
for _w, _c in WORD_SYMBOLS.items():
    _WORDS[_w] = ("id" if _c.isalpha() else "op", _c)
for _w, _c in BIG.items():
    _WORDS[_w] = ("big", _c)
for _w in COMMANDS:
    _WORDS[_w] = ("cmd", _w)
_LONGEST_WORD = max(map(len, _WORDS))
_NUMBER = re.compile(r"\d+(?:\.\d+)?|\.\d+")
_LATEX_NAME = re.compile(r"\\([A-Za-z]+)")
_LATEX = None


def _latex(name):
    global _LATEX
    if _LATEX is None:
        _LATEX = latex_commands()
    return _LATEX.get(name)


def _char_token(ch):
    if ch == HOLE:
        return "hole", ch
    if ch in BIG_CHARS:
        return "big", ch
    if ch in ROOT_CHARS:
        return "cmd", ch
    if ch in "⌊⌈⟨⌋⌉⟩‖":
        return "p", ch
    return ("id" if ch.isalpha() else "op"), ch


def tokenize(text):
    tokens, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            while i < n and text[i].isspace():
                i += 1
            tokens.append(("sp", " "))
            continue
        m = _NUMBER.match(text, i)
        if m:
            tokens.append(("num", m.group()))
            i = m.end()
            continue
        if ch == '"':
            end = text.find('"', i + 1)
            end = n if end < 0 else end
            tokens.append(("text", text[i + 1:end]))
            i = end + 1
            continue
        if ch == "\\":
            if text[i:i + 2] in ("\\{", "\\}"):
                tokens.append(("p", text[i:i + 2]))
                i += 2
                continue
            m = _LATEX_NAME.match(text, i)
            if m:
                name = m.group(1)
                if name in _WORDS:
                    tokens.append(_WORDS[name])
                elif _latex(name):
                    tokens.append(_char_token(_latex(name)))
                else:
                    tokens.append(("text", name))
                i = m.end()
                continue
            i += 1
            continue
        if ch.isascii() and ch.isalpha():
            for size in range(min(_LONGEST_WORD, n - i), 1, -1):
                word = text[i:i + size]
                token = _WORDS.get(word)
                if token is None or not word.isalpha():
                    continue
                if token[0] == "cmd" and word not in ALWAYS_COMMANDS and text[i + size:i + size + 1] not in ("(", "{"):
                    continue
                tokens.append(token)
                i += size
                break
            else:
                tokens.append(("id", ch))
                i += 1
            continue
        for typed, shown in OPERATORS:
            if text.startswith(typed, i):
                tokens.append(_char_token(shown))
                i += len(typed)
                break
        else:
            tokens.append(("p", ch) if ch in "^_/()[]{}|" else _char_token(ch))
            i += 1
    return tokens


# --------------------------------------------------------------------------- reading
def _row(items):
    return items[0] if len(items) == 1 else Row(items)


def _unwrap(node):
    """(a+b)/c shows as a+b over c: round brackets used only for grouping disappear."""
    if isinstance(node, Fence) and node.open == "(" and node.close == ")":
        return node.body
    return node


def _base_sym(node):
    while isinstance(node, (Script, Stack)):
        node = node.base
    return node if isinstance(node, Sym) else None


def _is_kind(node, kind):
    sym = _base_sym(node)
    return sym is not None and sym.kind == kind


def _is_boundary(node):
    return node is None or (isinstance(node, Sym) and node.kind == "op" and node.text not in "!′°%") \
        or _is_kind(node, "big")


def _shown(bracket):
    return bracket.lstrip("\\")


class _Parser:
    def __init__(self, tokens):
        self.tokens, self.i = tokens, 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else ("end", "")

    def take(self):
        token = self.peek()
        self.i += 1
        return token

    def stops_here(self, stops):
        kind, value = self.peek()
        return kind == "end" or (kind in ("p", "op") and value in stops)

    def skip_spaces(self):
        while self.peek()[0] == "sp":
            self.i += 1

    def row(self, stops=()):
        items = []                                  # None marks where a space was typed
        while not self.stops_here(stops):
            kind, value = self.peek()
            if kind == "sp":
                self.i += 1
                items.append(None)
            elif (kind, value) == ("p", "/"):
                self.i += 1
                num = self._operand_before(items)
                den = self._operand_after(stops)
                items.append(Frac(_unwrap(num), _unwrap(den)))
            else:
                items.append(self.scripted(stops))
        return _row([item for item in items if item is not None])

    @staticmethod
    def _operand_before(items):
        while items and items[-1] is None:
            items.pop()
        run = []
        while items and not _is_boundary(items[-1]):
            run.insert(0, items.pop())
        return _row(run) if run else hole()

    def _operand_after(self, stops):
        self.skip_spaces()
        run = []
        kind, value = self.peek()
        if kind == "op" and value in "−+±∓":
            run.append(Sym(self.take()[1], "op"))
        while not self.stops_here(stops):
            kind, value = self.peek()
            if kind == "op" or (kind, value) == ("p", "/"):
                break
            if kind == "sp":
                if run and _is_kind(run[-1], "fn"):         # 1/sin x keeps the x
                    self.skip_spaces()
                    continue
                break
            run.append(self.scripted(stops))
        return _row(run) if run and not (len(run) == 1 and _is_boundary(run[0])) else \
            (Row(run + [hole()]) if run else hole())

    def scripted(self, stops=()):
        base = self.atom(stops)
        sub = sup = None
        while self.peek()[0] == "p" and self.peek()[1] in ("^", "_"):
            which = self.take()[1]
            arg = self.script_arg(stops)
            if which == "^":
                sup = arg if sup is None else Script(sup, sup=arg)
            else:
                sub = arg if sub is None else Script(sub, sub=arg)
        if sub is None and sup is None:
            return base
        if isinstance(base, Sym) and ((base.kind == "big" and base.text in STACKING_BIG)
                                      or (base.kind == "fn" and base.text in LIMIT_FUNCTIONS)):
            return Stack(base, under=sub, over=sup)
        return Script(base, sub, sup)

    def script_arg(self, stops):
        kind, value = self.peek()
        if kind == "sp" or self.stops_here(stops) or (kind == "p" and value in ("^", "_", "/")):
            return hole()
        if (kind, value) == ("p", "("):
            return _unwrap(self.atom(stops))
        if kind == "op" and value in "−+±∓":
            self.i += 1
            if self.peek()[0] in ("sp", "end") or self.stops_here(stops):
                return Sym(value, "op")
            return Row([Sym(value, "op"), self.atom(stops)])
        return self.atom(stops)

    def atom(self, stops=()):
        kind, value = self.take()
        if kind in ("num", "id", "op", "text", "fn", "big", "hole"):
            return Sym(value, kind)
        if kind == "cmd":
            return self.command(value, stops)
        if kind == "p":
            if value in OPENERS:
                body = self.row(CLOSERS)
                close = self.take()[1] or OPENERS[value]
                return Fence(_shown(value), _shown(close), body)
            if value == "{":
                body = self.row(("}",))
                self.i += 1
                return body if isinstance(body, Row) else Row([body])
            if value in ("|", "‖"):
                body = self.row((value,))
                self.i += 1
                return Fence(value, value, body)
            if value in ("^", "_"):
                self.i -= 1                         # a script with nothing in front of it
                return hole()
        return Sym(_shown(value), "op") if kind != "end" else hole()

    def args(self, count, stops=()):
        out = []
        inner = (")",) if count == 1 else (",", ";", ")")
        while len(out) < count:
            kind, value = self.peek()
            if (kind, value) == ("p", "("):
                self.i += 1
                while True:
                    out.append(self.row(inner))
                    if self.take()[1] in (")", ""):
                        break
            elif (kind, value) == ("p", "{"):
                out.append(self.atom(stops))
            elif not out and kind == "sp":
                self.skip_spaces()
                if self.stops_here(stops):
                    break
                out.append(self.scripted(stops))
            elif not out and not self.stops_here(stops) and not (kind == "p" and value in ("^", "_", "/")):
                out.append(self.scripted(stops))
            else:
                break
        out = [arg.items[0] if isinstance(arg, Row) and len(arg.items) == 1 else
               (hole() if isinstance(arg, Row) and not arg.items else arg) for arg in out]
        return (out + [hole()] * count)[:count]

    def grid(self):
        if self.peek() != ("p", "("):
            return [[hole()]]
        self.i += 1
        rows, cells = [], []
        while True:
            cell = self.row((",", ";", ")"))
            cells.append(hole() if isinstance(cell, Row) and not cell.items else cell)
            end = self.take()[1]
            if end != ",":
                rows.append(cells)
                cells = []
            if end in (")", ""):
                break
        width = max(map(len, rows))
        return [cells + [hole() for _ in range(width - len(cells))] for cells in rows]

    def command(self, name, stops):
        if name in ROOT_CHARS or name in ("sqrt", "cbrt"):
            degree = "3" if name == "cbrt" else ROOT_CHARS.get(name)
            return Root(self.args(1, stops)[0], Sym(degree, "num") if degree else None)
        if name == "root":
            degree, body = self.args(2, stops)
            return Root(body, degree)
        if name == "frac":
            return Frac(*self.args(2, stops))
        if name == "binom":
            return Fence("(", ")", Frac(*self.args(2, stops), bar=False))
        if name in ("over", "under"):
            base, label = self.args(2, stops)
            return Stack(base, over=label) if name == "over" else Stack(base, under=label)
        if name in ACCENTS:
            return Accent(self.args(1, stops)[0], name)
        if name in WRAPPERS:
            return Fence(*WRAPPERS[name], self.args(1, stops)[0])
        if name == "cases":
            return Matrix(self.grid(), "{", "", "left")
        return Matrix(self.grid(), *MATRICES[name])


def parse(text):
    """The tree for a line of typed maths.  Never fails: anything unfinished gets an empty slot."""
    return _Parser(tokenize(text.strip())).row()


def is_empty(node):
    return isinstance(node, Row) and not node.items


def has_holes(node):
    if isinstance(node, Sym):
        return node.kind == "hole"
    if isinstance(node, Row):
        return any(has_holes(item) for item in node.items)
    if isinstance(node, Matrix):
        return any(has_holes(cell) for cells in node.rows for cell in cells)
    return any(has_holes(part) for part in vars(node).values() if part is not None and not isinstance(part, (str, bool)))


# --------------------------------------------------------------------------- MathML, for Word
_APPLY = "<mo>&#x2061;</mo>"       # the invisible "function of" sign; it makes Word build sin, lim and friends


def _mrow(node):
    if node is None:
        return "<mrow/>"
    if isinstance(node, Row):
        return f"<mrow>{_ml_items(node.items)}</mrow>"
    return _ml(node)


def _ml_items(items):
    out, i = [], 0
    while i < len(items):
        item = items[i]
        if _is_kind(item, "fn") and i + 1 < len(items):
            j = i + 2
            if not isinstance(items[i + 1], Fence):
                while j < len(items) and not _is_boundary(items[j]) and not _is_kind(items[j], "fn"):
                    j += 1
            out.append(f"<mrow>{_ml(item)}{_APPLY}<mrow>{_ml_items(items[i + 1:j])}</mrow></mrow>")
            i = j
        elif _is_kind(item, "big") and i + 1 < len(items):
            j = i + 1
            while j < len(items) and not (isinstance(items[j], Sym) and items[j].kind == "op"
                                          and items[j].text in RELATIONS | set("+−±∓,")):
                j += 1
            j = max(j, i + 2)
            out.append(f"<mrow>{_ml(item)}<mrow>{_ml_items(items[i + 1:j])}</mrow></mrow>")
            i = j
        else:
            out.append(_ml(item))
            i += 1
    return "".join(out)


def _ml(node):
    if isinstance(node, Sym):
        text = escape(node.text)
        if node.kind == "hole":
            return "<mrow/>"
        tag = {"num": "mn", "id": "mi", "fn": "mi", "text": "mtext"}.get(node.kind, "mo")
        if node.kind == "fn":
            return f'<mi mathvariant="normal">{text}</mi>'
        return f"<{tag}>{text}</{tag}>"
    if isinstance(node, Row):
        return _mrow(node)
    if isinstance(node, Script):
        if node.sub is not None and node.sup is not None:
            return f"<msubsup>{_mrow(node.base)}{_mrow(node.sub)}{_mrow(node.sup)}</msubsup>"
        if node.sub is not None:
            return f"<msub>{_mrow(node.base)}{_mrow(node.sub)}</msub>"
        return f"<msup>{_mrow(node.base)}{_mrow(node.sup)}</msup>"
    if isinstance(node, Stack):
        if node.under is not None and node.over is not None:
            return f"<munderover>{_mrow(node.base)}{_mrow(node.under)}{_mrow(node.over)}</munderover>"
        if node.under is not None:
            return f"<munder>{_mrow(node.base)}{_mrow(node.under)}</munder>"
        return f"<mover>{_mrow(node.base)}{_mrow(node.over)}</mover>"
    if isinstance(node, Frac):
        bar = "" if node.bar else ' linethickness="0"'
        return f"<mfrac{bar}>{_mrow(node.num)}{_mrow(node.den)}</mfrac>"
    if isinstance(node, Root):
        if node.degree is None:
            return f"<msqrt>{_mrow(node.body)}</msqrt>"
        return f"<mroot>{_mrow(node.body)}{_mrow(node.degree)}</mroot>"
    if isinstance(node, Fence):
        return (f'<mfenced open="{escape(node.open)}" close="{escape(node.close)}" separators="">'
                f"{_mrow(node.body)}</mfenced>")
    if isinstance(node, Accent):
        mark, _combining, under = ACCENTS[node.mark]
        if node.mark in ("overline", "underline"):      # written this way, Word draws a bar the full width
            tag = "munder" if under else "mover"
            return f'<{tag}>{_mrow(node.body)}<mo stretchy="true">{mark}</mo></{tag}>'
        return f'<mover accent="true">{_mrow(node.body)}<mo>{escape(mark)}</mo></mover>'
    if isinstance(node, Matrix):
        align = ' columnalign="left"' if node.align == "left" else ""
        rows = "".join("<mtr>" + "".join(f"<mtd>{_mrow(cell)}</mtd>" for cell in cells) + "</mtr>"
                       for cells in node.rows)
        table = f"<mtable{align}>{rows}</mtable>"
        if node.open or node.close:
            return f'<mfenced open="{node.open}" close="{node.close}" separators="">{table}</mfenced>'
        return table
    raise TypeError(node)


def to_mathml(node):
    body = _ml_items(node.items) if isinstance(node, Row) else _ml(node)
    return f'<math xmlns="http://www.w3.org/1998/Math/MathML">{body}</math>'


# --------------------------------------------------------------------------- ordinary characters
SUPERSCRIPTS = dict(zip("0123456789+-−=()abcdefghijklmnoprstuvwxyzABDEGHIJKLMNOPRTUVWβγδθφχ",
                        "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂᵝᵞᵟᶿᵠᵡ"))
SUBSCRIPTS = dict(zip("0123456789+-−=()aehijklmnoprstuvxβγρφχ",
                      "₀₁₂₃₄₅₆₇₈₉₊₋₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓᵦᵧᵨᵩᵪ"))
FRACTIONS = {"1/2": "½", "1/3": "⅓", "2/3": "⅔", "1/4": "¼", "3/4": "¾", "1/5": "⅕", "2/5": "⅖",
             "3/5": "⅗", "4/5": "⅘", "1/6": "⅙", "5/6": "⅚", "1/7": "⅐", "1/8": "⅛", "3/8": "⅜",
             "5/8": "⅝", "7/8": "⅞", "1/9": "⅑", "1/10": "⅒"}


def _flat(node):
    """The characters of something simple enough to shrink into a superscript or subscript, or None."""
    if isinstance(node, Sym):
        return None if node.kind == "hole" else node.text
    if isinstance(node, Row):
        parts = [_flat(item) for item in node.items]
        return None if None in parts else "".join(parts)
    if isinstance(node, Fence):
        inner = _flat(node.body)
        return None if inner is None else node.open + inner + node.close
    return None


def _small(node, table, marker):
    flat = _flat(node)
    if flat is not None and flat and all(ch in table for ch in flat):
        return "".join(table[ch] for ch in flat), True
    text, _exact = _text(node, False)
    return marker + (text if len(text) == 1 else f"({text})"), False


def _grouped(node):
    text, exact = _text(node, False)
    simple = isinstance(node, (Sym, Fence)) or (isinstance(node, Script) and isinstance(node.base, Sym))
    return (text if simple else f"({text})"), exact


def _text_items(items, spaced):
    out, exact = [], True
    for i, item in enumerate(items):
        text, ok = _text(item, spaced)
        exact = exact and ok
        if isinstance(item, Sym):
            before = items[i - 1] if i else None
            binary = before is not None and not (isinstance(before, Sym) and before.kind == "op")
            if item.kind == "op" and spaced and i + 1 < len(items) and (
                    item.text in RELATIONS or (item.text in BINARY - set("×·") and binary)):
                text = f" {text} " if binary or item.text in RELATIONS and i else f"{text} "
            elif item.kind == "op" and item.text in ",;":
                text += " " if spaced else ""
            elif item.kind in ("fn", "text") and i + 1 < len(items) and not isinstance(items[i + 1], Fence):
                text += " "
        elif (_is_kind(item, "fn") and i + 1 < len(items) and not isinstance(items[i + 1], Fence)) or (
                _is_kind(item, "big") and i + 1 < len(items) and spaced):
            text += " "
        out.append(text)
    return "".join(out), exact


def _text(node, spaced=True):
    if isinstance(node, Sym):
        return node.text, node.kind != "hole"
    if isinstance(node, Row):
        return _text_items(node.items, spaced)
    if isinstance(node, (Script, Stack)):
        low, high = (node.sub, node.sup) if isinstance(node, Script) else (node.under, node.over)
        text, exact = _grouped(node.base) if not isinstance(node.base, Sym) else _text(node.base, False)
        if isinstance(node, Stack) and not _is_kind(node.base, "big"):
            exact = False                           # lim and labelled arrows need the label underneath
        for part, table, marker in ((low, SUBSCRIPTS, "_"), (high, SUPERSCRIPTS, "^")):
            if part is not None:
                small, ok = _small(part, table, marker)
                text, exact = text + small, exact and ok
        return text, exact
    if isinstance(node, Frac):
        num, den = _flat(node.num), _flat(node.den)
        if node.bar and num and den and num.isdigit() and den.isdigit():
            return FRACTIONS.get(f"{num}/{den}") or (
                "".join(SUPERSCRIPTS[c] for c in num) + "⁄" + "".join(SUBSCRIPTS[c] for c in den)), True
        return _grouped(node.num)[0] + ("/" if node.bar else " over ") + _grouped(node.den)[0], False
    if isinstance(node, Root):
        degree = _flat(node.degree) if node.degree is not None else ""
        sign = {"": "√", "3": "∛", "4": "∜"}.get(degree)
        exact = isinstance(node.body, Sym) and node.body.kind != "hole"
        if sign is None:
            small, ok = _small(node.degree, SUPERSCRIPTS, "")
            sign, exact = (small if ok else f"root({_text(node.degree, False)[0]})") + "√", exact and ok
        return sign + _grouped(node.body)[0], exact
    if isinstance(node, Fence):
        text, exact = _text(node.body, spaced)
        return node.open + text + node.close, exact
    if isinstance(node, Accent):
        text, exact = _text(node.body, False)
        combining = ACCENTS[node.mark][1]
        if len(text) == 1:
            return text + combining, exact
        if node.mark in ("overline", "underline"):
            return "".join(ch + combining for ch in text), exact
        return f"({text}){combining}", False
    if isinstance(node, Matrix):
        rows = "; ".join(", ".join(_text(cell, spaced)[0] for cell in cells) for cells in node.rows)
        return (node.open or "[") + rows + (node.close or ("" if node.open else "]")), False
    raise TypeError(node)


def to_text(node):
    """(the maths in ordinary characters, whether those characters show it exactly as built up)."""
    text, exact = _text(node, True)
    return text.strip(), exact and bool(text.strip())


# --------------------------------------------------------------------------- the gallery
# Like Word's Equation tools: (name, what its button shows, things to start from).  None is a divider.
GALLERY = [
    ("Fraction", "x/y", ["(□)/(□)", "dy/dx", "(Δy)/(Δx)", "(∂y)/(∂x)", "π/2", None,
                         "binom(□, □)"]),
    ("Script", "e^x", ["□^□", "□_□", "□_□^□", None, "x^2", "e^(-iωt)", "x_(y^2)", "□^(□^□)"]),
    ("Radical", "root(n)(x)", ["sqrt(□)", "cbrt(□)", "root(□)(□)", None,
                               "(-b+-sqrt(b^2-4ac))/(2a)", "sqrt(a^2+b^2)"]),
    ("Integral", "int_(-x)^x", ["int □", "int_□^□ □", "iint □", "iiint □", "oint □", "oint_□^□ □", None,
                                "int_a^b f(x) dx"]),
    ("Large operator", "sum_(i=0)^n", ["sum □", "sum_(□)^(□) □", "sum_(□) □", "prod_(□)^(□) □",
                                        "⋃_(□)^(□) □", "⋂_(□)^(□) □", None, "sum_(i=1)^n i",
                                        "sum_(k=0)^n binom(n, k)"]),
    ("Bracket", "\\{()\\}", ["(□)", "[□]", "\\{□\\}", "|□|", "‖□‖", "⌊□⌋", "⌈□⌉", "⟨□⟩", None,
                              "cases(□, □; □, □)", "binom(□, □)", "f(x)=cases(-x, x<0; x, x>=0)"]),
    ("Function", "sin θ", ["sin □", "cos □", "tan □", "csc □", "sec □", "cot □", None,
                           "sin^(-1) □", "cos^(-1) □", "tan^(-1) □", "sinh □", "cosh □", "tanh □", None,
                           "sin θ", "cos 2x", "tan θ=(sin θ)/(cos θ)"]),
    ("Accent", "ddot(a)", ["dot(□)", "ddot(□)", "hat(□)", "bar(□)", "vec(□)", "tilde(□)", None,
                           "overline(□)", "underline(□)", None, "bar(x)", "vec(v)", "overline(AB)"]),
    ("Limit and log", "lim_(n->∞)", ["log_□ □", "log □", "ln □", "lim_(□) □", "min_(□) □", "max_(□) □", None,
                                      "lim_(n->∞) (1+1/n)^n", "max_(0<=x<=1) x e^(-x^2)"]),
    ("Operator", "over(=, Δ)", [":=", "==", "+=", "-=", "over(=, \"def\")", "over(=, Δ)", None,
                                "over(→, □)", "under(→, □)", "over(←, □)", "over(⇒, □)", "over(⇌, □)", None,
                                "over(→, \"yields\")"]),
    ("Matrix", "bmatrix(1,0;0,1)", ["matrix(□, □)", "matrix(□; □)", "matrix(□, □; □, □)",
                                     "matrix(□, □, □; □, □, □)", "matrix(□, □, □; □, □, □; □, □, □)", None,
                                     "pmatrix(□, □; □, □)", "bmatrix(□, □; □, □)", "vmatrix(□, □; □, □)", None,
                                     "pmatrix(1, 0; 0, 1)", "bmatrix(1, 0, 0; 0, 1, 0; 0, 0, 1)",
                                     "pmatrix(□, …, □; ⋮, ⋱, ⋮; □, …, □)"]),
]
