# -*- coding: utf-8 -*-
"""Utilità condivise: compatibilità Qt5/Qt6, log, costanti.

Questo modulo non importa nessun altro modulo del plugin, così da poter
essere usato da tutti gli altri senza cicli.
"""

from qgis.PyQt import sip
from qgis.core import Qgis, QgsMessageLog

PLUGIN_TAG = "Modeler Search Enhancer"

# Numero minimo di voci perché un filtro di ricerca aggiunga valore: sotto
# questa soglia la tendina nativa di Qt è già adeguata. È una scelta di
# prodotto, isolata qui per poterla cambiare senza toccare la logica.
SEARCH_MIN_ITEMS = 5

# Millisecondi di attesa dopo l'ultimo tasto prima di rifiltrare.
FILTER_DEBOUNCE_MS = 300


def log_warning(message):
    """Registra un avviso nel pannello dei log di QGIS."""
    QgsMessageLog.logMessage(message, PLUGIN_TAG, Qgis.MessageLevel.Warning)


def log_error(message):
    """Registra un errore nel pannello dei log di QGIS."""
    QgsMessageLog.logMessage(message, PLUGIN_TAG, Qgis.MessageLevel.Critical)


def is_alive(obj):
    """True se l'oggetto C++ sottostante a `obj` esiste ancora.

    PyQt tiene vivo il wrapper Python anche dopo che Qt ha distrutto
    l'oggetto C++; invocare un metodo su un wrapper del genere solleva
    RuntimeError. Questo è il pre-controllo economico che evita di
    arrivarci.
    """
    if obj is None:
        return False
    try:
        return not sip.isdeleted(obj)
    except (TypeError, RuntimeError):
        return False
