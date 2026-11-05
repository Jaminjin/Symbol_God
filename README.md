# SymbolPad

A small always-on-top palette for typing **any symbol** into Word (or any other Mac app).
Find a symbol by **searching** for it, like Word's *Insert Symbol*, or by **drawing** it,
like Google Docs' *Draw a symbol here*. Click it and it's typed where your cursor is.

The palette can float anywhere as a box, dock to the side of the screen as a panel,
or shrink to a little **Ω** bubble.

## Run it in PyCharm

1. **File → Open…** and choose `~/PycharmProjects/SymbolPad`.
2. PyCharm should pick up the project's `.venv` (Python 3.14) automatically.
   If it doesn't: **Settings → Project → Python Interpreter → Add Interpreter →
   Add Local Interpreter → Select existing** and choose `SymbolPad/.venv/bin/python`.
3. Open `main.py` and press the green **▶ Run** button.

The palette appears near the top-right corner, and an **Ω** appears in the menu bar.
SymbolPad has no Dock icon. To quit, use the Ω menu, ⚙ → *Quit SymbolPad*, or
PyCharm's ■ Stop button.

### One-time permission (needed to type into Word)

macOS only lets an app type into other apps after you allow it. The first time,
SymbolPad shows a blue **Allow…** banner:

1. Click **Allow…**. System Settings opens at **Privacy & Security → Accessibility**.
2. Turn on **PyCharm**. macOS gives the permission to the app that started
   SymbolPad. If you run it from Terminal instead, turn on Terminal.
3. Stop and run SymbolPad again.

Until you allow it, clicking a symbol copies it, and you press **⌘V** in Word.

## Using it

| To… | Do this |
|---|---|
| Open the palette from anywhere | **⌃⌥S** (Control-Option-S); change it in ⚙ |
| Find a symbol | Type in the search box: `alpha`, `integral`, `not equal`, `degree`, `arrow`… |
| Use LaTeX names | `\alpha`, `\leq`, `\rightarrow`, `\mathbb{R}`, `^2`, `_3` |
| Use a code | `U+2192`, `2192`, `&#945;` |
| Insert | Click it, or press **Enter** for the highlighted one |
| Copy without inserting | **⌘Enter**, the *Copy* button, or right-click → Copy |
| Draw a symbol | Click **✎ Draw** (⌘D), draw it, then click the right match |
| Browse | The category button (∑ Math ▾): Greek, Arrows, Superscripts, Science… |
| Insert a recent symbol | Click it in the *Recent* row, or **⌘1…⌘9** |
| Save favourites | Right-click → *Add to Favorites*, or the ☆ button |
| Go back to Word | **Esc** (clears the search first, if there is one) |

**Moving it around.** Drag the top bar to move it. Drag it to the left or right edge
of the screen and it docks there as a full-height side panel; drag it away to float
it again. You can also click ◨ or ❐ in the top bar, or double-click the bar.
**–** shrinks it to the Ω bubble, or to a tab on the screen edge when docked.
Click the bubble to open it again. **✕** hides it; bring it back with ⌃⌥S or the
Ω menu.

**Tips for school**

- Superscripts and subscripts: search `^2` → ², `_2` → ₂ (H₂O, x²).
- Accents that sit on a letter (x̄, x̂, v⃗): type the letter in Word first, then
  insert the accent from *Accents for x̄, x̂, v⃗*, or search `bar`, `hat`, `vector`.
- The info bar shows each symbol's LaTeX name and, if there is one, its built-in Mac
  shortcut (e.g. π is ⌥P).

## How drawing recognition works

There's no internet and no AI service involved. SymbolPad renders about 600 symbols from
fonts already on your Mac (STIX Two Math, Apple Symbols, Arial Unicode…) and thins
each one to a pen-like skeleton. Your drawing is compared with those shapes as
clouds of points that also remember stroke direction (see `symbolpad/recognizer.py`).
Hand-drawn reference shapes for about 70 common symbols cover the cases where fonts
don't look like handwriting, such as √ with its top bar.

**It learns your handwriting.** Each time you pick a match after drawing, your drawing
is saved as an extra example of that symbol. If a symbol isn't recognised at first,
search for it once, then draw it and pick it from the list. ⚙ → *Forget my handwriting*
resets this.

In testing with randomly distorted drawings of common math symbols, the right symbol
was the first match about 9 times out of 10, and in the top five nearly always.

## Settings (⚙)

- **When I pick a symbol**
  - *Type it* (default): types the character straight into Word.
  - *Paste it*: puts it on the clipboard for a moment and presses ⌘V. Try this if a
    non-English keyboard input method turns symbols into other characters.
  - *Only copy it*: copies it, and you paste it yourself.
- **Shrink to a bubble after inserting**
- **Shortcut to open SymbolPad**: ⌃⌥S, ⌃⇧S, ⌥⌘S, ⌃⌥⌘S, ⌃⇧Space or off.
- **Appearance**: follow macOS, light or dark.

## Troubleshooting

- **Nothing gets typed into Word.** Give PyCharm Accessibility permission (see above),
  then restart SymbolPad.
- **"Another app already uses that shortcut".** Pick a different one in ⚙.
- **The first launch takes a few seconds before Draw works.** It's preparing the
  symbol shapes. They're cached, so later launches are instant.

Settings, favourites and your saved drawings are in
`~/Library/Application Support/SymbolPad/`. Delete that folder to start fresh.

## Project layout

```
main.py                  ← run this
symbolpad/
  app.py                 wires everything together, menu-bar icon
  window.py              the palette: panel, bubble, docking, settings menu
  widgets.py             symbol grid, drawing pad, info bar, toast, bubble
  symbols.py             search index over ~19,000 symbols
  symbol_data.py         categories, everyday search words, LaTeX names
  recognizer.py          drawing recognition (numpy only)
  glyphs.py              turns font glyphs into recognition templates
  pen_shapes.py          hand-drawn reference shapes for common symbols
  engine.py              loads/caches templates, learns from your picks
  inserter.py            sends the symbol to the app you were typing in
  macos.py               macOS bits: typing, global shortcut, window behaviour
  storage.py             settings and saved drawings
  theme.py               light and dark colours
tests/                   python -m unittest discover -s tests
```

To run it outside PyCharm: `cd ~/PycharmProjects/SymbolPad && .venv/bin/python main.py`.
To reinstall the dependencies: `.venv/bin/pip install -r requirements.txt`.
