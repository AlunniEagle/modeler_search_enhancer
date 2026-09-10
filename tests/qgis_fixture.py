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


def build_dialog():
    """Un ModelerParametersDialog reale con 6 input e 2 algoritmi figli."""
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
        key = name.replace(" ", "_").upper()
        model.addModelParameter(
            QgsProcessingParameterFeatureSource(key, name),
            QgsProcessingModelParameter(key),
        )

    primo = QgsProcessingModelChildAlgorithm("native:buffer")
    primo.setChildId("buffer_1")
    primo.setDescription("Buffer delle strade")
    primo.addParameterSources(
        "INPUT",
        [QgsProcessingModelChildParameterSource.fromModelParameter("STRADE_URBANE")],
    )
    model.addChildAlgorithm(primo)

    secondo = QgsProcessingModelChildAlgorithm("native:centroids")
    secondo.setChildId("centroids_1")
    secondo.setDescription("Centroidi")
    model.addChildAlgorithm(secondo)

    alg = QgsApplication.processingRegistry().createAlgorithmById("native:centroids")
    return ModelerParametersDialog(alg, model, "centroids_1")
