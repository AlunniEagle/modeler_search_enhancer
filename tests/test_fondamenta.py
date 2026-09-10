# -*- coding: utf-8 -*-
"""Test delle utilità condivise e dell'harness."""

import unittest

from modeler_search_enhancer.plugin_support import (
    FILTER_DEBOUNCE_MS,
    PLUGIN_TAG,
    SEARCH_MIN_ITEMS,
    is_alive,
)
from modeler_search_enhancer.tests.qgis_fixture import SOURCE_NAMES, start_qgis


class TestCostanti(unittest.TestCase):
    def test_soglia_minima_e_cinque(self):
        self.assertEqual(SEARCH_MIN_ITEMS, 5)

    def test_debounce_e_trecento_ms(self):
        self.assertEqual(FILTER_DEBOUNCE_MS, 300)

    def test_tag_non_vuoto(self):
        self.assertTrue(PLUGIN_TAG)


class TestIsAlive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_none_non_e_vivo(self):
        self.assertFalse(is_alive(None))

    def test_oggetto_normale_e_vivo(self):
        from qgis.PyQt.QtWidgets import QWidget
        widget = QWidget()
        self.assertTrue(is_alive(widget))

    def test_oggetto_distrutto_non_e_vivo(self):
        from qgis.PyQt import sip
        from qgis.PyQt.QtWidgets import QWidget
        widget = QWidget()
        sip.delete(widget)
        self.assertFalse(is_alive(widget))


class TestHarness(unittest.TestCase):
    def test_ci_sono_almeno_cinque_sorgenti(self):
        # Il criterio di selezione richiede count() >= 5: la fixture deve
        # produrre abbastanza input perché i combo lo superino.
        self.assertGreaterEqual(len(SOURCE_NAMES), 5)


if __name__ == "__main__":
    unittest.main()
