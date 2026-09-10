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


class TestRisoluzioneSulComboVivo(unittest.TestCase):
    """Regressione di CR-3: la selezione usava un indice su uno snapshot."""

    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_selezione_imposta_il_currentdata_giusto(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()

        self.assertTrue(controller.select_text("Edifici nuovi"))
        self.assertEqual(combo.currentData(), "EDIFICI_NUOVI")
        self.assertEqual(combo.currentText(), "Edifici nuovi")

    def test_selezione_dopo_ripopolamento_resta_corretta(self):
        # Il modeler ripopola i combo quando cambiano gli algoritmi a monte.
        # Con lo snapshot, l'indice puntava alla voce sbagliata.
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()

        combo.clear()
        for nome in ["Reticolo idrico", "Edifici nuovi", "Aree verdi"]:
            combo.addItem(nome, nome.replace(" ", "_").upper())

        self.assertTrue(controller.select_text("Edifici nuovi"))
        self.assertEqual(combo.currentData(), "EDIFICI_NUOVI")

    def test_il_filtro_dopo_ripopolamento_usa_le_voci_nuove(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()

        combo.clear()
        for nome in ["Reticolo idrico", "Aree verdi"]:
            combo.addItem(nome, nome.replace(" ", "_").upper())

        digita(controller, combo, "")
        self.assertEqual(
            controller.current_candidates(), ["Reticolo idrico", "Aree verdi"]
        )

    def test_testo_inesistente_non_cambia_la_selezione(self):
        combo = combo_sorgenti()
        combo.setCurrentIndex(2)
        controller = ComboSearchController(combo)
        controller.attach()

        self.assertFalse(controller.select_text("non esiste"))
        self.assertEqual(combo.currentData(), "EDIFICI_STORICI")

    def test_selezione_su_combo_distrutto_non_solleva(self):
        from qgis.PyQt import sip
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        sip.delete(combo)
        self.assertFalse(controller.select_text("Edifici nuovi"))

    def test_il_completer_attivato_seleziona_la_voce(self):
        # Il segnale `activated` del completer è l'unica via per cui la
        # scelta fatta nel popup arriva a `select_text`. Senza questo test,
        # rimuovere il collegamento in `attach()` non farebbe fallire
        # nulla: il meccanismo resterebbe corretto ma irraggiungibile.
        #
        # Il completer si ottiene dall'API pubblica del line edit, senza
        # toccare attributi privati del controller.
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()

        completer = combo.lineEdit().completer()
        self.assertIsNotNone(completer)
        completer.activated[str].emit("Edifici nuovi")

        self.assertEqual(combo.currentData(), "EDIFICI_NUOVI")


class TestRiconciliazioneDelTesto(unittest.TestCase):
    """Il widget non deve mostrare un testo diverso dal valore reale."""

    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_testo_libero_viene_ripristinato(self):
        combo = combo_sorgenti()
        combo.setCurrentIndex(1)
        controller = ComboSearchController(combo)
        controller.attach()

        combo.lineEdit().setText("qualcosa che non esiste")
        controller.reconcile_text()

        self.assertEqual(combo.lineEdit().text(), "Strade rurali")
        self.assertEqual(combo.currentData(), "STRADE_RURALI")

    def test_testo_valido_non_viene_toccato(self):
        # Un testo che corrisponde a una voce reale deve restare com'è.
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        combo.lineEdit().setText("Edifici nuovi")
        controller.reconcile_text()
        self.assertEqual(combo.lineEdit().text(), "Edifici nuovi")

    def test_riconciliazione_su_combo_distrutto_non_solleva(self):
        from qgis.PyQt import sip
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        sip.delete(combo)
        controller.reconcile_text()  # non deve sollevare


class TestDetach(unittest.TestCase):
    """unload() deve restituire i combo come li ha trovati."""

    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_detach_ripristina_non_editabile(self):
        combo = combo_sorgenti()
        self.assertFalse(combo.isEditable())
        controller = ComboSearchController(combo)
        controller.attach()
        self.assertTrue(combo.isEditable())

        controller.detach()
        self.assertFalse(combo.isEditable())

    def test_detach_ripristina_il_testo_corretto(self):
        combo = combo_sorgenti()
        combo.setCurrentIndex(3)
        controller = ComboSearchController(combo)
        controller.attach()
        combo.lineEdit().setText("spazzatura")

        controller.detach()
        self.assertEqual(combo.currentText(), "Edifici nuovi")
        self.assertEqual(combo.currentData(), "EDIFICI_NUOVI")

    def test_detach_ripristina_la_insert_policy(self):
        combo = combo_sorgenti()
        originale = combo.insertPolicy()
        controller = ComboSearchController(combo)
        controller.attach()
        controller.detach()
        self.assertEqual(combo.insertPolicy(), originale)

    def test_detach_e_idempotente(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        controller.detach()
        controller.detach()  # non deve sollevare
        self.assertFalse(combo.isEditable())

    def test_detach_su_combo_distrutto_non_solleva(self):
        from qgis.PyQt import sip
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        sip.delete(combo)
        controller.detach()  # non deve sollevare


if __name__ == "__main__":
    unittest.main()
