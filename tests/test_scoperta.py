# -*- coding: utf-8 -*-
"""Test della scoperta dei combo su un dialog reale del modeler."""

import unittest

from qgis.PyQt.QtWidgets import QComboBox, QDialog
from qgis.gui import QgsProcessingModelerParameterWidget

from modeler_search_enhancer.dialog_watcher import find_source_combos
from modeler_search_enhancer.tests.qgis_fixture import build_dialog, start_qgis


class TestFindSourceCombos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()
        cls.dialog = build_dialog()

    def test_trova_almeno_un_combo(self):
        self.assertTrue(find_source_combos(self.dialog))

    def test_i_combo_trovati_stanno_sotto_un_parameter_widget(self):
        # L'aggancio strutturale: nessun combo fuori da un
        # QgsProcessingModelerParameterWidget deve essere restituito.
        #
        # L'invariante si verifica risalendo la catena degli antenati, non
        # confrontando `id()` fra due traversate. `id()` qui sarebbe
        # scorretto: i wrapper Python restituiti da un `findChildren()`
        # temporaneo vengono deallocati appena la lista esce di scope, e
        # l'indirizzo che `id()` ha registrato può essere riusato da un
        # oggetto diverso. Si confronterebbero identità stantie.
        trovati = find_source_combos(self.dialog)
        self.assertTrue(trovati)
        for combo in trovati:
            antenato = combo.parent()
            while antenato is not None and not isinstance(
                antenato, QgsProcessingModelerParameterWidget
            ):
                antenato = antenato.parent()
            self.assertIsInstance(antenato, QgsProcessingModelerParameterWidget)

    def test_i_combo_trovati_hanno_itemdata_di_sorgente(self):
        for combo in find_source_combos(self.dialog):
            self.assertIsInstance(combo.itemData(0), (str, list))
            self.assertNotIsInstance(combo.itemData(0), bool)

    def test_almeno_un_combo_trovato_e_di_output_di_algoritmo(self):
        # Criterio di accettazione di I4: la fixture deve mettere abbastanza
        # algoritmi a monte perché il ramo `list` di `itemData` — gli
        # output di algoritmo, il caso d'uso principale del plugin — sia
        # davvero esercitato su un dialog reale, e non solo su un combo
        # sintetico come in test_criterio.py.
        tipi = [type(combo.itemData(0)) for combo in find_source_combos(self.dialog)]
        self.assertIn(list, tipi)

    def test_esclude_i_combo_booleani(self):
        # Un combo booleano reale ha solo 2 voci (Sì/No) ed è già escluso
        # dal gate sul conteggio: verificarlo su `find_source_combos(dialog)`
        # non proverebbe mai che l'esclusione dipende dal *tipo*. Si
        # costruisce quindi un combo sintetico con 6 voci booleane, sopra
        # la soglia, così l'unica ragione per cui `should_enhance` lo scarta
        # è il tipo di `itemData`.
        from modeler_search_enhancer.dialog_watcher import should_enhance

        combo = QComboBox()
        for i in range(6):
            combo.addItem("Opzione %d" % i, i % 2 == 0)
        self.assertFalse(should_enhance(combo))

    def test_le_virgolette_tipografiche_non_ostacolano_il_rilevamento(self):
        # Le etichette degli output di algoritmo usano U+201C/U+201D, non
        # il doppio apice ASCII. Il gate primario della versione precedente
        # cercava `"` e quindi non corrispondeva mai.
        from modeler_search_enhancer.dialog_watcher import should_enhance

        combo = QComboBox()
        left_q = chr(0x201c)
        right_q = chr(0x201d)
        for i in range(6):
            etichetta = left_q + u'Output %d' + right_q + u' from algorithm ' + left_q + u'Passo %d' + right_q
            etichetta = etichetta % (i, i)
            combo.addItem(etichetta, ["child_%d" % i, "OUTPUT"])
        self.assertNotIn(u'"', combo.itemText(0))
        self.assertIn(left_q, combo.itemText(0))
        self.assertTrue(should_enhance(combo))

    def test_dialog_senza_parameter_widget_non_da_nulla(self):
        vuoto = QDialog()
        combo = QComboBox(vuoto)
        combo.addItems(["a", "b", "c", "d", "e", "f"])
        self.assertEqual(find_source_combos(vuoto), [])

    def test_none_non_solleva(self):
        self.assertEqual(find_source_combos(None), [])


if __name__ == "__main__":
    unittest.main()
