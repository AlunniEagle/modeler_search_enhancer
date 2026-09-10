# -*- coding: utf-8 -*-
"""Test del rilevamento event-driven che sostituisce il polling."""

import unittest

from qgis.PyQt.QtCore import QEvent
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

    def test_aprire_e_chiudere_piu_dialog_non_accumula_controller(self):
        # Il difetto originale: enhanced_combos non veniva mai ripulito e
        # accumulava wrapper di oggetti C++ già distrutti.
        for _ in range(3):
            dialog = build_dialog()
            dialog.show()
            QApplication.instance().processEvents()
            dialog.close()
            dialog.deleteLater()
            del dialog
            QApplication.instance().processEvents()

        ultimo = build_dialog()
        ultimo.show()
        QApplication.instance().processEvents()
        # I controller dei dialog chiusi devono essere stati potati.
        self.assertLessEqual(
            self.watcher.active_controller_count(),
            len(ultimo.findChildren(QComboBox)),
        )

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
