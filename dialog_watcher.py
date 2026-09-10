# -*- coding: utf-8 -*-
"""Rilevamento dei dialog del modeler e scoperta dei combo da migliorare."""

from .plugin_support import SEARCH_MIN_ITEMS, is_alive

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
