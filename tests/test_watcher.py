# -*- coding: utf-8 -*-
"""Test del rilevamento event-driven che sostituisce il polling."""

import unittest

from qgis.PyQt.QtCore import QCoreApplication, QEvent
from qgis.PyQt.QtWidgets import QApplication, QComboBox, QDialog

from modeler_search_enhancer.dialog_watcher import (
    MODELER_DIALOG_OBJECT_NAME,
    ModelerDialogWatcher,
    find_source_combos,
)
from modeler_search_enhancer.tests.qgis_fixture import build_dialog, start_qgis


class TestEventFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def setUp(self):
        self.watcher = ModelerDialogWatcher()
        QApplication.instance().installEventFilter(self.watcher)

    def tearDown(self):
        QApplication.instance().removeEventFilter(self.watcher)
        self.watcher.detach_all()

    def test_il_filtro_restituisce_sempre_false(self):
        # Restituire True bloccherebbe l'evento e romperebbe QGIS.
        dialog = QDialog()
        esito = self.watcher.eventFilter(dialog, QEvent(QEvent.Type.Show))
        self.assertFalse(esito)

    def test_dialog_del_modeler_viene_agganciato(self):
        dialog = build_dialog()
        dialog.show()
        QApplication.instance().processEvents()
        self.assertGreater(self.watcher.active_controller_count(), 0)

    def test_dialog_estraneo_viene_ignorato(self):
        estraneo = QDialog()
        estraneo.setObjectName("QualcosAltro")
        combo = QComboBox(estraneo)
        for i in range(6):
            combo.addItem("Voce %d" % i, "KEY_%d" % i)
        estraneo.show()
        QApplication.instance().processEvents()
        self.assertEqual(self.watcher.active_controller_count(), 0)

    def test_objectname_atteso_e_quello_di_qgis(self):
        self.assertEqual(MODELER_DIALOG_OBJECT_NAME, "ModelerParametersDialog")

    def test_i_controller_dei_dialog_chiusi_vengono_potati(self):
        # Questa è l'altra metà del difetto che il task chiude: la versione
        # precedente non ripuliva mai il proprio registro di combo e
        # accumulava wrapper di oggetti C++ già distrutti.
        #
        # Due accortezze rendono il test non vacuo, entrambe verificate
        # empiricamente su Qt5 e Qt6:
        #
        # - `close()` + `deleteLater()` + `processEvents()` **non**
        #   distrugge i widget: gli eventi `DeferredDelete` vanno pompati
        #   esplicitamente. Senza la pompa i controller restano vivi e il
        #   test non misurerebbe nulla.
        # - l'asserzione è sullo zero esatto, non su una soglia. Una soglia
        #   pari al numero di combo per dialog è soddisfatta anche con la
        #   potatura completamente disattivata.
        #
        # Con `_prune()` resa inerte questo test falla al primo giro.
        for _ in range(3):
            dialog = build_dialog()
            dialog.show()
            QApplication.instance().processEvents()
            self.assertGreater(self.watcher.active_controller_count(), 0)

            dialog.close()
            dialog.deleteLater()
            del dialog
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            QApplication.instance().processEvents()

            self.assertEqual(self.watcher.active_controller_count(), 0)

    def test_enhance_dialog_su_none_non_solleva(self):
        self.assertEqual(self.watcher.enhance_dialog(None), 0)

    def test_detach_all_azzera_il_conteggio(self):
        dialog = build_dialog()
        dialog.show()
        QApplication.instance().processEvents()
        self.watcher.detach_all()
        self.assertEqual(self.watcher.active_controller_count(), 0)

    def test_enhance_dialog_e_idempotente(self):
        # Regressione di I2: un secondo aggancio allo stesso dialog non deve
        # aumentare il conteggio dei controller, né impedire a
        # `detach_all()` di riportare tutti i combo a non editabile. Con la
        # guardia disattivata il secondo controller fotograferebbe
        # `isEditable()` già a True, e dopo `detach_all()` il combo
        # resterebbe editabile.
        dialog = build_dialog()
        dialog.show()
        QApplication.instance().processEvents()
        primo_conteggio = self.watcher.active_controller_count()
        self.assertGreater(primo_conteggio, 0)

        # Solo i combo che il plugin gestisce davvero: il dialog reale
        # contiene anche altri QComboBox nativi di QGIS, alcuni editabili
        # di loro, che non c'entrano con l'idempotenza sotto test.
        combos_gestiti = find_source_combos(dialog)
        self.assertTrue(combos_gestiti)

        agganciati_di_nuovo = self.watcher.enhance_dialog(dialog)
        self.assertEqual(agganciati_di_nuovo, 0)
        self.assertEqual(self.watcher.active_controller_count(), primo_conteggio)

        self.watcher.detach_all()
        self.assertFalse(any(combo.isEditable() for combo in combos_gestiti))

    def test_laggancio_e_rimandato_non_sincrono(self):
        # Lo `Show` è consegnato in modo sincrono da `show()`, ma
        # `eventFilter` rimanda l'aggancio con `QTimer.singleShot(0, ...)`.
        # Subito dopo `show()`, prima di pompare l'event loop, non deve
        # ancora esserci nessun controller: è il vincolo anti-crash che
        # sposta l'aggancio fuori dallo stack di consegna dell'evento. Con
        # una chiamata diretta al posto di `singleShot` questo primo assert
        # fallirebbe.
        dialog = build_dialog()
        dialog.show()
        self.assertEqual(self.watcher.active_controller_count(), 0)

        QApplication.instance().processEvents()
        self.assertGreater(self.watcher.active_controller_count(), 0)


if __name__ == "__main__":
    unittest.main()
