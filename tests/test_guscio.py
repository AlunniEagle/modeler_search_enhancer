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


def moduli_distribuiti():
    """Ogni file .py alla radice del plugin, cioè tutto ciò che viene spedito.

    `MODULI` elenca i moduli scritti a mano; questa funzione guarda invece
    l'intero contenuto della cartella, perché un file generato o dimenticato
    viene distribuito agli utenti esattamente come gli altri.
    """
    return sorted(
        nome
        for nome in os.listdir(PLUGIN_DIR)
        if nome.endswith(".py")
    )


class TestApiVietate(unittest.TestCase):
    """Regressione di CR-1 e CR-5 a livello di sorgente."""

    def test_nessun_uso_di_allwidgets(self):
        # Il controllo è sull'albero sintattico, non sul testo. La
        # docstring di `dialog_watcher` **cita** `QgsApplication.allWidgets()`
        # per spiegare che cosa ha sostituito e perché: una ricerca
        # testuale confonderebbe quella prosa con una chiamata reale.
        # Solo un accesso ad attributo o un nome conta come uso.
        import ast

        for nome in MODULI:
            for nodo in ast.walk(ast.parse(sorgente(nome))):
                if isinstance(nodo, ast.Attribute):
                    self.assertNotEqual(nodo.attr, "allWidgets", nome)
                elif isinstance(nodo, ast.Name):
                    self.assertNotEqual(nodo.id, "allWidgets", nome)

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
        # Anche questo va sull'albero sintattico, per la stessa ragione: un
        # commento che documentasse "non usare Qt.CaseInsensitive" farebbe
        # fallire una ricerca testuale.
        #
        # La distinzione che conta: nella forma non scoped `Qt.CaseInsensitive`
        # il nodo interno è un `Name`, mentre nella forma corretta
        # `Qt.CaseSensitivity.CaseInsensitive` è a sua volta un `Attribute`.
        # Il controllo sotto scatta quindi solo sulla forma sbagliata.
        import ast

        vietati = {
            ("Qt", "CaseInsensitive"),
            ("Qt", "MatchContains"),
            ("QComboBox", "NoInsert"),
            ("QCompleter", "PopupCompletion"),
            ("QCompleter", "UnfilteredPopupCompletion"),
            ("QEvent", "Show"),
            ("QPalette", "Highlight"),
        }
        for nome in MODULI:
            for nodo in ast.walk(ast.parse(sorgente(nome))):
                if not isinstance(nodo, ast.Attribute):
                    continue
                if not isinstance(nodo.value, ast.Name):
                    continue
                self.assertNotIn(
                    (nodo.value.id, nodo.attr),
                    vietati,
                    "{}: {}.{}".format(nome, nodo.value.id, nodo.attr),
                )

    def test_nessun_import_sip_diretto(self):
        for nome in MODULI:
            testo = sorgente(nome)
            for riga in testo.splitlines():
                self.assertNotEqual(riga.strip(), "import sip", nome)

    def test_nessun_import_diretto_di_pyqt(self):
        # Il repository dei plugin QGIS esegue un controllo Qt6 su **ogni**
        # file distribuito e rifiuta gli import diretti di PyQt5 o PyQt6:
        # solo `qgis.PyQt` funziona su entrambe le versioni.
        #
        # Il controllo guarda tutti i .py della cartella, non i soli moduli
        # scritti a mano: nella 2.0 a far fallire il controllo è stato un
        # file generato che nessuno importava, e che i controlli limitati a
        # `MODULI` non vedevano.
        import ast

        for nome in moduli_distribuiti():
            for nodo in ast.walk(ast.parse(sorgente(nome))):
                if isinstance(nodo, ast.Import):
                    for alias in nodo.names:
                        self.assertNotIn(
                            alias.name.split(".")[0],
                            ("PyQt5", "PyQt6"),
                            "{}: import {}".format(nome, alias.name),
                        )
                elif isinstance(nodo, ast.ImportFrom):
                    radice = (nodo.module or "").split(".")[0]
                    self.assertNotIn(
                        radice,
                        ("PyQt5", "PyQt6"),
                        "{}: from {} import ...".format(nome, nodo.module),
                    )

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
        # Organizzazione/app neutre e dedicate al progetto, ripulite subito
        # dopo l'uso: senza `clear()` il test lascerebbe chiavi persistenti
        # nel registro di chi esegue i test.
        from modeler_search_enhancer.modeler_search_enhancer import (
            leggi_locale_utente,
        )
        from qgis.PyQt.QtCore import QSettings

        vuoto = QSettings("ModelerSearchEnhancerTest", "NoSuchApp")
        vuoto.remove("locale/userLocale")
        try:
            self.assertEqual(leggi_locale_utente(vuoto), "")
        finally:
            vuoto.clear()

    def test_locale_presente_viene_troncato_a_due_lettere(self):
        from modeler_search_enhancer.modeler_search_enhancer import (
            leggi_locale_utente,
        )
        from qgis.PyQt.QtCore import QSettings

        settings = QSettings("ModelerSearchEnhancerTest", "LocaleApp")
        settings.setValue("locale/userLocale", "it_IT")
        try:
            self.assertEqual(leggi_locale_utente(settings), "it")
        finally:
            settings.clear()


if __name__ == "__main__":
    unittest.main()
