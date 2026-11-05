"""Curated symbol sets, friendly search words and LaTeX names.

Everything here is plain data. ``symbols.py`` turns it into a searchable index.
Characters inside the category strings are separated by spaces.
"""

import unicodedata


def _lookup(*names):
    """Return the first character whose Unicode name exists (skips gaps)."""
    for name in names:
        try:
            return unicodedata.lookup(name)
        except KeyError:
            pass
    return ""


def _alphabet(*patterns):
    """Build A-Z for styles like double-struck, filling Unicode's gaps."""
    out = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        ch = _lookup(*(p.format(letter) for p in patterns))
        if ch:
            out.append(ch)
    return " ".join(out)


_SUPER_LETTERS = "abcdefghijklmnoprstuvwxyz"   # Unicode has no superscript q
_SUB_LETTERS = "aehijklmnoprstuvx"


def _superscripts():
    digits = "ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE".split()
    chars = [_lookup(f"SUPERSCRIPT {d}") for d in digits]
    chars += [_lookup(f"SUPERSCRIPT {n}") for n in
              ("PLUS SIGN", "MINUS", "EQUALS SIGN", "LEFT PARENTHESIS", "RIGHT PARENTHESIS")]
    chars += [_lookup(f"MODIFIER LETTER SMALL {c.upper()}", f"SUPERSCRIPT LATIN SMALL LETTER {c.upper()}")
              for c in _SUPER_LETTERS]
    chars += [_lookup(f"MODIFIER LETTER SMALL {g}") for g in
              ("ALPHA", "BETA", "GREEK GAMMA", "DELTA", "THETA", "GREEK PHI", "CHI")]
    return " ".join(c for c in chars if c)


def _subscripts():
    digits = "ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE".split()
    chars = [_lookup(f"SUBSCRIPT {d}") for d in digits]
    chars += [_lookup(f"SUBSCRIPT {n}") for n in
              ("PLUS SIGN", "MINUS", "EQUALS SIGN", "LEFT PARENTHESIS", "RIGHT PARENTHESIS")]
    chars += [_lookup(f"LATIN SUBSCRIPT SMALL LETTER {c.upper()}") for c in _SUB_LETTERS]
    chars += [_lookup(f"GREEK SUBSCRIPT SMALL LETTER {g}") for g in ("BETA", "GAMMA", "RHO", "PHI", "CHI")]
    return " ".join(c for c in chars if c)


# Combining marks attach to the character typed just before them (x then ̄ gives x̄).
COMBINING = (
    "̂ ̄ ̅ ̇ ̈ ̃ ̌ ́ ̀ ̆ ̊ "
    "⃗ ⃖ ⃡ ̲ ̳ ̸ ⃒ ̧ ̣ ⃝ ⃞"
)

# (key, title, icon, characters).  Order = order shown in the category menu.
CATEGORIES = [
    ("math", "Math", "∑",
     "+ − × ÷ ± ∓ · ⋅ ∘ ∗ = ≠ ≈ ≉ ≃ ≅ ≡ ≢ ∼ ≜ ≔ ∝ < > ≤ ≥ ⩽ ⩾ ≦ ≧ ≪ ≫ ≲ ≳ ≺ ≻ "
     "∞ √ ∛ ∜ ∫ ∬ ∭ ∮ ∯ ∑ ∏ ∐ ∂ ∇ ∆ ′ ″ ‴ ° ∠ ∡ ⊥ ∥ ∦ ∣ ∤ ∴ ∵ ∶ ∷ "
     "⌊ ⌋ ⌈ ⌉ ⟨ ⟩ ‖ ⊕ ⊖ ⊗ ⊘ ⊙ ⊞ ⊠ ⋯ ⋮ ⋰ ⋱ … % ‰ ℓ ℏ ℵ ∅ ∖ ⨯ ⨁ ⨂ ∔ ≐ ≍ ⊲ ⊳ ⋈ ≀ ⋄ ◊ ∎"),
    ("logic", "Logic & Sets", "∀",
     "∀ ∃ ∄ ¬ ∧ ∨ ⊻ ⊼ ⊽ ⇒ ⇔ → ↔ ⊢ ⊣ ⊨ ⊤ ⊥ ∴ ∵ ∈ ∉ ∋ ∌ ⊂ ⊃ ⊆ ⊇ ⊄ ⊅ ⊈ ⊉ ⊊ ⊋ "
     "∪ ∩ ∖ ⋃ ⋂ ⊎ ⊔ ⊓ ⊏ ⊐ ⊑ ⊒ ∅ ∁ ℘ ℕ ℤ ℚ ℝ ℂ ℙ ℍ 𝔽 ℵ ∘ □ ◇"),
    ("greek", "Greek", "α",
     "α β γ δ ε ζ η θ ι κ λ μ ν ξ ο π ρ σ ς τ υ φ χ ψ ω ϵ ϑ ϰ ϕ ϖ ϱ ϒ ϝ "
     "Α Β Γ Δ Ε Ζ Η Θ Ι Κ Λ Μ Ν Ξ Ο Π Ρ Σ Τ Υ Φ Χ Ψ Ω"),
    ("arrows", "Arrows", "→",
     "→ ← ↑ ↓ ↔ ↕ ↗ ↘ ↙ ↖ ⇒ ⇐ ⇑ ⇓ ⇔ ⇕ ⟶ ⟵ ⟷ ⟹ ⟸ ⟺ ↦ ⟼ ↪ ↩ ⇀ ↼ ⇁ ↽ ⇌ ⇋ ⇄ ⇆ "
     "⇉ ⇇ ⇈ ⇊ ↠ ↞ ↣ ↢ ⇝ ↝ ↜ ↯ ↺ ↻ ⟲ ⟳ ↶ ↷ ↰ ↱ ↲ ↳ ↴ ↵ ⇥ ⇤ ⇠ ⇡ ⇢ ⇣ ⤴ ⤵ "
     "➔ ➜ ➝ ➞ ➟ ➠ ⇦ ⇧ ⇨ ⇩ ⬌ ⬍ ↛ ↚ ↮ ⇏ ⇍ ⇎ ⤳ ⇶"),
    ("scripts", "Superscript & Subscript", "x²", _superscripts() + " " + _subscripts()),
    ("numbers", "Fractions & Numbers", "½",
     "½ ⅓ ⅔ ¼ ¾ ⅕ ⅖ ⅗ ⅘ ⅙ ⅚ ⅐ ⅛ ⅜ ⅝ ⅞ ⅑ ⅒ ↉ ⅟ ⁄ "
     "Ⅰ Ⅱ Ⅲ Ⅳ Ⅴ Ⅵ Ⅶ Ⅷ Ⅸ Ⅹ Ⅺ Ⅻ Ⅼ Ⅽ Ⅾ Ⅿ ⅰ ⅱ ⅲ ⅳ ⅴ ⅵ ⅶ ⅷ ⅸ ⅹ "
     "① ② ③ ④ ⑤ ⑥ ⑦ ⑧ ⑨ ⑩ ⑪ ⑫ ⑬ ⑭ ⑮ ⑯ ⑰ ⑱ ⑲ ⑳ ❶ ❷ ❸ ❹ ❺ ❻ ❼ ❽ ❾ ❿"),
    ("science", "Science & Units", "℃",
     "° ℃ ℉ Å µ Ω ℧ ℓ ħ ℏ Δ ∆ ∂ ∇ λ ν ρ σ ε ± × · ≈ ∝ ∞ ⇌ ⇋ ⇄ ⟶ → ↑ ↓ "
     "‰ ′ ″ ⌀ ∅ ⊙ ⊗ ♂ ♀ ☉ ⚛ ☢ ☣ ∿ ⏚ ⎓ ⏦"),
    ("letterlike", "Letterlike", "ℝ",
     "ℝ ℕ ℤ ℚ ℂ ℙ ℍ ℓ ℏ ℘ ℑ ℜ ℵ ℶ ℷ ℸ ℮ ℯ ℊ ℎ ℬ ℰ ℱ ℋ ℐ ℒ ℳ ℛ ℭ ℌ ℨ "
     "ⅅ ⅆ ⅇ ⅈ ⅉ ℀ ℁ ℅ ℆ № ℗ ℞ ℠ ™ © ® ℡ ⅋ ℧ Ⅎ ⅁"),
    ("mathletters", "Math Letters (𝔸 𝒜 𝔄)", "𝔸",
     _alphabet("MATHEMATICAL DOUBLE-STRUCK CAPITAL {}", "DOUBLE-STRUCK CAPITAL {}") + " " +
     _alphabet("MATHEMATICAL SCRIPT CAPITAL {}", "SCRIPT CAPITAL {}") + " " +
     _alphabet("MATHEMATICAL FRAKTUR CAPITAL {}", "BLACK-LETTER CAPITAL {}")),
    ("punctuation", "Punctuation", "§",
     "— – ‒ ‐ ‑ … · • ‣ ◦ ⁃ ‘ ’ ‚ ‛ “ ” „ ‟ « » ‹ › ¡ ¿ ‼ ⁇ ⁈ ⁉ ‽ § ¶ † ‡ "
     "※ ⁂ ⁎ ⁑ ‖ ¦ ¬ ¯ ´ ¨ ¸ ˆ ˜ © ® ™ @ & # № ℅ ⸮ ‿ ⁀ ⁔ ′ ″ ‴ ⁄"),
    ("currency", "Currency", "€",
     "$ ¢ £ ¥ € ₹ ₩ ₽ ₺ ₴ ₦ ₱ ₫ ₪ ₭ ₮ ₲ ₵ ₸ ₼ ₾ ₿ ฿ ¤ ₡ ₣ ₤ ₥ ₧ ₨ ₰ ₳ ₶ ₷ ₻ ₠"),
    ("shapes", "Shapes & Marks", "★",
     "✓ ✔ ✗ ✘ ☐ ☑ ☒ ★ ☆ ✦ ✧ ✪ ✩ ● ○ ◉ ◎ ◯ ◌ ◐ ◑ ■ □ ▪ ▫ ▬ ▭ ▮ ▯ "
     "▲ △ ▶ ▷ ▼ ▽ ◀ ◁ ▴ ▵ ▸ ▹ ▾ ▿ ◂ ◃ ◆ ◇ ◈ ◊ ⬟ ⬠ ⬡ ⬢ "
     "♠ ♣ ♥ ♦ ♤ ♧ ♡ ♢ ♔ ♕ ♖ ♗ ♘ ♙ ♚ ♛ ♜ ♝ ♞ ♟ ♩ ♪ ♫ ♬ ♭ ♮ ♯ "
     "☀ ☁ ☂ ☃ ☎ ☛ ☞ ✈ ✉ ✎ ✏ ✐ ✂ ⌘ ⌥ ⇧ ⌃ ⎋ ⌫ ⏎ ⏏ ⌚ ⌛ ☺ ☹ ☯ ☮ ⚠ ⚑ ⚐ ⚙ ⚖ ⚓ ♻"),
    ("accented", "Accented Letters", "é",
     "á à â ä ã å ā ă ą æ ç ć č ď é è ê ë ē ė ę ě ğ í ì î ï ī į ı ł ñ ń ň "
     "ó ò ô ö õ ø ō ő œ ř ś š ş ß ť ú ù û ü ū ů ű ų ý ÿ ž ź ż ð þ "
     "Á À Â Ä Ã Å Ā Ă Ą Æ Ç Ć Č Ď É È Ê Ë Ē Ė Ę Ě Ğ Í Ì Î Ï Ī Į İ Ł Ñ Ń Ň "
     "Ó Ò Ô Ö Õ Ø Ō Ő Œ Ř Ś Š Ş Ť Ú Ù Û Ü Ū Ů Ű Ų Ý Ÿ Ž Ź Ż Ð Þ ¿ ¡"),
    ("combining", "Accents for x̄, x̂, v⃗", "x̄", COMBINING),
]

# Shown first and ranked highest when searching: what students reach for most.
COMMON = (
    "± × ÷ · ≠ ≈ ≡ ≤ ≥ ∞ √ ∫ ∑ ∏ ∂ ∇ Δ ° ′ ″ ∠ ⊥ ∥ ∴ ∵ → ← ↑ ↓ ↔ ⇒ ⇔ ⇌ "
    "∈ ∉ ⊂ ⊆ ∪ ∩ ∅ ∀ ∃ ¬ ∧ ∨ ℝ ℕ ℤ ℚ ℂ α β γ δ ε θ λ μ π σ τ φ ω Ω Σ Π Φ Θ Λ "
    "Γ Ψ ρ η ζ ξ χ ψ κ ν ² ³ ½ ¼ ¾ € £ ¥ ¢ © ® ™ • … — – § ¶ † ✓ ✗ ★ ℃ µ Å "
    "‰ ∝ ≅ ∼ ⟶ ∮ ∬ ℏ ℓ ⌊ ⌋ ⌈ ⌉ ⟨ ⟩ ∘ ⊕ ⊗ ="
)

# Everyday words people type when they don't know the official Unicode name.
# Format: "<char> | word; word; word"
_KEYWORDS = """
± | plus minus; plus or minus; pm; +-
∓ | minus plus; mp; -+
× | times; multiply; multiplication; cross product; x
÷ | divide; division; divided by; obelus
· | dot; middle dot; centre dot; multiply; product
⋅ | dot product; cdot; multiply
∘ | composition; compose; ring; circ; function composition
∗ | asterisk; star; convolution
= | equal; equals; equal sign; is
≠ | not equal; unequal; does not equal; ne; !=; =/
≈ | approximately; approx; almost equal; about; roughly; ~=
≉ | not approximately
≃ | asymptotically equal; similar equal
≅ | congruent; isomorphic; approximately equal
≡ | equivalent; identical; congruent mod; modulo; equiv; triple bar
≢ | not equivalent; not identical
∼ | similar; tilde; distributed as; sim
≜ | defined as; equal by definition
≔ | defined as; colon equals; assignment; :=
∝ | proportional; proportional to; varies as; propto
< | less than
> | greater than
≤ | less than or equal; at most; leq; <=; le
≥ | greater than or equal; at least; geq; >=; ge
⩽ | less than or equal slanted; leqslant
⩾ | greater than or equal slanted; geqslant
≪ | much less than; ll
≫ | much greater than; gg
∞ | infinity; infinite; inf; infty; lemniscate
√ | square root; root; sqrt; radical; surd
∛ | cube root; cbrt
∜ | fourth root
∫ | integral; integrate; int; antiderivative
∬ | double integral; iint
∭ | triple integral; iiint
∮ | contour integral; line integral; closed integral; oint
∑ | sum; summation; sigma; series
∏ | product; pi product; prod
∂ | partial; partial derivative; del; curly d
∇ | nabla; del; gradient; grad; divergence; curl
∆ | delta; increment; change; laplacian; triangle
Δ | change; triangle; discriminant; difference
′ | prime; minute; feet; derivative; apostrophe
″ | double prime; second; inches; second derivative
‴ | triple prime; third derivative
° | degree; degrees; deg; temperature; angle
∠ | angle
∡ | measured angle
⊥ | perpendicular; perp; orthogonal; bottom; false; up tack
∥ | parallel; is parallel to
∦ | not parallel
∣ | divides; such that; given; mid
∤ | does not divide
∴ | therefore; so; hence; thus
∵ | because; since
⌊ | floor; left floor
⌋ | floor; right floor
⌈ | ceiling; ceil; left ceiling
⌉ | ceiling; ceil; right ceiling
⟨ | angle bracket; bra; left angle; langle; inner product
⟩ | angle bracket; ket; right angle; rangle; inner product
‖ | norm; double bar; double vertical; magnitude
⊕ | xor; exclusive or; direct sum; oplus; circled plus
⊗ | tensor product; otimes; circled times
⊙ | circled dot; odot; sun
⋯ | dots; cdots; centered ellipsis; and so on
⋮ | vertical dots; vdots; vertical ellipsis
⋱ | diagonal dots; ddots
… | ellipsis; dots; ldots; three dots; and so on
∎ | qed; end of proof; tombstone; halmos
∀ | for all; forall; for every; for each; universal
∃ | exists; there exists; there is; existential
∄ | does not exist; there does not exist; nexists
¬ | not; negation; logical not; neg
∧ | and; logical and; wedge; conjunction
∨ | or; logical or; vee; disjunction
⊻ | xor; exclusive or
⇒ | implies; then; therefore; double arrow; =>
⇔ | if and only if; iff; equivalent; double arrow both; <=>
⊢ | proves; turnstile; entails
⊨ | models; satisfies; entails
⊤ | true; top; tautology
∈ | element of; in; is in; belongs to; member of
∉ | not element of; not in; notin
∋ | contains as member; ni; owns
⊂ | subset; proper subset
⊃ | superset; proper superset
⊆ | subset or equal; subseteq
⊇ | superset or equal; supseteq
⊊ | proper subset; subsetneq
⊄ | not subset
∪ | union; cup; or
∩ | intersection; cap; and
∖ | set minus; set difference; without; minus
∅ | empty set; null set; emptyset; nothing; varnothing; diameter
∁ | complement
℘ | power set; weierstrass p
ℕ | natural numbers; naturals; N; blackboard N; double struck N
ℤ | integers; whole numbers; Z; blackboard Z; double struck Z
ℚ | rational numbers; rationals; Q; blackboard Q; double struck Q
ℝ | real numbers; reals; R; blackboard R; double struck R
ℂ | complex numbers; C; blackboard C; double struck C
ℙ | primes; probability; P; blackboard P
ℍ | quaternions; H; blackboard H
ℵ | aleph; cardinality; infinity cardinal
ℏ | h bar; hbar; reduced planck constant; dirac constant
ħ | h bar; hbar
ℓ | script l; ell; liter; litre; length
α | alpha; angle; alpha particle
β | beta
γ | gamma; photon
δ | delta; small change
ε | epsilon; small number; permittivity
θ | theta; angle
λ | lambda; wavelength; eigenvalue
μ | mu; micro; mean; coefficient of friction
π | pi; 3.14
σ | sigma; standard deviation; stress
τ | tau; torque; time constant
φ | phi; golden ratio; angle; flux
ω | omega; angular velocity; angular frequency
Ω | omega; ohm; ohms; resistance
Σ | sigma; sum
Π | pi; product
µ | micro; micro sign; mu; micrometre; microgram
Å | angstrom; ångström
℃ | celsius; degrees celsius; centigrade; temperature
℉ | fahrenheit; degrees fahrenheit; temperature
‰ | per mille; per thousand; permille
⇌ | equilibrium; reversible reaction; rightleftharpoons; chemistry
⇋ | equilibrium; leftrightharpoons
→ | right arrow; arrow; to; tends to; approaches; yields; maps to; ->
← | left arrow; gets; from; <-
↑ | up arrow; increase; gas evolved
↓ | down arrow; decrease; precipitate
↔ | left right arrow; both ways; <->
⟶ | long right arrow; reaction arrow; longrightarrow
⟹ | long implies; longrightarrow double
↦ | maps to; mapsto
↪ | hook arrow; injection; embedding
↠ | surjection; two headed arrow
² | squared; superscript 2; power of two; ^2
³ | cubed; superscript 3; power of three; ^3
¹ | superscript 1; ^1
ⁿ | to the n; superscript n; ^n
½ | half; one half; 1/2
⅓ | one third; 1/3
⅔ | two thirds; 2/3
¼ | quarter; one quarter; 1/4
¾ | three quarters; 3/4
• | bullet; bullet point; dot
— | em dash; long dash; dash
– | en dash; range dash; dash
‐ | hyphen
“ | left quote; open quote; smart quote
” | right quote; close quote; smart quote
‘ | left single quote; open quote
’ | apostrophe; right single quote; close quote
« | guillemet; french quote; left
» | guillemet; french quote; right
§ | section; section sign; law
¶ | paragraph; pilcrow
† | dagger; died; obelisk; footnote
‡ | double dagger; footnote
© | copyright
® | registered; registered trademark
™ | trademark; tm
€ | euro; currency
£ | pound; sterling; gbp
¥ | yen; yuan
¢ | cent; cents
$ | dollar; usd
₹ | rupee; indian rupee
₩ | won; korean won
₿ | bitcoin
✓ | check; tick; checkmark; correct; yes; done
✔ | check; tick; checkmark; heavy check; done
✗ | cross; x mark; wrong; no; ballot x
✘ | cross; x mark; wrong; heavy ballot x
☐ | checkbox; empty box; unchecked; todo
☑ | checked box; checkbox ticked; done
☒ | checkbox crossed
★ | star; filled star; favourite
☆ | star; empty star; outline star
● | filled circle; black circle; dot
○ | circle; empty circle; ring
■ | filled square; black square
□ | square; empty square; box; d'alembertian
▲ | triangle; filled triangle; up
△ | triangle; empty triangle; up
♥ | heart; love
♡ | heart; empty heart
⌀ | diameter
☉ | sun; solar mass
♂ | male; mars
♀ | female; venus
⚛ | atom
☢ | radioactive; radiation
☣ | biohazard
∿ | sine wave; alternating current; ac
⏚ | earth ground; ground
⎓ | direct current; dc
℅ | care of
№ | number; numero
ⅈ | imaginary unit; i
ⅇ | e; euler number; exponential
ⅆ | differential d; dx
ℯ | e; euler number; natural log base
ℜ | real part; re
ℑ | imaginary part; im
⟲ | anticlockwise; counterclockwise; rotate left
⟳ | clockwise; rotate right
↺ | anticlockwise; counterclockwise; undo
↻ | clockwise; redo; refresh
⇧ | shift key; shift
⌘ | command key; cmd; place of interest
⌥ | option key; alt
⌃ | control key; ctrl; up arrowhead
⎋ | escape key; esc
⌫ | delete; backspace; erase left
⏎ | return; enter
∅ | null; zero set
"""

# Combining marks: friendly words (they have awkward official names).
_COMBINING_KEYWORDS = {
    "̂": "hat; circumflex; estimator; unit vector; x hat",
    "̄": "bar; macron; mean; average; x bar; overline",
    "̅": "overline; bar; complement; conjugate",
    "̇": "dot; time derivative; x dot; dot above",
    "̈": "double dot; second derivative; ddot; umlaut; diaeresis",
    "̃": "tilde; approximately; x tilde",
    "̌": "check; caron; hacek",
    "́": "acute; accent",
    "̀": "grave; accent",
    "̆": "breve",
    "̊": "ring; mathring; ring above",
    "⃗": "vector; vector arrow; arrow over; v vector; vec",
    "⃖": "left vector arrow; arrow over left",
    "⃡": "left right arrow over; line segment; vector both",
    "̲": "underline; underscore",
    "̳": "double underline",
    "̸": "not; slash through; negate; cancel",
    "⃒": "vertical line through; not",
    "̧": "cedilla",
    "̣": "dot below",
    "⃝": "enclosing circle; circled",
    "⃞": "enclosing square; boxed",
}

# LaTeX command -> character.  Pairs separated by whitespace.
_LATEX = """
alpha α beta β gamma γ delta δ epsilon ϵ varepsilon ε zeta ζ eta η theta θ vartheta ϑ
iota ι kappa κ varkappa ϰ lambda λ mu μ nu ν xi ξ omicron ο pi π varpi ϖ rho ρ varrho ϱ
sigma σ varsigma ς tau τ upsilon υ phi ϕ varphi φ chi χ psi ψ omega ω digamma ϝ
Gamma Γ Delta Δ Theta Θ Lambda Λ Xi Ξ Pi Π Sigma Σ Upsilon Υ Phi Φ Psi Ψ Omega Ω
pm ± mp ∓ times × div ÷ cdot ⋅ cdotp · ast ∗ star ⋆ circ ∘ bullet ∙ cap ∩ cup ∪ uplus ⊎
sqcap ⊓ sqcup ⊔ vee ∨ lor ∨ wedge ∧ land ∧ setminus ∖ wr ≀ diamond ⋄ bigtriangleup △
bigtriangledown ▽ triangleleft ◁ triangleright ▷ lhd ⊲ rhd ⊳ unlhd ⊴ unrhd ⊵ oplus ⊕
ominus ⊖ otimes ⊗ oslash ⊘ odot ⊙ bigcirc ◯ dagger † ddagger ‡ dag † ddag ‡ amalg ⨿
leq ≤ le ≤ geq ≥ ge ≥ neq ≠ ne ≠ equiv ≡ sim ∼ simeq ≃ approx ≈ cong ≅ asymp ≍ propto ∝
models ⊨ perp ⊥ mid ∣ nmid ∤ parallel ∥ nparallel ∦ bowtie ⋈ Join ⨝ smile ⌣ frown ⌢
prec ≺ succ ≻ preceq ⪯ succeq ⪰ ll ≪ gg ≫ subset ⊂ supset ⊃ subseteq ⊆ supseteq ⊇
subsetneq ⊊ supsetneq ⊋ nsubseteq ⊈ nsupseteq ⊉ sqsubset ⊏ sqsupset ⊐ sqsubseteq ⊑
sqsupseteq ⊒ in ∈ ni ∋ notin ∉ vdash ⊢ dashv ⊣ doteq ≐ lesssim ≲ gtrsim ≳ leqslant ⩽
geqslant ⩾ approxeq ≊ triangleq ≜ coloneqq ≔ eqqcolon ≕ nless ≮ ngtr ≯ nleq ≰ ngeq ≱
nsim ≁ ncong ≇ napprox ≉ nequiv ≢ leftarrow ← gets ← rightarrow → to → leftrightarrow ↔
uparrow ↑ downarrow ↓ updownarrow ↕ Leftarrow ⇐ Rightarrow ⇒ Leftrightarrow ⇔ Uparrow ⇑
Downarrow ⇓ Updownarrow ⇕ longleftarrow ⟵ longrightarrow ⟶ longleftrightarrow ⟷
Longleftarrow ⟸ Longrightarrow ⟹ Longleftrightarrow ⟺ implies ⟹ impliedby ⟸ iff ⟺
mapsto ↦ longmapsto ⟼ hookleftarrow ↩ hookrightarrow ↪ leftharpoonup ↼ leftharpoondown ↽
rightharpoonup ⇀ rightharpoondown ⇁ rightleftharpoons ⇌ leftrightharpoons ⇋ nearrow ↗
searrow ↘ swarrow ↙ nwarrow ↖ leadsto ⇝ twoheadrightarrow ↠ twoheadleftarrow ↞
rightarrowtail ↣ leftarrowtail ↢ circlearrowleft ↺ circlearrowright ↻ curvearrowleft ↶
curvearrowright ↷ rightrightarrows ⇉ leftleftarrows ⇇ upuparrows ⇈ downdownarrows ⇊
rightleftarrows ⇄ leftrightarrows ⇆ nrightarrow ↛ nleftarrow ↚ nRightarrow ⇏ nLeftarrow ⇍
nLeftrightarrow ⇎ nleftrightarrow ↮ Lsh ↰ Rsh ↱ dashrightarrow ⇢ dashleftarrow ⇠
infty ∞ nabla ∇ partial ∂ forall ∀ exists ∃ nexists ∄ neg ¬ lnot ¬ emptyset ∅ varnothing ∅
aleph ℵ beth ℶ gimel ℷ daleth ℸ hbar ℏ hslash ℏ ell ℓ wp ℘ Re ℜ Im ℑ angle ∠
measuredangle ∡ sphericalangle ∢ triangle △ surd √ sqrt √ cbrt ∛ top ⊤ bot ⊥ flat ♭
natural ♮ sharp ♯ clubsuit ♣ diamondsuit ♢ heartsuit ♡ spadesuit ♠ sum ∑ prod ∏ coprod ∐
int ∫ iint ∬ iiint ∭ oint ∮ oiint ∯ bigcap ⋂ bigcup ⋃ bigoplus ⨁ bigotimes ⨂ bigodot ⨀
bigvee ⋁ bigwedge ⋀ biguplus ⨄ bigsqcup ⨆ langle ⟨ rangle ⟩ lfloor ⌊ rfloor ⌋ lceil ⌈
rceil ⌉ Vert ‖ | ‖ ldots … dots … cdots ⋯ vdots ⋮ ddots ⋱ therefore ∴ because ∵
degree ° prime ′ dprime ″ trprime ‴ checkmark ✓ copyright © textregistered ® texttrademark ™
pounds £ euro € S § P ¶ complement ∁ square □ Box □ blacksquare ■ lozenge ◊ blacklozenge ⧫
bigstar ★ mho ℧ eth ð Finv Ⅎ Game ⅁ intercal ⊺ barwedge ⊼ veebar ⊻ circledast ⊛
boxplus ⊞ boxtimes ⊠ boxminus ⊟ boxdot ⊡ qed ∎ mathbb{N} ℕ mathbb{Z} ℤ mathbb{Q} ℚ
mathbb{R} ℝ mathbb{C} ℂ mathbb{P} ℙ mathbb{H} ℍ mathbb{F} 𝔽 mathbb{E} 𝔼 mathbb{1} 𝟙
N ℕ Z ℤ Q ℚ R ℝ C ℂ
"""

_LATEX_COMBINING = {
    "hat": "̂", "widehat": "̂", "bar": "̄", "overline": "̅", "dot": "̇",
    "ddot": "̈", "tilde": "̃", "widetilde": "̃", "check": "̌",
    "acute": "́", "grave": "̀", "breve": "̆", "mathring": "̊",
    "vec": "⃗", "overrightarrow": "⃗", "overleftarrow": "⃖",
    "overleftrightarrow": "⃡", "underline": "̲", "not": "̸",
}

# Option-key shortcuts on a US / ABC keyboard (shown as a tip).
MAC_KEYS = {
    "π": "⌥P", "∆": "⌥J", "≠": "⌥=", "≤": "⌥,", "≥": "⌥.", "∞": "⌥5", "√": "⌥V", "∫": "⌥B",
    "∑": "⌥W", "∏": "⌥⇧P", "∂": "⌥D", "≈": "⌥X", "±": "⌥⇧=", "÷": "⌥/", "°": "⌥⇧8",
    "•": "⌥8", "·": "⌥⇧9", "©": "⌥G", "®": "⌥R", "™": "⌥2", "µ": "⌥M", "Ω": "⌥Z",
    "ø": "⌥O", "Ø": "⌥⇧O", "…": "⌥;", "–": "⌥-", "—": "⌥⇧-", "§": "⌥6", "¶": "⌥7",
    "£": "⌥3", "¢": "⌥4", "¥": "⌥Y", "€": "⌥⇧2", "¬": "⌥L", "†": "⌥T", "‡": "⌥⇧7",
    "‰": "⌥⇧R", "ƒ": "⌥F", "å": "⌥A", "Å": "⌥⇧A", "ß": "⌥S", "æ": "⌥'", "œ": "⌥Q",
    "ç": "⌥C", "¿": "⌥⇧/", "¡": "⌥1", "º": "⌥0", "ª": "⌥9", "«": "⌥\\", "»": "⌥⇧\\",
    "“": "⌥[", "”": "⌥⇧[", "‘": "⌥]", "’": "⌥⇧]", "◊": "⌥⇧V", "⁄": "⌥⇧1", "ı": "⌥⇧B",
}


def chars_of(text):
    return [c for c in text.split(" ") if c]


def keywords():
    """{char: [keyword, ...]} from the friendly-word table."""
    table = {}
    for line in _KEYWORDS.strip().splitlines():
        ch, _, words = line.partition(" | ")
        table.setdefault(ch.strip(), []).extend(w.strip() for w in words.split(";") if w.strip())
    for ch, words in _COMBINING_KEYWORDS.items():
        table.setdefault(ch, []).extend(w.strip() for w in words.split(";"))
    return table


def latex_commands():
    """{char: [command, ...]} with commands written without the backslash."""
    parts = _LATEX.split()
    table = {}
    for cmd, ch in zip(parts[0::2], parts[1::2]):
        table.setdefault(ch, []).append(cmd)
    for cmd, ch in _LATEX_COMBINING.items():
        table.setdefault(ch, []).append(cmd)
    # ^2, _2, ^n ... for the super/subscript characters
    for ch in chars_of(_superscripts()):
        base = unicodedata.normalize("NFKC", ch)
        if len(base) == 1:
            table.setdefault(ch, []).append("^" + base)
    for ch in chars_of(_subscripts()):
        base = unicodedata.normalize("NFKC", ch)
        if len(base) == 1:
            table.setdefault(ch, []).append("_" + base)
    return table
