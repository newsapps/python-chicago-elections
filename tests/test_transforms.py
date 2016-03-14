import unittest

from chi_elections.transforms import replace_single_quotes

class TestTransforms(unittest.TestCase):
    def test_replace_single_quotes(self):
        self.assertEqual(replace_single_quotes("Roque ''Rocky'' De La Fuente"),
            'Roque "Rocky" De La Fuente')
