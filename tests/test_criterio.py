# -*- coding: utf-8 -*-
"""Test del criterio che decide quali combo migliorare."""

import unittest

from qgis.PyQt.QtWidgets import QComboBox

from modeler_search_enhancer.dialog_watcher import should_enhance
from modeler_search_enhancer.tests.qgis_fixture import start_qgis


def combo_con(items_e_dati):
    """Un QComboBox popolato con coppie (testo, itemData)."""
    combo = QComboBox()
    for testo, dato in items_e_dati:
        combo.addItem(testo, dato)
    return combo


class TestShouldEnhance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_combo_di_input_del_modello_va_migliorato(self):
        # itemData str = riferimento a un input del modello.
        combo = combo_con([("Layer %d" % i, "KEY_%d" % i) for i in range(6)])
        self.assertTrue(should_enhance(combo))

    def test_combo_di_output_di_algoritmo_va_migliorato(self):
        # itemData list = [childId, nomeOutput].
        combo = combo_con(
            [("Output %d" % i, ["child_%d" % i, "OUTPUT"]) for i in range(6)]
        )
        self.assertTrue(should_enhance(combo))

    def test_combo_booleano_non_va_migliorato(self):
        # Anche con abbastanza voci, un booleano non si cerca.
        combo = combo_con([("Sì", True), ("No", False)] * 3)
        self.assertFalse(should_enhance(combo))

    def test_combo_di_enumerato_non_va_migliorato(self):
        # itemData int = indice dell'opzione di un QgsProcessingParameterEnum.
        combo = combo_con([("Opzione %d" % i, i) for i in range(6)])
        self.assertFalse(should_enhance(combo))

    def test_combo_senza_itemData_non_va_migliorato(self):
        combo = QComboBox()
        combo.addItems(["a", "b", "c", "d", "e", "f"])
        self.assertFalse(should_enhance(combo))

    def test_combo_troppo_corto_non_va_migliorato(self):
        combo = combo_con([("Layer %d" % i, "KEY_%d" % i) for i in range(4)])
        self.assertFalse(should_enhance(combo))

    def test_combo_al_limite_va_migliorato(self):
        combo = combo_con([("Layer %d" % i, "KEY_%d" % i) for i in range(5)])
        self.assertTrue(should_enhance(combo))

    def test_combo_vuoto_non_va_migliorato(self):
        self.assertFalse(should_enhance(QComboBox()))

    def test_none_non_va_migliorato(self):
        self.assertFalse(should_enhance(None))

    def test_combo_distrutto_non_va_migliorato(self):
        from qgis.PyQt import sip
        combo = combo_con([("Layer %d" % i, "KEY_%d" % i) for i in range(6)])
        sip.delete(combo)
        self.assertFalse(should_enhance(combo))


if __name__ == "__main__":
    unittest.main()
