# -*- coding: utf-8 -*-
"""Test del filtro di ricerca su un combo."""

import unittest

from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QComboBox

from modeler_search_enhancer.combo_search import ComboSearchController
from modeler_search_enhancer.tests.qgis_fixture import SOURCE_NAMES, start_qgis


def combo_sorgenti():
    """Un combo popolato come quelli del modeler: testo + chiave in itemData."""
    combo = QComboBox()
    for nome in SOURCE_NAMES:
        combo.addItem(nome, nome.replace(" ", "_").upper())
    return combo


def digita(controller, combo, testo):
    """Simula la digitazione e forza il filtro senza attendere il debounce."""
    combo.lineEdit().setText(testo)
    controller.refresh_filter()


class TestFiltro(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_query_vuota_offre_tutte_le_voci(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        digita(controller, combo, "")
        self.assertEqual(controller.current_candidates(), SOURCE_NAMES)

    def test_filtro_e_case_insensitive(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        digita(controller, combo, "STRADE")
        self.assertEqual(
            controller.current_candidates(), ["Strade urbane", "Strade rurali"]
        )

    def test_filtro_su_sottostringa_interna(self):
        # MatchContains: "urban" non è un prefisso di "Strade urbane".
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        digita(controller, combo, "urban")
        self.assertEqual(controller.current_candidates(), ["Strade urbane"])

    def test_filtro_multi_termine_in_and(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        digita(controller, combo, "edifici nuovi")
        self.assertEqual(controller.current_candidates(), ["Edifici nuovi"])

    def test_termini_in_ordine_qualsiasi(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        digita(controller, combo, "nuovi edifici")
        self.assertEqual(controller.current_candidates(), ["Edifici nuovi"])

    def test_query_senza_risultati_da_lista_vuota(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        digita(controller, combo, "zzzz")
        self.assertEqual(controller.current_candidates(), [])

    def test_digitazione_reale_tasto_per_tasto(self):
        # `setText()` non genera gli eventi di tastiera che fanno
        # sincronizzare a Qt il `completionPrefix` del completer. Questo
        # test digita davvero, tasto per tasto, ed è l'unico che vede il
        # popup nelle stesse condizioni dell'utente: senza l'azzeramento
        # del prefisso in `refresh_filter`, la query in ordine invertito
        # qui sotto restituirebbe una lista vuota.
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()

        combo.lineEdit().clear()
        QTest.keyClicks(combo.lineEdit(), "nuovi edifici")
        controller.refresh_filter()

        self.assertEqual(controller.current_candidates(), ["Edifici nuovi"])


class TestIndipendenzaFraCombo(unittest.TestCase):
    """Regressione di CR-2: lo stato era condiviso sul singleton del plugin."""

    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_due_combo_filtrano_entrambi(self):
        primo, secondo = combo_sorgenti(), combo_sorgenti()
        c1, c2 = ComboSearchController(primo), ComboSearchController(secondo)
        c1.attach()
        c2.attach()

        digita(c1, primo, "strade")
        digita(c2, secondo, "edifici")

        self.assertEqual(
            c1.current_candidates(), ["Strade urbane", "Strade rurali"]
        )
        self.assertEqual(
            c2.current_candidates(), ["Edifici storici", "Edifici nuovi"]
        )

    def test_la_stessa_query_nel_secondo_combo_filtra_comunque(self):
        # Con _last_search_text condiviso questo era il caso che non
        # filtrava affatto: la guardia usciva subito.
        primo, secondo = combo_sorgenti(), combo_sorgenti()
        c1, c2 = ComboSearchController(primo), ComboSearchController(secondo)
        c1.attach()
        c2.attach()

        digita(c1, primo, "strade")
        digita(c2, secondo, "strade")

        self.assertEqual(
            c2.current_candidates(), ["Strade urbane", "Strade rurali"]
        )

    def test_il_controller_e_figlio_qt_del_combo(self):
        # Garantisce che Qt lo distrugga insieme al combo: è ciò che
        # sostituisce il bookkeeping manuale che accumulava riferimenti.
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        self.assertIs(controller.parent(), combo)


if __name__ == "__main__":
    unittest.main()
