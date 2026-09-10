# -*- coding: utf-8 -*-
"""Ricerca incrementale su un singolo QComboBox del modeler."""

from qgis.PyQt.QtCore import QObject, QStringListModel, Qt, QTimer
from qgis.PyQt.QtGui import QPalette
from qgis.PyQt.QtWidgets import QComboBox, QCompleter

from .plugin_support import FILTER_DEBOUNCE_MS, is_alive


class ComboSearchController(QObject):
    """Aggiunge una ricerca incrementale a un QComboBox esistente.

    Ogni istanza possiede tutto il proprio stato: nulla è condiviso fra
    combo diversi. È figlia Qt del combo che decora, quindi Qt la distrugge
    insieme a esso e non serve alcun registro manuale di oggetti vivi.

    Non conserva alcuna cache delle voci: le rilegge dal combo a ogni
    passata di filtro. Un combo del modeler ha al massimo qualche decina di
    voci, e il debounce le rilegge non più di una volta ogni 300 ms.
    """

    def __init__(self, combo):
        super().__init__(combo)
        self._combo = combo
        # Guardia di rientranza: la impostano `select_text` e
        # `reconcile_text`, che scrivono nel line edit e non devono
        # rilanciare il filtro su una modifica generata da noi stessi.
        self._updating = False
        # Stato originale del combo, da restituire in `detach()`: il
        # plugin non deve lasciare i widget di QGIS alterati quando viene
        # disattivato.
        self._was_editable = combo.isEditable()
        self._original_insert_policy = combo.insertPolicy()
        self._model = QStringListModel(self)
        self._completer = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.refresh_filter)

    # --- ciclo di vita -------------------------------------------------

    def attach(self):
        """Rende il combo ricercabile."""
        combo = self._combo
        if not is_alive(combo):
            return

        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )

        self._model.setStringList(self._live_items())

        line_edit = combo.lineEdit()
        line_edit.setCompleter(self._completer)
        # Stringa sorgente in inglese, come il resto dei testi rivolti
        # all'utente e come la documentazione: è la lingua base del plugin.
        # `tr()` permette di aggiungere un .qm italiano senza toccare il
        # codice. La versione precedente aveva l'italiano hardcoded.
        line_edit.setPlaceholderText(self.tr(u"\U0001F50D Type to filter..."))
        line_edit.textEdited.connect(self._on_text_edited)
        self._apply_search_style()

    # --- lettura del combo vivo ----------------------------------------

    def _live_items(self):
        """Le voci attualmente presenti nel combo. Nessuna cache."""
        combo = self._combo
        if not is_alive(combo):
            return []
        return [combo.itemText(i) for i in range(combo.count())]

    def current_candidates(self):
        """Le voci che il popup del completer mostra davvero all'utente.

        Legge il `completionModel()`, non il modello sorgente. La
        distinzione è sostanziale: il `QCompleter` applica un **proprio**
        filtro `MatchContains` usando `completionPrefix`, che Qt
        sincronizza da sé con l'intero testo digitato, sopra al modello che
        gli passiamo. Un metodo che leggesse il modello sorgente
        riporterebbe voci che l'utente non vede, e nasconderebbe ai test
        proprio le divergenze fra il nostro filtro e quello di Qt.
        """
        if self._completer is None:
            return []
        modello = self._completer.completionModel()
        return [
            modello.data(modello.index(riga, 0))
            for riga in range(modello.rowCount())
        ]

    # --- filtro ---------------------------------------------------------

    def _on_text_edited(self, _text):
        if self._updating:
            return
        self._timer.start(FILTER_DEBOUNCE_MS)

    def refresh_filter(self):
        """Rifiltra le voci in base al testo corrente del combo."""
        combo = self._combo
        if self._updating or not is_alive(combo):
            return
        line_edit = combo.lineEdit()
        if line_edit is None:
            return

        items = self._live_items()
        query = line_edit.text().strip().lower()
        if query:
            termini = query.split()
            items = [
                voce
                for voce in items
                if all(termine in voce.lower() for termine in termini)
            ]
        self._model.setStringList(items)
        # Azzerare il prefisso è indispensabile, non cosmetico. Qt
        # sincronizza `completionPrefix` con l'intero testo digitato, e il
        # completer lo riapplica come sottostringa sopra al nostro modello
        # già filtrato. Senza questo azzeramento una query multi-termine in
        # ordine invertito — "nuovi edifici" per la voce "Edifici nuovi" —
        # passa il nostro filtro e viene poi scartata da quello di Qt: il
        # popup resta vuoto. Verificato con digitazione reale, tasto per
        # tasto, su QGIS 3.40.2.
        self._completer.setCompletionPrefix("")

    # --- presentazione ---------------------------------------------------

    def _apply_search_style(self):
        """Bordo derivato dalla palette, così resta leggibile su tema scuro."""
        combo = self._combo
        colore = combo.palette().color(QPalette.ColorRole.Highlight).name()
        combo.lineEdit().setStyleSheet(
            "QLineEdit { border: 1px solid %s; border-radius: 3px;"
            " padding: 1px 4px; }" % colore
        )
