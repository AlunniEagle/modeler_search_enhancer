# -*- coding: utf-8 -*-
"""Rilevamento dei dialog del modeler e scoperta dei combo da migliorare."""

from qgis.PyQt.QtCore import QEvent, QObject, QTimer
from qgis.PyQt.QtWidgets import QComboBox
from qgis.gui import QgsProcessingModelerParameterWidget

from .combo_search import ComboSearchController
from .plugin_support import SEARCH_MIN_ITEMS, is_alive, log_error

MODELER_DIALOG_OBJECT_NAME = "ModelerParametersDialog"


def should_enhance(combo):
    """True se `combo` elenca sorgenti del modello e vale la pena filtrarlo.

    Il criterio è strutturale e non guarda il testo delle voci: le etichette
    sono tradotte e usano virgolette tipografiche, quindi qualunque
    euristica testuale sarebbe fragile e legata alla lingua.

    Il tipo di `itemData` distingue le sorgenti da tutto il resto:

    - `str`  -> chiave di un input del modello
    - `list` -> coppia [childId, nomeOutput] di un output di algoritmo
    - `bool` -> parametro booleano (Sì/No)
    - `int`  -> indice di opzione di un parametro enumerato

    Il controllo è una lista chiusa di tipi ammessi, non una lista di
    esclusioni: in Python `bool` è sottoclasse di `int`, quindi un controllo
    per esclusione renderebbe significativo l'ordine dei test. Con
    l'allowlist la questione non si pone.
    """
    if not is_alive(combo):
        return False
    if combo.count() < SEARCH_MIN_ITEMS:
        return False
    return isinstance(combo.itemData(0), (str, list))


def find_source_combos(dialog):
    """I QComboBox di `dialog` che elencano sorgenti del modello.

    La ricerca è limitata al dialog passato: non si enumerano mai liste
    globali di widget. Usa `isinstance` tramite `findChildren` sulla classe
    reale, non un confronto su `type(w).__name__`, che sarebbe
    silenziosamente falsificabile da una classe omonima.
    """
    if not is_alive(dialog):
        return []
    combos = []
    for widget in dialog.findChildren(QgsProcessingModelerParameterWidget):
        for combo in widget.findChildren(QComboBox):
            if should_enhance(combo):
                combos.append(combo)
    return combos


class ModelerDialogWatcher(QObject):
    """Aggancia la ricerca ai dialog del modeler quando vengono mostrati.

    Sostituisce il polling di `QgsApplication.allWidgets()`, che era la
    causa dei crash: quel polling enumerava ogni QWidget esistente, inclusi
    quelli a metà costruzione e quelli già distrutti in C++, e scattava
    anche dentro gli event loop annidati dei dialog nativi di Windows.

    Qui non si enumera nulla di globale. Si reagisce al solo `Show` di un
    dialog identificato per `objectName`, e l'aggancio è rimandato con
    `singleShot(0)`: il dialog è già costruito quando riceve `Show`, e il
    rinvio ci sposta fuori dallo stack di consegna dell'evento, dove il
    dialog è ancora dentro il proprio `showEvent`.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._controllers = []

    def eventFilter(self, obj, event):
        # Percorso caldo: questo metodo riceve ogni evento
        # dell'applicazione. Un confronto di interi e si esce. Non
        # aggiungere lavoro qui.
        if event.type() == QEvent.Type.Show:
            try:
                if obj.objectName() == MODELER_DIALOG_OBJECT_NAME:
                    QTimer.singleShot(0, lambda d=obj: self.enhance_dialog(d))
            except (AttributeError, RuntimeError):
                # obj può non essere più valido, o non essere un QObject
                # con objectName: non è un errore da segnalare.
                pass
        return False

    def enhance_dialog(self, dialog):
        """Aggancia un controller a ogni combo sorgente di `dialog`.

        Restituisce il numero di combo agganciati.
        """
        self._prune()
        if not is_alive(dialog):
            return 0
        agganciati = 0
        try:
            for combo in find_source_combos(dialog):
                controller = ComboSearchController(combo)
                controller.attach()
                self._controllers.append(controller)
                agganciati += 1
        except Exception as exc:  # noqa: BLE001
            log_error("Aggancio del dialog non riuscito: {}".format(exc))
        return agganciati

    def _prune(self):
        """Scarta i controller i cui combo Qt ha già distrutto.

        I controller sono figli Qt dei rispettivi combo, quindi muoiono con
        essi: qui si rimuovono solo i riferimenti Python rimasti, che è
        proprio l'accumulo che il plugin originale non faceva mai.
        """
        self._controllers = [c for c in self._controllers if is_alive(c)]

    def active_controller_count(self):
        """Quanti controller sono attualmente attivi."""
        self._prune()
        return len(self._controllers)

    def detach_all(self):
        """Ripristina ogni combo agganciato. Invocato da `unload()`."""
        for controller in self._controllers:
            if not is_alive(controller):
                continue
            try:
                controller.detach()
            except Exception as exc:  # noqa: BLE001
                log_error("Ripristino di un combo non riuscito: {}".format(exc))
        self._controllers = []
