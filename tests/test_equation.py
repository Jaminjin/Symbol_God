"""The Equation page: reading typed maths, what goes to Word, and the page itself (no screen needed)."""

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from symbolpad import mathexpr as mx
from symbolpad import mathview
from symbolpad.storage import Store

_qapp = QApplication.instance() or QApplication([])
MATHML = "{http://www.w3.org/1998/Math/MathML}"


def text(source):
    return mx.to_text(mx.parse(source))


def mathml(source):
    return mx.to_mathml(mx.parse(source))


def tags(source):
    return [el.tag.replace(MATHML, "") for el in ET.fromstring(mathml(source)).iter()]


class PlainCharacterTests(unittest.TestCase):
    def test_powers_and_subscripts(self):
        self.assertEqual(text("6^2"), ("6²", True))
        self.assertEqual(text("Cl_2"), ("Cl₂", True))
        self.assertEqual(text("H_2SO_4"), ("H₂SO₄", True))
        self.assertEqual(text("Ca^(2+)"), ("Ca²⁺", True))
        self.assertEqual(text("x_1^2"), ("x₁²", True))
        self.assertEqual(text("e^-x"), ("e⁻ˣ", True))

    def test_a_chemical_equation(self):
        self.assertEqual(text("2H_2 + O_2 -> 2H_2O"), ("2H₂ + O₂ → 2H₂O", True))

    def test_number_fractions(self):
        self.assertEqual(text("1/2"), ("½", True))
        self.assertEqual(text("3/16"), ("³⁄₁₆", True))

    def test_what_plain_characters_cannot_stack(self):
        for source in ("(a+b)/c", "x^q", "sqrt(x+1)", "lim_(n->inf) 1/n", "pmatrix(1,0;0,1)", "vec(AB)", "x^"):
            self.assertFalse(text(source)[1], source)
        self.assertEqual(text("(a+b)/c")[0], "(a+b)/c")
        self.assertEqual(text("x^q")[0], "x^q")

    def test_roots_accents_and_names(self):
        self.assertEqual(text("sqrt 2"), ("√2", True))
        self.assertEqual(text("cbrt(x)"), ("∛x", True))
        self.assertEqual(text("bar(x)"), ("x̄", True))
        self.assertEqual(text("2pir"), ("2πr", True))
        self.assertEqual(text("sin^2 theta + cos^2 θ = 1"), ("sin² θ + cos² θ = 1", True))
        self.assertEqual(text("x!=3"), ("x ≠ 3", True))
        self.assertEqual(text("\\alpha+\\beta")[0], "α + β")

    def test_nothing_typed(self):
        self.assertTrue(mx.is_empty(mx.parse("   ")))
        self.assertEqual(text(""), ("", False))


class StructureTests(unittest.TestCase):
    def test_fraction_takes_what_is_next_to_the_slash(self):
        tree = mx.parse("a+b/c+d")
        self.assertEqual([type(item).__name__ for item in tree.items], ["Sym", "Sym", "Frac", "Sym", "Sym"])
        tree = mx.parse("(a+b)/(c+d)")
        self.assertIsInstance(tree, mx.Frac)
        self.assertIsInstance(tree.num, mx.Row)             # the grouping brackets are gone
        self.assertIsInstance(mx.parse("2x/3y"), mx.Frac)

    def test_brackets_in_a_power_only_group(self):
        tree = mx.parse("x^(n+1)")
        self.assertIsInstance(tree.sup, mx.Row)
        self.assertIsInstance(mx.parse("(x+1)^2").base, mx.Fence)

    def test_limits_go_under_sums_and_beside_integrals(self):
        self.assertIsInstance(mx.parse("sum_(i=0)^n"), mx.Stack)
        self.assertIsInstance(mx.parse("lim_(n->inf)"), mx.Stack)
        self.assertIsInstance(mx.parse("int_a^b"), mx.Script)

    def test_unfinished_typing_gets_empty_slots(self):
        for source in ("x^", "a/", "^2", "sqrt", "frac(", "(a+b", "matrix(1,", "sum_", "|x", "x_^", "/", "root(3)"):
            tree = mx.parse(source)
            self.assertTrue(mx.has_holes(tree) or source in ("(a+b", "|x"), source)
            ET.fromstring(mx.to_mathml(tree))
            mx.to_text(tree)

    def test_words_only_count_as_commands_with_brackets(self):
        self.assertEqual(text("5 bar")[0], "5bar")
        self.assertIsInstance(mx.parse("bar(x)"), mx.Accent)

    def test_matrix_rows_are_evened_out(self):
        tree = mx.parse("matrix(1,2,3;4)")
        self.assertEqual([len(row) for row in tree.rows], [3, 3])


class WordTests(unittest.TestCase):
    """The MathML shapes below are the ones Word 16 was seen to build the right structure from."""

    def test_structures(self):
        self.assertEqual(tags("6^2"), ["math", "msup", "mn", "mn"])
        self.assertIn("msubsup", tags("x_1^2"))
        self.assertIn("mfrac", tags("(a+b)/c"))
        self.assertIn("msqrt", tags("sqrt(x)"))
        self.assertIn("mroot", tags("root(3)(x)"))
        self.assertIn("munderover", tags("sum_(i=0)^n i"))
        self.assertIn("munder", tags("lim_(n->inf) 1/n"))
        self.assertIn("mfenced", tags("(x+1)"))
        self.assertIn("mtable", tags("pmatrix(1,0;0,1)"))

    def test_functions_are_applied_to_what_follows(self):
        self.assertIn("<mo>&#x2061;</mo><mrow><mi>θ</mi></mrow>", mathml("sin θ"))

    def test_bars_stretch(self):
        self.assertIn('<mover><mrow><mi>A</mi><mi>B</mi></mrow><mo stretchy="true">¯</mo></mover>', mathml("overline(AB)"))
        self.assertIn('<munder>', mathml("underline(AB)"))
        self.assertIn('<mover accent="true">', mathml("hat(x)"))

    def test_less_than_is_escaped(self):
        self.assertIn("<mo>&lt;</mo>", mathml("x<0"))

    def test_everything_in_the_gallery_is_sound(self):
        image = QImage(200, 80, QImage.Format.Format_ARGB32)
        for name, picture, items in mx.GALLERY:
            for source in [picture] + [item for item in items if item]:
                tree = mx.parse(source)
                self.assertFalse(mx.is_empty(tree), source)
                ET.fromstring(mx.to_mathml(tree))
                self.assertTrue(mx.to_text(tree)[0], source)
                self.assertGreater(mathview.layout(tree, 24).w, 0, source)
                mathview.draw(image, tree, QColor("black"), QRectF(0, 0, 200, 80), 24)


class FakeInserter:
    def __init__(self):
        self.calls = []

    def insert(self, text):
        self.calls.append(("text", text))

    def insert_equation(self, mathml, text):
        self.calls.append(("equation", mathml, text))

    def copy_equation(self, mathml, text):
        self.calls.append(("copy", mathml, text))


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from symbolpad import app as symbolpad_app
        cls.tmp = tempfile.TemporaryDirectory()

        class TemporaryStore(Store):                          # never touch your real settings
            def __init__(self):
                super().__init__(Path(cls.tmp.name))

        original = symbolpad_app.Store
        symbolpad_app.Store = TemporaryStore
        try:
            cls.ctl = symbolpad_app.Controller(_qapp)
        finally:
            symbolpad_app.Store = original
        cls.ctl.start()
        cls.panel = cls.ctl.window.panel
        cls.real_inserter = cls.ctl.inserter

    @classmethod
    def tearDownClass(cls):
        cls.ctl.inserter = cls.real_inserter
        cls.ctl.window.hide()
        cls.tmp.cleanup()

    def setUp(self):
        self.ctl.inserter = self.fake = FakeInserter()
        self.ctl.store.settings["equations"] = []
        self.panel.show_page("equation")
        self.panel.eq_input.clear()

    def test_the_page_is_remembered(self):
        self.assertEqual(self.ctl.store["page"], "equation")
        self.assertEqual(self.panel.pages.currentIndex(), 2)
        self.assertTrue(self.panel.info.isHidden())
        self.panel.show_page("search")
        self.assertFalse(self.panel.info.isHidden())

    def test_enter_types_plain_characters_when_they_are_exact(self):
        self.panel.eq_input.setText("Cl_2")
        self.assertEqual(self.panel.eq_text_btn.objectName(), "link")
        self.panel.insert_equation()
        self.assertEqual(self.fake.calls, [("text", "Cl₂")])
        self.assertEqual(self.ctl.store["equations"], ["Cl_2"])

    def test_enter_makes_an_equation_when_they_are_not(self):
        self.panel.eq_input.setText("(a+b)/c")
        self.assertEqual(self.panel.eq_math_btn.objectName(), "link")
        self.panel.insert_equation()
        kind, mathml_, plain = self.fake.calls[0]
        self.assertEqual((kind, plain), ("equation", "(a+b)/c"))
        self.assertIn("<mfrac>", mathml_)

    def test_command_enter_does_the_other(self):
        self.panel.eq_input.setText("6^2")
        self.panel.insert_equation(other=True)
        self.assertEqual(self.fake.calls[0][0], "equation")

    def test_nothing_typed_inserts_nothing(self):
        self.panel.insert_equation()
        self.assertEqual(self.fake.calls, [])
        self.assertFalse(self.panel.eq_math_btn.isEnabled())

    def test_a_structure_selects_its_first_slot_and_tab_moves_on(self):
        line = self.panel.eq_input
        self.panel.use_template("(□)/(□)")
        self.assertEqual((line.text(), line.selectionStart(), line.selectedText()), ("(□)/(□)", 1, "□"))
        line.insert("a")
        self.panel._next_hole()
        self.assertEqual(line.selectionStart(), 5)
        line.insert("b")
        self.assertEqual(line.text(), "(a)/(b)")

    def test_a_structure_wraps_what_was_selected(self):
        line = self.panel.eq_input
        line.setText("a+b")
        line.selectAll()
        self.panel.use_template("□^□")
        self.assertEqual((line.text(), line.selectedText()), ("(a+b)^□", "□"))

    def test_recent_equations_keep_the_newest_first_without_repeats(self):
        for source in ("x^2", "Cl_2", "x^2"):
            self.ctl.insert_maths(source, True)
        self.assertEqual(self.ctl.store["equations"], ["x^2", "Cl_2"])

    def test_copy_puts_both_forms_on_the_clipboard(self):
        self.ctl.copy_maths("x^2/y")
        kind, mathml_, plain = self.fake.calls[0]
        self.assertEqual((kind, plain), ("copy", "x²/y"))
        self.assertTrue(mathml_.startswith("<math "))


if __name__ == "__main__":
    unittest.main()
