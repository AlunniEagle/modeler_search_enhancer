# -*- coding: utf-8 -*-
"""Avvio di QGIS headless e costruzione di un dialog reale del modeler.

Costruire un vero ModelerParametersDialog, invece di un finto QDialog, è
ciò che rende i test capaci di cogliere le regressioni: la struttura dei
widget e i tipi di itemData sono quelli reali.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# I sei input del modello. I nomi sono scelti per avere prefissi condivisi,
# così i test possono verificare il filtro multi-termine.
SOURCE_NAMES = [
    "Strade urbane",
    "Strade rurali",
    "Edifici storici",
    "Edifici nuovi",
    "Confini comunali",
    "Punti di interesse",
]

_app = None


def start_qgis():
    """Avvia QgsApplication una volta per processo e la restituisce."""
    global _app
    if _app is not None:
        return _app

    from qgis.core import QgsApplication

    _app = QgsApplication([], False)
    _app.initQgis()
    sys.path.append(os.path.join(QgsApplication.prefixPath(), "python", "plugins"))
    from processing.core.Processing import Processing

    Processing.initialize()
    return _app


def chiave_di(nome):
    """La chiave del parametro di modello derivata dal suo nome visibile.

    Usata sia per registrare i parametri del modello sia per riferirli in
    `fromModelParameter`, così le due derivazioni non possono andare fuori
    sincrono se `SOURCE_NAMES` cambia.
    """
    return nome.replace(" ", "_").upper()


# Descrizioni dei bufferi a monte. Devono essere abbastanza numerosi perché,
# nel dialog reale, il combo degli output di algoritmo superi le 5 voci del
# gate `SEARCH_MIN_ITEMS`: con un solo algoritmo a monte quel combo ha 1
# sola voce e il ramo `list` di `itemData` — gli output di algoritmo, il
# caso d'uso principale del plugin — non viene mai esercitato su un dialog
# reale.
BUFFER_DESCRIPTIONS = [
    "Buffer delle strade urbane",
    "Buffer delle strade rurali",
    "Buffer degli edifici storici",
    "Buffer degli edifici nuovi",
    "Buffer dei confini comunali",
    "Buffer dei punti di interesse",
]


def build_dialog():
    """Un ModelerParametersDialog reale con 6 input e 6 algoritmi figli a monte."""
    start_qgis()

    from qgis.core import (
        QgsApplication,
        QgsProcessingModelAlgorithm,
        QgsProcessingModelChildAlgorithm,
        QgsProcessingModelChildParameterSource,
        QgsProcessingModelParameter,
        QgsProcessingParameterFeatureSource,
    )
    from processing.modeler.ModelerParametersDialog import ModelerParametersDialog

    model = QgsProcessingModelAlgorithm("test", "test")
    for name in SOURCE_NAMES:
        key = chiave_di(name)
        model.addModelParameter(
            QgsProcessingParameterFeatureSource(key, name),
            QgsProcessingModelParameter(key),
        )

    for indice, descrizione in enumerate(BUFFER_DESCRIPTIONS, start=1):
        figlio = QgsProcessingModelChildAlgorithm("native:buffer")
        figlio.setChildId("buffer_{}".format(indice))
        figlio.setDescription(descrizione)
        if indice == 1:
            figlio.addParameterSources(
                "INPUT",
                [QgsProcessingModelChildParameterSource.fromModelParameter(
                    chiave_di(SOURCE_NAMES[0]))],
            )
        model.addChildAlgorithm(figlio)

    ultimo = QgsProcessingModelChildAlgorithm("native:centroids")
    ultimo.setChildId("centroids_1")
    ultimo.setDescription("Centroidi")
    model.addChildAlgorithm(ultimo)

    alg = QgsApplication.processingRegistry().createAlgorithmById("native:centroids")
    return ModelerParametersDialog(alg, model, "centroids_1")
