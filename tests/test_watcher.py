# -*- coding: utf-8 -*-
"""Test del rilevamento event-driven che sostituisce il polling."""

import unittest

from qgis.PyQt.QtCore import QCoreApplication, QEvent
from qgis.PyQt.QtWidgets import QApplication, QComboBox, QDialog

from modeler_search_enhancer.dialog_watcher import (
    MODELER_DIALOG_OBJECT_NAME,
    ModelerDialogWatcher,
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


if __name__ == "__main__":
    unittest.main()
