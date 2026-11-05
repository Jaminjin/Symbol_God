import unittest

from symbolpad.symbols import SymbolIndex


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = SymbolIndex()

    def first(self, query):
        results = self.index.search(query)
        return results[0].char if results else None

    def test_names_and_everyday_words(self):
        self.assertEqual(self.first("alpha"), "α")
        self.assertEqual(self.first("Delta"), "Δ")
        self.assertEqual(self.first("integral"), "∫")
        self.assertEqual(self.first("not equal"), "≠")
        self.assertEqual(self.first("less than or equal"), "≤")
        self.assertEqual(self.first("therefore"), "∴")
        self.assertEqual(self.first("degree"), "°")
        self.assertEqual(self.first("real numbers"), "ℝ")
        self.assertEqual(self.first("equilibrium"), "⇌")

    def test_latex_and_codes(self):
        self.assertEqual(self.first("\\leq"), "≤")
        self.assertEqual(self.first("\\rightarrow"), "→")
        self.assertEqual(self.first("\\mathbb{R}"), "ℝ")
        self.assertEqual(self.first("^2"), "²")
        self.assertEqual(self.first("U+2192"), "→")
        self.assertEqual(self.first("&#945;"), "α")

    def test_typing_a_symbol_shows_it_first(self):
        self.assertEqual(self.first("α"), "α")
        self.assertEqual(self.first("→"), "→")

    def test_combining_marks(self):
        self.assertEqual(self.first("x bar"), "̄")
        self.assertEqual(self.first("vector"), "⃗")

    def test_every_curated_symbol_has_a_name(self):
        for _key, _title, _icon, chars in self.index.categories:
            for ch in chars:
                self.assertIsNotNone(self.index.get(ch), ch)


if __name__ == "__main__":
    unittest.main()
