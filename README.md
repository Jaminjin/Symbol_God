# SymbolPad

A small always-on-top palette for typing **any symbol** into Word (or any other Mac app).
Find a symbol by **searching** for it, like Word's *Insert Symbol*, or by **drawing** it,
like Google Docs' *Draw a symbol here*. Click it and it's typed where your cursor is.

The palette can float anywhere as a box, dock to the side of the screen as a panel,
or shrink to a little **τ** bubble. It's made of Apple's Liquid Glass, so whatever is
behind it shows through, the way it does in Launchpad.

## Download the app

You don't need PyCharm or Python for this.

1. Go to the [Releases page](https://github.com/Jaminjin/Symbol_God/releases) and, under
   **Assets** of the newest release, download **SymbolPad.dmg**.
2. Open it and drag **SymbolPad** onto **Applications**.
3. Open SymbolPad from Applications. The first time, macOS says it can't check the app
   (it isn't signed with a paid Apple developer account). Click **Done**, then open
   **System Settings → Privacy & Security**, scroll down and click **Open Anyway**.
4. Click the blue **Allow…** banner in SymbolPad, switch on **SymbolPad** under
   *Accessibility*, then quit SymbolPad (τ menu → *Quit*) and open it again.

It needs a Mac with Apple Silicon (M1 or newer). Liquid Glass needs macOS 26 or newer;
on older versions the palette uses the ordinary blurred background instead.

## Run it in PyCharm

1. **File → Open…** and choose the `SymbolPad` folder.
2. PyCharm should pick up the project's `.venv` (Python 3.14) automatically.
   If it doesn't: **Settings → Project → Python Interpreter → Add Interpreter →
   Add Local Interpreter → Select existing** and choose `SymbolPad/.venv/bin/python`.
   Starting from a fresh copy of the code instead? Make a new virtual environment there
   and run `pip install -r requirements.txt` in PyCharm's Terminal.
3. Open `main.py` and press the green **▶ Run** button.

The palette appears near the top-right corner, and a **τ** appears in the menu bar.
To quit, use the τ menu, ⚙ → *Quit SymbolPad*, or PyCharm's ■ Stop button.

### One-time permission (needed to type into Word)

macOS only lets an app type into other apps after you allow it. The first time,
SymbolPad shows a blue **Allow…** banner:

1. Click **Allow…**. System Settings opens at **Privacy & Security → Accessibility**.
2. Turn on **PyCharm**. macOS gives the permission to the app that started
   SymbolPad: PyCharm, Terminal, or SymbolPad itself if you downloaded the app.
3. Stop and run SymbolPad again.

Until you allow it, clicking a symbol copies it, and you press **⌘V** in Word.

## Using it

| To… | Do this |
|---|---|
| Open the palette from anywhere | **⌃⌥S** (Control-Option-S); press it again to close. Change it in ⚙ → *Shortcuts…* |
| Find a symbol | Type in the search box: `alpha`, `integral`, `not equal`, `degree`, `arrow`… |
| Use LaTeX names | `\alpha`, `\leq`, `\rightarrow`, `\mathbb{R}`, `^2`, `_3` |
| Use a code | `U+2192`, `2192`, `&#945;` |
| Insert | Click it, or press **Enter** for the highlighted one |
| Copy without inserting | **⌘Enter**, the *Copy* button, or right-click → Copy |
| Draw a symbol | Click **✎ Draw** (⌘D), draw it, then click the right match |
| Browse | The category button (∑ Math ▾): Greek, Arrows, Superscripts, Science… |
| Insert a recent symbol | Click it in the *Recent* row, or **⌘1…⌘9** |
| Save favourites | Right-click → *Add to Favorites*, or the ☆ button |
| Play a looping GIF in the panel | ⚙ → *Show GIF* (⚙ → *Choose GIF…* to change it, or right-click the GIF) |
| Go back to Word | **Esc** (clears the search first, if there is one) |

**Moving it around.** Drag the top bar to move it. Drag it to the left or right edge
of the screen and it docks there as a full-height side panel; drag it away to float
it again. You can also click ◨ or ❐ in the top bar, or double-click the bar.
**–** shrinks it to the τ bubble, or to a tab on the screen edge when docked.
Click the bubble to open it again. **✕** hides it; bring it back with your shortcut or
the τ icon.

**Resizing it.** Drag any edge or corner of the open palette (the pointer turns into
arrows; there's a small grip in the bottom-right corner). SymbolPad remembers the size:
it comes back the same from the bubble and the next time you open the app. A docked
panel keeps your width and fills the height of the screen. ⚙ → *Reset window size*
goes back to the original.

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
- **Shortcuts…** opens a small window with two boxes. Click a box, then press the keys
  you want (they need ⌘, ⌃ or ⌥ in them; the F keys work on their own).
  - *Open SymbolPad*: works in every app.
  - *Close SymbolPad*: leave it as *Same as open* to have one shortcut do both, or give
    closing its own keys. Those keys are only taken over while the palette is open.
  - *Closing* either hides the palette or shrinks it to the bubble.
  - **Esc** cancels, **⌫** removes a shortcut.
- **Show the τ icon in**: the menu bar, the Dock, or both. With a Dock icon, SymbolPad
  also appears in ⌘-Tab, and clicking the icon opens the palette. On another app's
  full-screen page the Dock icon steps aside (the Dock is hidden there anyway), because
  macOS won't let an app with a Dock icon float over full-screen apps.
- **Look**
  - *Liquid Glass · dark, like Launchpad* (default): blurred, colourful glass with white text.
  - *Liquid Glass · light*: the bright variety, with dark text.
  - *Liquid Glass · clear*: you can see straight through it.
  - *Solid*: no glass; light, dark, or whichever macOS is using.
- **Background colour**: pick one of the colours or *Custom…* for any colour (the
  palette changes as you move around the colour picker). On glass the colour is a tint,
  and you choose how strong: light, medium, strong or solid. Text switches between
  white and black by itself to stay readable. *None* removes the colour.
- **RGB border**: the animated rainbow edge.
- **Show GIF / Choose GIF…**
- **Reset window size**

## Troubleshooting

- **Nothing gets typed into Word.** Give SymbolPad (or PyCharm, if you run it from
  there) Accessibility permission (see above), then restart SymbolPad.
- **The shortcut does nothing, or SymbolPad says it's taken.** Another app is using
  those keys. Pick different ones in ⚙ → *Shortcuts…*.
- **I hid the τ icon and the palette.** Press your shortcut, or open SymbolPad again
  from Applications (or run it again in PyCharm).
- **The first launch takes a few seconds before Draw works.** It's preparing the
  symbol shapes. They're cached, so later launches are instant.

Settings, favourites and your saved drawings are in
`~/Library/Application Support/SymbolPad/`. Delete that folder to start fresh.

## Project layout

```
main.py                  ← run this
build_dmg.py             ← run this to make dist/SymbolPad.dmg (the downloadable app)
symbolpad/
  app.py                 wires everything together, menu-bar and Dock icon
  window.py              the palette: panel, bubble, docking, resizing, settings menu
  widgets.py             symbol grid, drawing pad, info bar, toast, bubble
  shortcuts.py           the window where you record your shortcuts
  theme.py               the looks: glass or solid, light or dark, your own colour
  icon.py                draws the τ app icon
  symbols.py             search index over ~19,000 symbols
  symbol_data.py         categories, everyday search words, LaTeX names
  recognizer.py          drawing recognition (numpy only)
  glyphs.py              turns font glyphs into recognition templates
  pen_shapes.py          hand-drawn reference shapes for common symbols
  engine.py              loads/caches templates, learns from your picks
  inserter.py            sends the symbol to the app you were typing in
  macos.py               macOS bits: typing, shortcuts, Liquid Glass, window behaviour
  storage.py             settings and saved drawings
tests/                   python -m unittest discover -s tests
```

To run it outside PyCharm: `.venv/bin/python main.py` from the project folder.
To reinstall the dependencies: `.venv/bin/pip install -r requirements.txt`.

### Making the downloadable app

Right-click `build_dmg.py` → **Run** (or `.venv/bin/python build_dmg.py`). It needs
`pip install pyinstaller` once. The result is `dist/SymbolPad.dmg`, which you attach to
a release on GitHub. The version number comes from `symbolpad/__init__.py`.
