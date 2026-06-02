import unittest


class AritmeticaUnitarios(unittest.TestCase):
    def test_adicao(self):
        resultado = 1 + 2
        self.assertEqual(resultado, 3)


if __name__ == "__main__":
    unittest.main()
