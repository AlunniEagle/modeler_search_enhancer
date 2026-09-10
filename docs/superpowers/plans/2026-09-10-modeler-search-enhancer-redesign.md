# Modeler Search Enhancer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sostituire il rilevamento a polling che fa crashare QGIS con un rilevamento event-driven, rendere il filtro dei combo corretto e indipendente per combo, e portare il plugin su una codebase unica compatibile Qt5 e Qt6.

**Architecture:** Un event filter installato sull'applicazione reagisce al solo `QEvent.Show` dei dialog con `objectName == "ModelerParametersDialog"` e rimanda l'aggancio con `QTimer.singleShot(0, ...)`. Dentro quel dialog, la scoperta è strutturale (`QgsProcessingModelerParameterWidget` → `QComboBox`), non basata su stringhe tradotte. Ogni combo riceve un `ComboSearchController` figlio Qt del combo stesso, che possiede tutto il proprio stato e non conserva alcuna cache delle voci.

**Tech Stack:** Python 3, PyQt tramite lo shim `qgis.PyQt` (PyQt5 5.15 e PyQt6 6.10), API QGIS 3.34+, test con `unittest` della standard library.

**Spec di riferimento:** `docs/superpowers/specs/2026-09-10-modeler-search-enhancer-redesign-design.md`

## Global Constraints

Ogni task deve rispettare questi vincoli. Sono stati tutti verificati eseguendo codice contro QGIS 3.34.15, 3.40.2 e 4.0.0.

- **Enum sempre in forma scoped.** `Qt.CaseSensitivity.CaseInsensitive`, `Qt.MatchFlag.MatchContains`, `QComboBox.InsertPolicy.NoInsert`, `QCompleter.CompletionMode.PopupCompletion`, `QEvent.Type.Show`, `QPalette.ColorRole.Highlight`, `Qgis.MessageLevel.Warning`. La forma non scoped solleva `AttributeError` su PyQt6.
- **`from qgis.PyQt import sip`.** `import sip` solleva `ModuleNotFoundError` su PyQt6.
- **Nessun `int()` su un enum.** Su PyQt6 gli enum sono `enum.Enum`, non `IntEnum`: serve `.value`.
- **Vietato `QgsApplication.allWidgets()`** e vietato qualunque `QTimer` ricorrente. Solo `QTimer.singleShot`, e `QTimer` single-shot come debounce per-combo.
- **Nessun `except Exception: pass` silenzioso.** Ogni eccezione inattesa va in `QgsMessageLog` tramite gli helper di `plugin_support`. Le sole eccezioni inghiottite senza log sono `RuntimeError`/`AttributeError` sul percorso caldo dell'event filter e i `disconnect()` in fase di teardown.
- **Nessuna stringa localizzata usata come logica.** Il rilevamento è strutturale. Le stringhe rivolte all'utente passano da `self.tr()`.
- **`qgisMinimumVersion` resta `3.34`.** Nessun branching per versione di Qt o di QGIS.
- **Codifica UTF-8** e commenti in italiano, come il resto del repository.
- **Non modificare `README.MD` né `help.html`** fino al Task 10: contengono tre differenze di whitespace non committate lasciate deliberatamente nel working tree.

**Comando di test canonico.** Da eseguire dalla directory *padre* del plugin, in Git Bash. Verificato funzionante su entrambe le versioni:

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Per la verifica su Qt6, la stessa riga con `"/c/Program Files/QGIS 4.0.0/bin/python-qgis.bat"`.

I comandi `git` vanno invece eseguiti dentro la directory del plugin:

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer"
```

## File Structure

| File | Responsabilità |
|---|---|
| `plugin_support.py` (nuovo) | Compatibilità Qt5/Qt6 (`sip`), helper di log, costanti. Nessuna dipendenza dagli altri moduli del plugin. |
| `combo_search.py` (nuovo) | `ComboSearchController`: tutto il comportamento di ricerca di un singolo combo. Dipende solo da `plugin_support`. |
| `dialog_watcher.py` (nuovo) | `ModelerDialogWatcher`, `should_enhance`, `find_source_combos`: rilevamento del dialog e scoperta dei combo. Dipende da `combo_search` e `plugin_support`. |
| `modeler_search_enhancer.py` (riscritto) | Il solo guscio del plugin: `initGui`, `unload`, azione di aiuto, installazione dell'event filter. È l'unico modulo che conosce `iface`. |
| `tests/__init__.py` (nuovo) | Rende `tests` un package per `unittest discover`. |
| `tests/qgis_fixture.py` (nuovo) | Avvio di QGIS headless e costruzione di un vero `ModelerParametersDialog`. Condiviso da tutti i test. |
| `tests/test_criterio.py` (nuovo) | Test del criterio di selezione dei combo. |
| `tests/test_scoperta.py` (nuovo) | Test della scoperta strutturale su un dialog reale. |
| `tests/test_watcher.py` (nuovo) | Test del rilevamento event-driven e dell'assenza di polling. |
| `tests/test_ricerca.py` (nuovo) | Test del filtro, dell'indipendenza fra combo, della risoluzione sul combo vivo e del ripristino. |
| `tests/test_guscio.py` (nuovo) | Test del fix del locale e dell'assenza di API vietate nel sorgente. |
| `metadata.txt` (modificato) | Versione e changelog. |

La separazione fra `dialog_watcher` e `combo_search` è deliberata: il primo sa *quando* e *dove* agganciare, il secondo sa *come* comportarsi. Nessuno dei due conosce `iface`, quindi entrambi sono testabili senza GUI QGIS.

---

### Task 1: Fondamenta — `plugin_support.py` e harness di test

Questo task non produce comportamento visibile, ma tutto il resto del piano ne dipende: senza harness non si può scrivere un test che falla.

**Files:**
- Create: `plugin_support.py`
- Create: `tests/__init__.py`
- Create: `tests/qgis_fixture.py`
- Test: `tests/test_fondamenta.py`

**Interfaces:**
- Consumes: niente.
- Produces:
  - `PLUGIN_TAG: str`
  - `SEARCH_MIN_ITEMS: int` (valore 5)
  - `FILTER_DEBOUNCE_MS: int` (valore 300)
  - `log_warning(message: str) -> None`
  - `log_error(message: str) -> None`
  - `is_alive(obj) -> bool`
  - `tests.qgis_fixture.start_qgis() -> QgsApplication`
  - `tests.qgis_fixture.build_dialog() -> QDialog` — un vero `ModelerParametersDialog` con 6 input di modello e 2 algoritmi figli
  - `tests.qgis_fixture.SOURCE_NAMES: list[str]` — i nomi dei 6 input, per gli assert sul filtro

- [ ] **Step 1: Scrivere il test che falla**

Crea `tests/__init__.py` vuoto, poi `tests/test_fondamenta.py`:

```python
# -*- coding: utf-8 -*-
"""Test delle utilità condivise e dell'harness."""

import unittest

from modeler_search_enhancer.plugin_support import (
    FILTER_DEBOUNCE_MS,
    PLUGIN_TAG,
    SEARCH_MIN_ITEMS,
    is_alive,
)
from modeler_search_enhancer.tests.qgis_fixture import SOURCE_NAMES, start_qgis


class TestCostanti(unittest.TestCase):
    def test_soglia_minima_e_cinque(self):
        self.assertEqual(SEARCH_MIN_ITEMS, 5)

    def test_debounce_e_trecento_ms(self):
        self.assertEqual(FILTER_DEBOUNCE_MS, 300)

    def test_tag_non_vuoto(self):
        self.assertTrue(PLUGIN_TAG)


class TestIsAlive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_none_non_e_vivo(self):
        self.assertFalse(is_alive(None))

    def test_oggetto_normale_e_vivo(self):
        from qgis.PyQt.QtWidgets import QWidget
        widget = QWidget()
        self.assertTrue(is_alive(widget))

    def test_oggetto_distrutto_non_e_vivo(self):
        from qgis.PyQt import sip
        from qgis.PyQt.QtWidgets import QWidget
        widget = QWidget()
        sip.delete(widget)
        self.assertFalse(is_alive(widget))


class TestHarness(unittest.TestCase):
    def test_ci_sono_almeno_cinque_sorgenti(self):
        # Il criterio di selezione richiede count() >= 5: la fixture deve
        # produrre abbastanza input perché i combo lo superino.
        self.assertGreaterEqual(len(SOURCE_NAMES), 5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Eseguire il test per verificare che falli**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `ModuleNotFoundError: No module named 'modeler_search_enhancer.plugin_support'`.

- [ ] **Step 3: Scrivere `plugin_support.py`**

```python
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
```

- [ ] **Step 4: Scrivere `tests/qgis_fixture.py`**

```python
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
```

- [ ] **Step 5: Eseguire i test per verificare che passino**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `Ran 7 tests`, `OK`.

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer"
git add plugin_support.py tests/__init__.py tests/qgis_fixture.py tests/test_fondamenta.py
git commit -m "test: harness headless e utilità condivise Qt5/Qt6"
```

---

### Task 2: Criterio di selezione dei combo

**Files:**
- Create: `dialog_watcher.py`
- Test: `tests/test_criterio.py`

**Interfaces:**
- Consumes: `plugin_support.SEARCH_MIN_ITEMS`, `plugin_support.is_alive`
- Produces: `dialog_watcher.should_enhance(combo: QComboBox) -> bool`

- [ ] **Step 1: Scrivere il test che falla**

Crea `tests/test_criterio.py`:

```python
# -*- coding: utf-8 -*-
"""Test del criterio che decide quali combo migliorare."""

import unittest

from qgis.PyQt.QtWidgets import QComboBox

from modeler_search_enhancer.dialog_watcher import should_enhance
from modeler_search_enhancer.tests.qgis_fixture import start_qgis


def combo_con(items_e_dati):
    """Un QComboBox popolato con coppie (testo, itemData)."""
    combo = QComboBox()
    for testo, dato in items_e_dati:
        combo.addItem(testo, dato)
    return combo


class TestShouldEnhance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_combo_di_input_del_modello_va_migliorato(self):
        # itemData str = riferimento a un input del modello.
        combo = combo_con([("Layer %d" % i, "KEY_%d" % i) for i in range(6)])
        self.assertTrue(should_enhance(combo))

    def test_combo_di_output_di_algoritmo_va_migliorato(self):
        # itemData list = [childId, nomeOutput].
        combo = combo_con(
            [("Output %d" % i, ["child_%d" % i, "OUTPUT"]) for i in range(6)]
        )
        self.assertTrue(should_enhance(combo))

    def test_combo_booleano_non_va_migliorato(self):
        # Anche con abbastanza voci, un booleano non si cerca.
        combo = combo_con([("Sì", True), ("No", False)] * 3)
        self.assertFalse(should_enhance(combo))

    def test_combo_di_enumerato_non_va_migliorato(self):
        # itemData int = indice dell'opzione di un QgsProcessingParameterEnum.
        combo = combo_con([("Opzione %d" % i, i) for i in range(6)])
        self.assertFalse(should_enhance(combo))

    def test_combo_senza_itemData_non_va_migliorato(self):
        combo = QComboBox()
        combo.addItems(["a", "b", "c", "d", "e", "f"])
        self.assertFalse(should_enhance(combo))

    def test_combo_troppo_corto_non_va_migliorato(self):
        combo = combo_con([("Layer %d" % i, "KEY_%d" % i) for i in range(4)])
        self.assertFalse(should_enhance(combo))

    def test_combo_al_limite_va_migliorato(self):
        combo = combo_con([("Layer %d" % i, "KEY_%d" % i) for i in range(5)])
        self.assertTrue(should_enhance(combo))

    def test_combo_vuoto_non_va_migliorato(self):
        self.assertFalse(should_enhance(QComboBox()))

    def test_none_non_va_migliorato(self):
        self.assertFalse(should_enhance(None))

    def test_combo_distrutto_non_va_migliorato(self):
        from qgis.PyQt import sip
        combo = combo_con([("Layer %d" % i, "KEY_%d" % i) for i in range(6)])
        sip.delete(combo)
        self.assertFalse(should_enhance(combo))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Eseguire il test per verificare che falli**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `ModuleNotFoundError: No module named 'modeler_search_enhancer.dialog_watcher'`.

- [ ] **Step 3: Scrivere `dialog_watcher.py` con il solo criterio**

```python
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
```

- [ ] **Step 4: Eseguire i test per verificare che passino**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `Ran 17 tests`, `OK`.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer"
git add dialog_watcher.py tests/test_criterio.py
git commit -m "feat: criterio strutturale di selezione dei combo, indipendente dalla lingua"
```

---

### Task 3: Scoperta strutturale dei combo in un dialog

**Files:**
- Modify: `dialog_watcher.py` (aggiunge `find_source_combos`)
- Test: `tests/test_scoperta.py`

**Interfaces:**
- Consumes: `dialog_watcher.should_enhance`, `plugin_support.is_alive`
- Produces: `dialog_watcher.find_source_combos(dialog) -> list[QComboBox]`

- [ ] **Step 1: Scrivere il test che falla**

Crea `tests/test_scoperta.py`:

```python
# -*- coding: utf-8 -*-
"""Test della scoperta dei combo su un dialog reale del modeler."""

import unittest

from qgis.PyQt.QtWidgets import QComboBox, QDialog
from qgis.gui import QgsProcessingModelerParameterWidget

from modeler_search_enhancer.dialog_watcher import find_source_combos
from modeler_search_enhancer.tests.qgis_fixture import build_dialog, start_qgis


class TestFindSourceCombos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()
        cls.dialog = build_dialog()

    def test_trova_almeno_un_combo(self):
        self.assertTrue(find_source_combos(self.dialog))

    def test_i_combo_trovati_stanno_sotto_un_parameter_widget(self):
        # L'aggancio strutturale: nessun combo fuori da un
        # QgsProcessingModelerParameterWidget deve essere restituito.
        widgets = self.dialog.findChildren(QgsProcessingModelerParameterWidget)
        ammessi = set()
        for widget in widgets:
            for combo in widget.findChildren(QComboBox):
                ammessi.add(id(combo))
        for combo in find_source_combos(self.dialog):
            self.assertIn(id(combo), ammessi)

    def test_i_combo_trovati_hanno_itemdata_di_sorgente(self):
        for combo in find_source_combos(self.dialog):
            self.assertIsInstance(combo.itemData(0), (str, list))
            self.assertNotIsInstance(combo.itemData(0), bool)

    def test_esclude_i_combo_booleani(self):
        for combo in find_source_combos(self.dialog):
            testi = [combo.itemText(i) for i in range(combo.count())]
            self.assertNotEqual(sorted(testi), ["No", "Yes"])

    def test_le_virgolette_tipografiche_non_ostacolano_il_rilevamento(self):
        # Le etichette degli output di algoritmo usano U+201C/U+201D, non
        # il doppio apice ASCII. Il gate primario della versione precedente
        # cercava `"` e quindi non corrispondeva mai.
        from modeler_search_enhancer.dialog_watcher import should_enhance

        combo = QComboBox()
        for i in range(6):
            etichetta = u"“Output %d” from algorithm “Passo %d”" % (i, i)
            combo.addItem(etichetta, ["child_%d" % i, "OUTPUT"])
        self.assertNotIn('"', combo.itemText(0))
        self.assertIn(u"“", combo.itemText(0))
        self.assertTrue(should_enhance(combo))

    def test_dialog_senza_parameter_widget_non_da_nulla(self):
        vuoto = QDialog()
        combo = QComboBox(vuoto)
        combo.addItems(["a", "b", "c", "d", "e", "f"])
        self.assertEqual(find_source_combos(vuoto), [])

    def test_none_non_solleva(self):
        self.assertEqual(find_source_combos(None), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Eseguire il test per verificare che falli**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `ImportError: cannot import name 'find_source_combos'`.

- [ ] **Step 3: Aggiungere `find_source_combos` a `dialog_watcher.py`**

Aggiungi questi import in testa al file, sotto quelli esistenti:

```python
from qgis.PyQt.QtWidgets import QComboBox
from qgis.gui import QgsProcessingModelerParameterWidget
```

e questa funzione dopo `should_enhance`:

```python
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
```

- [ ] **Step 4: Eseguire i test per verificare che passino**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `Ran 24 tests`, `OK`.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer"
git add dialog_watcher.py tests/test_scoperta.py
git commit -m "feat: scoperta strutturale dei combo limitata al singolo dialog"
```

---

### Task 4: Controller — stato per combo e filtro

Chiude **CR-2**. Il controller viene costruito prima del watcher perché il watcher lo istanzia.

**Files:**
- Create: `combo_search.py`
- Test: `tests/test_ricerca.py`

**Interfaces:**
- Consumes: `plugin_support.FILTER_DEBOUNCE_MS`, `plugin_support.is_alive`
- Produces:
  - `ComboSearchController(combo: QComboBox)` — QObject figlio di `combo`
  - `.attach() -> None`
  - `.refresh_filter() -> None` — rifiltra subito, senza attendere il debounce
  - `.current_candidates() -> list[str]` — le voci attualmente offerte dal completer

`refresh_filter()` e `current_candidates()` sono pubblici proprio per rendere i test deterministici senza dover attendere il timer né aprire popup.

- [ ] **Step 1: Scrivere il test che falla**

Crea `tests/test_ricerca.py`:

```python
# -*- coding: utf-8 -*-
"""Test del filtro di ricerca su un combo."""

import unittest

from qgis.PyQt.QtWidgets import QComboBox

from modeler_search_enhancer.combo_search import ComboSearchController
from modeler_search_enhancer.tests.qgis_fixture import SOURCE_NAMES, start_qgis


def combo_sorgenti():
    """Un combo popolato come quelli del modeler: testo + chiave in itemData."""
    combo = QComboBox()
    for nome in SOURCE_NAMES:
        combo.addItem(nome, nome.replace(" ", "_").upper())
    return combo


def digita(controller, combo, testo):
    """Simula la digitazione e forza il filtro senza attendere il debounce."""
    combo.lineEdit().setText(testo)
    controller.refresh_filter()


class TestFiltro(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_query_vuota_offre_tutte_le_voci(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        digita(controller, combo, "")
        self.assertEqual(controller.current_candidates(), SOURCE_NAMES)

    def test_filtro_e_case_insensitive(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        digita(controller, combo, "STRADE")
        self.assertEqual(
            controller.current_candidates(), ["Strade urbane", "Strade rurali"]
        )

    def test_filtro_su_sottostringa_interna(self):
        # MatchContains: "urban" non è un prefisso di "Strade urbane".
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        digita(controller, combo, "urban")
        self.assertEqual(controller.current_candidates(), ["Strade urbane"])

    def test_filtro_multi_termine_in_and(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        digita(controller, combo, "edifici nuovi")
        self.assertEqual(controller.current_candidates(), ["Edifici nuovi"])

    def test_termini_in_ordine_qualsiasi(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        digita(controller, combo, "nuovi edifici")
        self.assertEqual(controller.current_candidates(), ["Edifici nuovi"])

    def test_query_senza_risultati_da_lista_vuota(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        digita(controller, combo, "zzzz")
        self.assertEqual(controller.current_candidates(), [])


class TestIndipendenzaFraCombo(unittest.TestCase):
    """Regressione di CR-2: lo stato era condiviso sul singleton del plugin."""

    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_due_combo_filtrano_entrambi(self):
        primo, secondo = combo_sorgenti(), combo_sorgenti()
        c1, c2 = ComboSearchController(primo), ComboSearchController(secondo)
        c1.attach()
        c2.attach()

        digita(c1, primo, "strade")
        digita(c2, secondo, "edifici")

        self.assertEqual(
            c1.current_candidates(), ["Strade urbane", "Strade rurali"]
        )
        self.assertEqual(
            c2.current_candidates(), ["Edifici storici", "Edifici nuovi"]
        )

    def test_la_stessa_query_nel_secondo_combo_filtra_comunque(self):
        # Con _last_search_text condiviso questo era il caso che non
        # filtrava affatto: la guardia usciva subito.
        primo, secondo = combo_sorgenti(), combo_sorgenti()
        c1, c2 = ComboSearchController(primo), ComboSearchController(secondo)
        c1.attach()
        c2.attach()

        digita(c1, primo, "strade")
        digita(c2, secondo, "strade")

        self.assertEqual(
            c2.current_candidates(), ["Strade urbane", "Strade rurali"]
        )

    def test_ogni_controller_ha_il_proprio_timer(self):
        primo, secondo = combo_sorgenti(), combo_sorgenti()
        c1, c2 = ComboSearchController(primo), ComboSearchController(secondo)
        c1.attach()
        c2.attach()
        self.assertIsNot(c1._timer, c2._timer)

    def test_il_controller_e_figlio_qt_del_combo(self):
        # Garantisce che Qt lo distrugga insieme al combo: è ciò che
        # sostituisce il bookkeeping manuale che accumulava riferimenti.
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        self.assertIs(controller.parent(), combo)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Eseguire il test per verificare che falli**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `ModuleNotFoundError: No module named 'modeler_search_enhancer.combo_search'`.

- [ ] **Step 3: Scrivere `combo_search.py`**

```python
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
        self._updating = False
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
        """Le voci attualmente offerte dal completer."""
        return list(self._model.stringList())

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

    # --- presentazione ---------------------------------------------------

    def _apply_search_style(self):
        """Bordo derivato dalla palette, così resta leggibile su tema scuro."""
        combo = self._combo
        colore = combo.palette().color(QPalette.ColorRole.Highlight).name()
        combo.lineEdit().setStyleSheet(
            "QLineEdit { border: 1px solid %s; border-radius: 3px;"
            " padding: 1px 4px; }" % colore
        )
```

- [ ] **Step 4: Eseguire i test per verificare che passino**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `Ran 34 tests`, `OK`.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer"
git add combo_search.py tests/test_ricerca.py
git commit -m "fix: stato di ricerca per combo invece che condiviso sul plugin"
```

---

### Task 5: Controller — risoluzione della selezione sul combo vivo

Chiude **CR-3**, il difetto più grave: collegava la sorgente sbagliata nel modello.

**Files:**
- Modify: `combo_search.py`
- Modify: `tests/test_ricerca.py` (aggiunge una classe di test)

**Interfaces:**
- Consumes: quanto prodotto dal Task 4
- Produces: `ComboSearchController.select_text(text: str) -> bool` — risolve `text` sul combo vivo, imposta la selezione e restituisce `True` se la voce esisteva

- [ ] **Step 1: Scrivere il test che falla**

Aggiungi in fondo a `tests/test_ricerca.py`, prima del blocco `if __name__`:

```python
class TestRisoluzioneSulComboVivo(unittest.TestCase):
    """Regressione di CR-3: la selezione usava un indice su uno snapshot."""

    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_selezione_imposta_il_currentdata_giusto(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()

        self.assertTrue(controller.select_text("Edifici nuovi"))
        self.assertEqual(combo.currentData(), "EDIFICI_NUOVI")
        self.assertEqual(combo.currentText(), "Edifici nuovi")

    def test_selezione_dopo_ripopolamento_resta_corretta(self):
        # Il modeler ripopola i combo quando cambiano gli algoritmi a monte.
        # Con lo snapshot, l'indice puntava alla voce sbagliata.
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()

        combo.clear()
        for nome in ["Reticolo idrico", "Edifici nuovi", "Aree verdi"]:
            combo.addItem(nome, nome.replace(" ", "_").upper())

        self.assertTrue(controller.select_text("Edifici nuovi"))
        self.assertEqual(combo.currentData(), "EDIFICI_NUOVI")

    def test_il_filtro_dopo_ripopolamento_usa_le_voci_nuove(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()

        combo.clear()
        for nome in ["Reticolo idrico", "Aree verdi"]:
            combo.addItem(nome, nome.replace(" ", "_").upper())

        digita(controller, combo, "")
        self.assertEqual(
            controller.current_candidates(), ["Reticolo idrico", "Aree verdi"]
        )

    def test_testo_inesistente_non_cambia_la_selezione(self):
        combo = combo_sorgenti()
        combo.setCurrentIndex(2)
        controller = ComboSearchController(combo)
        controller.attach()

        self.assertFalse(controller.select_text("non esiste"))
        self.assertEqual(combo.currentData(), "EDIFICI_STORICI")

    def test_selezione_su_combo_distrutto_non_solleva(self):
        from qgis.PyQt import sip
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        sip.delete(combo)
        self.assertFalse(controller.select_text("Edifici nuovi"))
```

- [ ] **Step 2: Eseguire il test per verificare che falli**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `AttributeError: 'ComboSearchController' object has no attribute 'select_text'`.

- [ ] **Step 3: Aggiungere `select_text` e collegare il completer**

Aggiungi questo metodo a `ComboSearchController`, dopo `refresh_filter`:

```python
    # --- selezione -------------------------------------------------------

    def select_text(self, text):
        """Risolve `text` sul combo vivo e lo seleziona.

        La risoluzione avviene con `findText` sul combo così com'è adesso,
        non con l'indice di una lista memorizzata: è questo che impedisce di
        collegare la sorgente sbagliata quando il modeler ha ripopolato il
        combo dopo l'aggancio.

        Restituisce True se la voce esisteva.
        """
        combo = self._combo
        if not is_alive(combo):
            return False
        index = combo.findText(text)
        if index < 0:
            return False
        self._updating = True
        try:
            combo.setCurrentIndex(index)
            line_edit = combo.lineEdit()
            if line_edit is not None:
                line_edit.setText(combo.itemText(index))
        finally:
            self._updating = False
        return True
```

Poi, in `attach()`, collega il completer subito dopo averlo creato — inserisci questa riga immediatamente prima di `self._model.setStringList(self._live_items())`:

```python
        self._completer.activated.connect(self.select_text)
```

- [ ] **Step 4: Eseguire i test per verificare che passino**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `Ran 39 tests`, `OK`.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer"
git add combo_search.py tests/test_ricerca.py
git commit -m "fix: risolvi la selezione sul combo vivo, non su uno snapshot obsoleto"
```

---

### Task 6: Controller — riconciliazione del testo e ripristino

**Files:**
- Modify: `combo_search.py`
- Modify: `tests/test_ricerca.py`

**Interfaces:**
- Consumes: quanto prodotto dai Task 4 e 5
- Produces:
  - `ComboSearchController.reconcile_text() -> None`
  - `ComboSearchController.detach() -> None`

- [ ] **Step 1: Scrivere il test che falla**

Aggiungi in fondo a `tests/test_ricerca.py`, prima del blocco `if __name__`:

```python
class TestRiconciliazioneDelTesto(unittest.TestCase):
    """Il widget non deve mostrare un testo diverso dal valore reale."""

    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_testo_libero_viene_ripristinato(self):
        combo = combo_sorgenti()
        combo.setCurrentIndex(1)
        controller = ComboSearchController(combo)
        controller.attach()

        combo.lineEdit().setText("qualcosa che non esiste")
        controller.reconcile_text()

        self.assertEqual(combo.lineEdit().text(), "Strade rurali")
        self.assertEqual(combo.currentData(), "STRADE_RURALI")

    def test_testo_valido_non_viene_toccato(self):
        # Un testo che corrisponde a una voce reale deve restare com'è.
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        combo.lineEdit().setText("Edifici nuovi")
        controller.reconcile_text()
        self.assertEqual(combo.lineEdit().text(), "Edifici nuovi")

    def test_riconciliazione_su_combo_distrutto_non_solleva(self):
        from qgis.PyQt import sip
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        sip.delete(combo)
        controller.reconcile_text()  # non deve sollevare


class TestDetach(unittest.TestCase):
    """unload() deve restituire i combo come li ha trovati."""

    @classmethod
    def setUpClass(cls):
        cls.app = start_qgis()

    def test_detach_ripristina_non_editabile(self):
        combo = combo_sorgenti()
        self.assertFalse(combo.isEditable())
        controller = ComboSearchController(combo)
        controller.attach()
        self.assertTrue(combo.isEditable())

        controller.detach()
        self.assertFalse(combo.isEditable())

    def test_detach_ripristina_il_testo_corretto(self):
        combo = combo_sorgenti()
        combo.setCurrentIndex(3)
        controller = ComboSearchController(combo)
        controller.attach()
        combo.lineEdit().setText("spazzatura")

        controller.detach()
        self.assertEqual(combo.currentText(), "Edifici nuovi")
        self.assertEqual(combo.currentData(), "EDIFICI_NUOVI")

    def test_detach_ripristina_la_insert_policy(self):
        combo = combo_sorgenti()
        originale = combo.insertPolicy()
        controller = ComboSearchController(combo)
        controller.attach()
        controller.detach()
        self.assertEqual(combo.insertPolicy(), originale)

    def test_detach_e_idempotente(self):
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        controller.detach()
        controller.detach()  # non deve sollevare
        self.assertFalse(combo.isEditable())

    def test_detach_su_combo_distrutto_non_solleva(self):
        from qgis.PyQt import sip
        combo = combo_sorgenti()
        controller = ComboSearchController(combo)
        controller.attach()
        sip.delete(combo)
        controller.detach()  # non deve sollevare
```

- [ ] **Step 2: Eseguire il test per verificare che falli**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `AttributeError: 'ComboSearchController' object has no attribute 'reconcile_text'`.

- [ ] **Step 3: Aggiungere `reconcile_text` e `detach`**

Aggiungi questi due metodi a `ComboSearchController`, dopo `select_text`:

```python
    def reconcile_text(self):
        """Riporta il line edit al valore reale se il testo non è una voce.

        Con `NoInsert`, `currentData()` conserva il valore valido anche
        mentre il line edit mostra testo libero. Senza questo ripristino il
        widget mostrerebbe all'utente una stringa diversa da quella che il
        modello userà davvero.
        """
        combo = self._combo
        if self._updating or not is_alive(combo):
            return
        line_edit = combo.lineEdit()
        if line_edit is None:
            return
        if combo.findText(line_edit.text()) >= 0:
            return
        self._updating = True
        try:
            line_edit.setText(combo.itemText(combo.currentIndex()))
        finally:
            self._updating = False

    def detach(self):
        """Riporta il combo allo stato in cui era prima di `attach`."""
        combo = self._combo
        self._timer.stop()
        if not is_alive(combo):
            self._completer = None
            return

        line_edit = combo.lineEdit()
        if line_edit is not None:
            # In teardown un disconnect può fallire perché già disconnesso:
            # è l'unico caso in cui inghiottire l'eccezione è corretto.
            try:
                line_edit.textEdited.disconnect(self._on_text_edited)
            except (TypeError, RuntimeError):
                pass
            try:
                line_edit.editingFinished.disconnect(self.reconcile_text)
            except (TypeError, RuntimeError):
                pass
            line_edit.setCompleter(None)
            line_edit.setStyleSheet("")

        # setEditable(False) ripristina da sé il testo della voce corrente.
        combo.setEditable(self._was_editable)
        combo.setInsertPolicy(self._original_insert_policy)
        self._completer = None
```

Poi collega `reconcile_text` in `attach()`: aggiungi questa riga subito dopo `line_edit.textEdited.connect(self._on_text_edited)`:

```python
        line_edit.editingFinished.connect(self.reconcile_text)
```

- [ ] **Step 4: Eseguire i test per verificare che passino**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `Ran 47 tests`, `OK`.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer"
git add combo_search.py tests/test_ricerca.py
git commit -m "feat: riconciliazione del testo digitato e ripristino completo del combo"
```

---

### Task 7: Watcher event-driven

Chiude **CR-1**, il crash.

**Files:**
- Modify: `dialog_watcher.py`
- Test: `tests/test_watcher.py`

**Interfaces:**
- Consumes: `dialog_watcher.find_source_combos`, `combo_search.ComboSearchController`, `plugin_support.is_alive`, `plugin_support.log_error`
- Produces:
  - `ModelerDialogWatcher(parent=None)` — QObject da installare come event filter
  - `.eventFilter(obj, event) -> bool` — restituisce sempre `False`
  - `.enhance_dialog(dialog) -> int` — aggancia i combo, restituisce quanti
  - `.detach_all() -> None`
  - `.active_controller_count() -> int`

- [ ] **Step 1: Scrivere il test che falla**

Crea `tests/test_watcher.py`:

```python
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
```

- [ ] **Step 2: Eseguire il test per verificare che falli**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `ImportError: cannot import name 'ModelerDialogWatcher'`.

- [ ] **Step 3: Aggiungere `ModelerDialogWatcher` a `dialog_watcher.py`**

Aggiungi questi import in testa al file:

```python
from qgis.PyQt.QtCore import QEvent, QObject, QTimer

from .combo_search import ComboSearchController
from .plugin_support import log_error
```

e questa classe in fondo al file:

```python
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
```

- [ ] **Step 4: Eseguire i test per verificare che passino**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `Ran 54 tests`, `OK`.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer"
git add dialog_watcher.py tests/test_watcher.py
git commit -m "fix: rilevamento event-driven al posto del polling di allWidgets che causava i crash"
```

---

### Task 8: Riscrittura del guscio del plugin

Chiude **CR-5**, **CR-6** e i residui di **CR-7**.

**Files:**
- Modify: `modeler_search_enhancer.py` (riscrittura completa)
- Test: `tests/test_guscio.py`

**Interfaces:**
- Consumes: `dialog_watcher.ModelerDialogWatcher`
- Produces: `ModelerSearchEnhancer(iface)` con `initGui()`, `unload()`, `tr(message)`, `showHelp()` — la firma che `__init__.py` si aspetta, invariata

- [ ] **Step 1: Scrivere il test che falla**

Crea `tests/test_guscio.py`:

```python
# -*- coding: utf-8 -*-
"""Test del guscio del plugin e delle API vietate."""

import io
import os
import unittest

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULI = (
    "modeler_search_enhancer.py",
    "dialog_watcher.py",
    "combo_search.py",
    "plugin_support.py",
)


def sorgente(nome):
    with io.open(os.path.join(PLUGIN_DIR, nome), encoding="utf-8") as handle:
        return handle.read()


class TestApiVietate(unittest.TestCase):
    """Regressione di CR-1 e CR-5 a livello di sorgente."""

    def test_nessun_uso_di_allwidgets(self):
        for nome in MODULI:
            self.assertNotIn("allWidgets", sorgente(nome), nome)

    def test_il_watcher_non_ha_timer_propri(self):
        # Il polling viveva in un QTimer ricorrente del watcher. Ora il
        # watcher pianifica solo con QTimer.singleShot, che non si ripete.
        testo = sorgente("dialog_watcher.py")
        self.assertIn("QTimer.singleShot", testo)
        self.assertNotIn(".start(", testo)

    def test_il_debounce_e_single_shot(self):
        # L'unico timer del plugin è il debounce per combo, e deve essere
        # single-shot: uno ricorrente ci riporterebbe al polling.
        testo = sorgente("combo_search.py")
        self.assertIn("setSingleShot(True)", testo)
        self.assertEqual(testo.count(".start("), 1)

    def test_nessun_enum_non_scoped(self):
        vietati = (
            "Qt.CaseInsensitive",
            "Qt.MatchContains",
            "QComboBox.NoInsert",
            "QCompleter.PopupCompletion",
            "QCompleter.UnfilteredPopupCompletion",
            "QEvent.Show",
        )
        for nome in MODULI:
            testo = sorgente(nome)
            for simbolo in vietati:
                self.assertNotIn(simbolo, testo, "{} in {}".format(simbolo, nome))

    def test_nessun_import_sip_diretto(self):
        for nome in MODULI:
            testo = sorgente(nome)
            for riga in testo.splitlines():
                self.assertNotEqual(riga.strip(), "import sip", nome)

    def test_nessun_except_silenzioso_generico(self):
        # `except Exception` seguito dal solo `pass` è ciò che ha nascosto
        # la rottura su Qt6: le eccezioni inattese devono essere loggate.
        # Il confronto è su espressione regolare e non su una stringa
        # letterale, per non dipendere dall'indentazione.
        import re

        schema = re.compile(r"except\s+Exception[^\n]*:\s*\n\s*pass\b")
        for nome in MODULI:
            self.assertIsNone(schema.search(sorgente(nome)), nome)

    def test_la_classe_morta_e_stata_rimossa(self):
        self.assertNotIn(
            "class SearchableComboBox", sorgente("modeler_search_enhancer.py")
        )

    def test_il_criterio_non_guarda_il_testo_delle_voci(self):
        # Il rilevamento deve dipendere solo da count() e itemData(). Se
        # tornasse a leggere itemText() sarebbe di nuovo legato alla lingua
        # dell'interfaccia, che è la radice di CR-4.
        import inspect

        from modeler_search_enhancer.dialog_watcher import should_enhance

        self.assertNotIn("itemText", inspect.getsource(should_enhance))

    def test_nessuna_stringa_localizzata_nella_logica_di_rilevamento(self):
        # Regressione di CR-4: il rilevamento si appoggiava a parole chiave
        # italiane e inglesi, quindi non funzionava nelle altre lingue.
        vietate = (
            "from algorithm",
            "dall'algoritmo",
            "utilizzo del risultato",
            "layer in ingresso",
            "input layer",
            "dipendenze",
            "dependencies",
            "tabella",
            "selezione",
        )
        testo = sorgente("dialog_watcher.py").lower()
        for frase in vietate:
            self.assertNotIn(frase, testo, frase)


class TestLocale(unittest.TestCase):
    """Regressione di CR-6: TypeError su profilo senza la chiave del locale."""

    def test_locale_assente_non_solleva(self):
        from modeler_search_enhancer.modeler_search_enhancer import (
            leggi_locale_utente,
        )
        from qgis.PyQt.QtCore import QSettings

        vuoto = QSettings("ClaudeTest_NoSuchOrg", "ClaudeTest_NoSuchApp")
        vuoto.remove("locale/userLocale")
        self.assertEqual(leggi_locale_utente(vuoto), "")

    def test_locale_presente_viene_troncato_a_due_lettere(self):
        from modeler_search_enhancer.modeler_search_enhancer import (
            leggi_locale_utente,
        )
        from qgis.PyQt.QtCore import QSettings

        settings = QSettings("ClaudeTest_Org", "ClaudeTest_App")
        settings.setValue("locale/userLocale", "it_IT")
        self.assertEqual(leggi_locale_utente(settings), "it")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Eseguire il test per verificare che falli**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: fallimenti su `allWidgets`, sugli enum non scoped, su `class SearchableComboBox`, e `ImportError` su `leggi_locale_utente`.

- [ ] **Step 3: Riscrivere `modeler_search_enhancer.py`**

Sostituisci l'intero contenuto del file con:

```python
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
        help_action.setStatusTip(self.tr(u'Mostra la documentazione del plugin'))
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
            self.tr(u'File di aiuto non trovato'),
            self.tr(u'Documentazione non trovata in:\n{}').format(help_file))

    def unload(self):
        """Ripristina i combo, rimuove il watcher e svuota il menu."""
        if self.watcher is not None:
            QApplication.instance().removeEventFilter(self.watcher)
            self.watcher.detach_all()
            self.watcher = None

        for action in self.actions:
            self.iface.removePluginMenu(self.tr(MENU_LABEL), action)
        self.actions = []
```

- [ ] **Step 4: Eseguire i test per verificare che passino**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `Ran 65 tests`, `OK`.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer"
git add modeler_search_enhancer.py tests/test_guscio.py
git commit -m "refactor: guscio del plugin snello, fix del locale, rimozione del codice morto"
```

---

### Task 9: Verifica su Qt6 e aggiornamento di `metadata.txt`

**Files:**
- Modify: `metadata.txt`

**Interfaces:**
- Consumes: tutto quanto prodotto dai Task 1–8
- Produces: nessuna nuova interfaccia

- [ ] **Step 1: Eseguire la suite completa su QGIS 3.40.2 (Qt5)**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `Ran 65 tests`, `OK`.

- [ ] **Step 2: Eseguire la suite completa su QGIS 4.0.0 (Qt6)**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 4.0.0/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `Ran 65 tests`, `OK`. Se compare un `AttributeError` su un enum, è un enum non scoped sfuggito: correggilo e ripeti entrambe le esecuzioni.

- [ ] **Step 3: Eseguire la suite su QGIS 3.34.15, la versione minima dichiarata**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.34.15/bin/python-qgis-ltr.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `Ran 65 tests`, `OK`. Questo verifica che `qgisMinimumVersion=3.34` sia una promessa mantenuta.

- [ ] **Step 4: Aggiornare `metadata.txt`**

Porta `version=1.2` a `version=2.0` e sostituisci il blocco `changelog=` mettendo la nuova voce in testa, prima di `1.2`:

```
changelog=2.0
        - Risolto il crash di QGIS causato dal rilevamento a polling delle finestre
        - Rilevamento ora event-driven e limitato alla singola finestra del modeler
        - Corretto il filtro che si applicava a un solo campo per volta
        - Corretta la selezione che poteva collegare la sorgente sbagliata nel modello
        - Rilevamento indipendente dalla lingua dell'interfaccia
        - Piena compatibilita' con Qt6 e QGIS 4.0
        - Stile del campo di ricerca leggibile anche con tema scuro
        - Aggiunta una suite di test automatici
        1.2
```

Lascia invariate le righe successive del changelog.

- [ ] **Step 5: Verificare che i metadati siano coerenti**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer" && grep -E "^(version|qgisMinimumVersion)=" metadata.txt
```

Atteso:

```
qgisMinimumVersion=3.34
version=2.0
```

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer"
git add metadata.txt
git commit -m "chore: versione 2.0 e changelog"
```

---

### Task 10: Documentazione

**ATTENZIONE — vincolo sul working tree.** `README.MD` e `help.html` contengono differenze di whitespace non committate, lasciate deliberatamente. Modifica solo il contenuto testuale che serve, non normalizzare le fini di riga, e verifica il diff prima di committare: devono comparire solo le modifiche intenzionali di questo task, più le tre righe di whitespace già presenti. Se il diff mostra centinaia di righe cambiate, il tuo editor ha riscritto le fini di riga: annulla e riprova.

**Files:**
- Modify: `help.html`
- Modify: `README.MD`

**Interfaces:** nessuna.

- [ ] **Step 1: Ispezionare lo stato di partenza del diff**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer" && git diff --numstat README.MD help.html
```

Atteso: una riga aggiunta e una rimossa per ciascun file. Annota questi numeri: dopo le modifiche il conteggio deve essere cresciuto solo di quanto hai scritto tu.

- [ ] **Step 2: Aggiornare `help.html`**

I documenti sono in inglese: le sostituzioni vanno scritte in inglese. Ogni riga sotto è da sostituire esattamente, mantenendo l'indentazione esistente.

I numeri di riga servono solo a orientarsi e si riferiscono al file **prima** di qualunque modifica: applica le sostituzioni cercando il testo, non andando alla riga, perché ogni modifica sposta quelle successive.

Riga 147 — il polling non esiste più:

```html
            <li><strong>Monitors</strong> - Continuously monitors for open Modeler windows</li>
```

diventa

```html
            <li><strong>Detects</strong> - Activates as soon as an algorithm configuration window opens in the Modeler</li>
```

Riga 155 — la nota descrive la vecchia euristica testuale:

```html
            <strong>⚠️ Note:</strong> The plugin only enhances ComboBoxes that contain algorithm outputs (like "Result from buffer operation"). It intelligently ignores configuration ComboBoxes such as "Dependencies", parameter dropdowns, and other non-algorithm-output fields.
```

diventa

```html
            <strong>⚠️ Note:</strong> The plugin only enhances fields that list model inputs and algorithm outputs, and only when they hold at least five entries. Boolean and enumerated parameter dropdowns are left untouched. Detection is structural, so it works the same in every interface language.
```

Riga 160 — il bordo non è più verde fisso:

```html
            <li><strong>🟢 Green Border:</strong> Indicates a ComboBox has been enhanced with search</li>
```

diventa

```html
            <li><strong>🔲 Highlighted Border:</strong> Indicates a ComboBox has been enhanced with search</li>
```

Riga 162 — lo sfondo verde chiaro è stato rimosso perché illeggibile su tema scuro:

```html
            <li><strong>💡 Light Green Background:</strong> Enhanced ComboBoxes have a subtle green background</li>
```

diventa

```html
            <li><strong>🌗 Theme Aware:</strong> The highlight follows your QGIS colour theme, so it stays readable in dark mode</li>
```

Infine, subito dopo la lista degli indicatori visivi (dopo la riga 163, `</ul>`), aggiungi questo blocco che documenta la riconciliazione del testo:

```html
        <div class="warning">
            <strong>⚠️ Note:</strong> If you type text that does not match any entry and then click away, the field returns to the value that is actually selected. The model always uses the selected entry, never the text you typed.
        </div>
```

- [ ] **Step 3: Aggiornare `README.MD`**

Riga 6 — la versione:

```markdown
![Version](https://img.shields.io/badge/version-1.2-blue)
```

diventa

```markdown
![Version](https://img.shields.io/badge/version-2.0-blue)
```

Riga 68:

```markdown
- **🟢 Green Border:** Indicates a ComboBox has been enhanced with search
```

diventa

```markdown
- **🔲 Highlighted Border:** Indicates a ComboBox has been enhanced with search
```

Riga 70:

```markdown
- **💡 Light Green Background:** Enhanced ComboBoxes have a subtle green background
```

diventa

```markdown
- **🌗 Theme Aware:** The highlight follows your QGIS colour theme, so it stays readable in dark mode
```

Riga 76:

```markdown
1. **🔍 Monitors** - Continuously monitors for open Modeler windows
```

diventa

```markdown
1. **🔍 Detects** - Activates as soon as an algorithm configuration window opens in the Modeler
```

Righe 98 e 100 — i requisiti erano più bassi di quanto `metadata.txt` dichiari, ed è ora corretto in una sola direzione:

```markdown
- **QGIS:** 3.28.9 or higher
```

diventa

```markdown
- **QGIS:** 3.34 or higher, including the 4.x series built on Qt6
```

e

```markdown
- **Qt:** 5.9+
```

diventa

```markdown
- **Qt:** 5.15+ or 6.x
```

Riga 106:

```markdown
- **Detection:** Qt Widget Analysis
```

diventa

```markdown
- **Detection:** Structural widget inspection, independent of interface language
```

- [ ] **Step 4: Verificare che il diff non sia esploso**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer" && git diff --numstat README.MD help.html && git diff --stat
```

Atteso: conteggi nell'ordine delle decine di righe, non delle migliaia. Se sono migliaia, le fini di riga sono state riscritte: `git checkout -- README.MD help.html` e riprova con un editor che le preservi.

- [ ] **Step 5: Eseguire la suite un'ultima volta**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins" && "/c/Program Files/QGIS 3.40.2/bin/python-qgis.bat" -m unittest discover -s modeler_search_enhancer/tests -t . -v
```

Atteso: `Ran 65 tests`, `OK`.

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/lalunni/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer"
git add README.MD help.html
git commit -m "docs: aggiorna aiuto e readme al comportamento della 2.0"
```

---

## Verifica manuale finale

I test automatici non possono premere tasti in una finestra reale. Dopo il Task 10, una passata a mano in QGIS:

1. Apri QGIS, poi il Processing Modeler.
2. Aggiungi al modello 6 input vettoriali e due algoritmi, per esempio Buffer e Centroidi.
3. Apri la configurazione del secondo algoritmo. Il campo del layer in ingresso deve avere il bordo evidenziato e il testo di suggerimento.
4. Digita `edifici nuovi` in ordine inverso, `nuovi edifici`: la voce deve comparire comunque.
5. Scegli una voce dal menu a tendina dei suggerimenti, conferma con OK, riapri: deve essere rimasta selezionata quella giusta.
6. Digita del testo inventato e sposta il fuoco altrove: il campo deve tornare al valore selezionato.
7. Con la finestra dell'algoritmo aperta, usa Salva come da un altro pannello del modeler: QGIS non deve chiudersi. Questo è lo scenario esatto della segnalazione della community.
8. Disattiva il plugin da Gestisci plugin con la finestra dell'algoritmo aperta: i campi devono tornare a tendine normali, non modificabili.
9. Ripeti i passi 3 e 4 su QGIS 4.0.
