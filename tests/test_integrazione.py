# -*- coding: utf-8 -*-
"""Test end-to-end del ciclo di vita reale del plugin.

È il test che prova che il crash segnalato dalla community è risolto:
percorre lo stesso cammino di QGIS — `classFactory`, `initGui`, apertura
di un vero `ModelerParametersDialog`, `unload` — invece di esercitare i
moduli in isolamento.
"""

import unittest

from qgis.PyQt.QtWidgets import QApplication, QComboBox, QMainWindow

from modeler_search_enhancer import classFactory
from modeler_search_enhancer.tests.qgis_fixture import build_dialog, start_qgis


class IfaceFinto:
    """Il minimo di QgisInterface che il guscio del plugin usa davvero."""

    def __init__(self, finestra):
        self._finestra = finestra
        self.voci = []

    def mainWindow(self):
        return self._finestra

    def addPluginToMenu(self, menu, azione):
        self.voci.append((menu, azione))

    def removePluginMenu(self, menu, azione):
        self.voci = [v for v in self.voci if v[1] is not azione]


class TestCicloDiVitaDelPlugin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()
        cls.finestra = QMainWindow()

    def setUp(self):
        self.iface = IfaceFinto(self.finestra)
        self.plugin = classFactory(self.iface)

    def tearDown(self):
        # `unload` deve essere sicuro anche se `initGui` non è mai stato
        # chiamato, e ripetibile.
        self.plugin.unload()

    def test_classfactory_costruisce_il_plugin(self):
        self.assertEqual(type(self.plugin).__name__, "ModelerSearchEnhancer")

    def test_initgui_aggiunge_una_sola_voce_di_menu(self):
        self.plugin.initGui()
        self.assertEqual(len(self.iface.voci), 1)

    def test_un_dialog_del_modeler_viene_agganciato_dal_plugin_caricato(self):
        self.plugin.initGui()
        dialog = build_dialog()
        dialog.show()
        QApplication.instance().processEvents()
        self.assertGreater(self.plugin.watcher.active_controller_count(), 0)

    def test_unload_ripristina_i_combo_agganciati(self):
        self.plugin.initGui()
        dialog = build_dialog()
        dialog.show()
        QApplication.instance().processEvents()
        agganciati = self.plugin.watcher.active_controller_count()
        editabili_prima = sum(
            1 for c in dialog.findChildren(QComboBox) if c.isEditable())

        self.plugin.unload()
        editabili_dopo = sum(
            1 for c in dialog.findChildren(QComboBox) if c.isEditable())

        self.assertEqual(editabili_prima - editabili_dopo, agganciati)

    def test_unload_svuota_il_menu(self):
        self.plugin.initGui()
        self.plugin.unload()
        self.assertEqual(len(self.iface.voci), 0)

    def test_due_cicli_initgui_unload_non_sollevano(self):
        # Senza asserzioni sullo stato, un secondo `initGui()` che
        # duplicasse la voce di menu passerebbe inosservato.
        self.plugin.initGui()
        self.assertEqual(len(self.iface.voci), 1)
        self.plugin.unload()
        self.assertEqual(len(self.iface.voci), 0)

        self.plugin.initGui()
        self.assertEqual(len(self.iface.voci), 1)
        self.plugin.unload()
        self.assertEqual(len(self.iface.voci), 0)


if __name__ == "__main__":
    unittest.main()
