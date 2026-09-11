# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ModelerSearchEnhancer
                                 A QGIS plugin
 Ricerca avanzata per i parametri del Processing Modeler di QGIS
 ***************************************************************************/
"""

import os

from qgis.PyQt.QtCore import QCoreApplication, QSettings, QTranslator, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QAction, QApplication, QMessageBox

from .dialog_watcher import ModelerDialogWatcher

MENU_LABEL = u'&Modeler Search Enhancer'


def leggi_locale_utente(settings=None):
    """Le prime due lettere del locale utente, o stringa vuota.

    `QSettings.value` restituisce None quando la chiave non esiste, cosa
    che accade su un profilo QGIS appena creato. La versione precedente
    affettava direttamente il risultato e sollevava TypeError, impedendo il
    caricamento del plugin.
    """
    if settings is None:
        settings = QSettings()
    valore = settings.value('locale/userLocale')
    if not valore:
        return ""
    return str(valore)[0:2]


class ModelerSearchEnhancer:
    """Guscio del plugin: installa il watcher e gestisce il menu.

    È l'unico modulo che conosce `iface`. Tutta la logica di rilevamento e
    di ricerca vive in `dialog_watcher` e `combo_search`, che sono
    testabili senza GUI.
    """

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.watcher = None
        self.translator = None

        locale = leggi_locale_utente()
        if locale:
            locale_path = os.path.join(
                self.plugin_dir, 'i18n',
                'ModelerSearchEnhancer_{}.qm'.format(locale))
            if os.path.exists(locale_path):
                self.translator = QTranslator()
                self.translator.load(locale_path)
                QCoreApplication.installTranslator(self.translator)

    def tr(self, message):
        """Traduce `message` con il sistema di traduzione di QGIS."""
        return QCoreApplication.translate('ModelerSearchEnhancer', message)

    def initGui(self):
        """Installa il watcher e aggiunge la voce di aiuto al menu."""
        self.watcher = ModelerDialogWatcher()
        QApplication.instance().installEventFilter(self.watcher)

        help_action = QAction(
            QIcon(':/images/themes/default/mActionHelpContents.svg'),
            self.tr(u'Help'),
            self.iface.mainWindow())
        help_action.setStatusTip(self.tr(u'Show the plugin documentation'))
        help_action.triggered.connect(self.showHelp)

        self.iface.addPluginToMenu(self.tr(MENU_LABEL), help_action)
        self.actions.append(help_action)

    def showHelp(self):
        """Apre `help.html` nel browser di sistema."""
        help_file = os.path.join(self.plugin_dir, 'help.html')
        if os.path.exists(help_file):
            QDesktopServices.openUrl(QUrl.fromLocalFile(help_file))
            return
        QMessageBox.warning(
            self.iface.mainWindow(),
            self.tr(u'Help file not found'),
            self.tr(u'Documentation not found at:\n{}').format(help_file))

    def unload(self):
        """Ripristina i combo, rimuove il watcher e svuota il menu."""
        if self.watcher is not None:
            QApplication.instance().removeEventFilter(self.watcher)
            self.watcher.detach_all()
            self.watcher = None

        for action in self.actions:
            self.iface.removePluginMenu(self.tr(MENU_LABEL), action)
        self.actions = []

        if self.translator is not None:
            QCoreApplication.removeTranslator(self.translator)
            self.translator = None
