"""
/***************************************************************************
 ModelerSearchEnhancer
                                 A QGIS plugin
 Search functionality for QGIS Processing Modeler algorithm outputs/inputs
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QTimer, Qt, QSortFilterProxyModel, QStringListModel
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDialog, QLabel, QCompleter, QComboBox
from qgis.core import QgsApplication
import os.path


class SearchableComboBox(QComboBox):
    """ComboBox con ricerca integrata"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        
        # Modello per il filtro
        self.pFilterModel = QSortFilterProxyModel(self)
        self.pFilterModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.pFilterModel.setSourceModel(self.model())
        
        # Completer personalizzato
        self.completer = QCompleter(self.pFilterModel, self)
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.setCompleter(self.completer)
        
        # Connessioni
        self.lineEdit().textEdited.connect(self.pFilterModel.setFilterFixedString)
        self.completer.activated.connect(self.onCompleterActivated)

    def onCompleterActivated(self, text):
        """Gestisce la selezione dal completer"""
        if text:
            index = self.findText(text)
            if index >= 0:
                self.setCurrentIndex(index)

    def setModel(self, model):
        """Override setModel per aggiornare il proxy"""
        super().setModel(model)
        self.pFilterModel.setSourceModel(model)
        self.completer.setModel(self.pFilterModel)

    def setModelColumn(self, column):
        """Override setModelColumn"""
        self.completer.setCompletionColumn(column)
        self.pFilterModel.setFilterKeyColumn(column)
        super().setModelColumn(column)


class ModelerSearchEnhancer:
    """Plugin per aggiungere ricerca agli input del Modeler"""

    def __init__(self, iface):
        """Constructor."""
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
        # Localizzazione
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'ModelerSearchEnhancer_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.monitored_widgets = set()
        self.enhanced_combos = set()
        
    def tr(self, message):
        """Traduzione stringhe."""
        return QCoreApplication.translate('ModelerSearchEnhancer', message)

    def initGui(self):
        """Inizializza il plugin."""        
        # Avvia il monitoring delle finestre
        self.setupModelerMonitoring()
        
        # Crea azione principale del plugin
        icon_path = ':/plugins/modeler_search_enhancer/icon.png'
        self.main_action = QAction(
            QIcon(icon_path),
            self.tr(u'🔍 Modeler Search Enhancer'),
            self.iface.mainWindow()
        )
        self.main_action.setStatusTip(self.tr(u'Enhanced search for Modeler algorithm inputs/outputs'))
        self.main_action.setEnabled(False)  # Disabilitata perché lavora automaticamente
        self.main_action.triggered.connect(self.showPluginInfo)
        
        # Crea azione Help
        self.help_action = QAction(
            QIcon(':/images/themes/default/mActionHelpContents.svg'),
            self.tr(u'Help'),
            self.iface.mainWindow()
        )
        self.help_action.setStatusTip(self.tr(u'Show plugin documentation'))
        self.help_action.triggered.connect(self.showHelp)
        
        # Aggiungi al menu
        self.iface.addPluginToMenu(
            self.tr(u'&Modeler Search Enhancer'),
            self.main_action
        )
        self.iface.addPluginToMenu(
            self.tr(u'&Modeler Search Enhancer'),
            self.help_action
        )
        
        # Aggiungi alla toolbar (solo l'azione principale)
        self.iface.addToolBarIcon(self.main_action)
        
        self.actions.append(self.main_action)
        self.actions.append(self.help_action)

    def showPluginInfo(self):
        """Mostra informazioni sul plugin"""
        from qgis.PyQt.QtWidgets import QMessageBox
        
        QMessageBox.information(
            self.iface.mainWindow(),
            "Modeler Search Enhancer",
            "🔍 Modeler Search Enhancer Plugin\n\n"
            "This plugin automatically enhances ComboBox fields in the QGIS Processing Modeler "
            "with intelligent search capabilities.\n\n"
            "✅ Active and running in background\n"
            "🎯 Automatically detects Modeler windows\n"
            "🔍 Adds search to algorithm input/output ComboBoxes\n\n"
            "For detailed instructions, click Help in the plugin menu."
        )

    def showHelp(self):
        """Mostra la documentazione del plugin"""
        import os
        import webbrowser
        from qgis.PyQt.QtCore import QUrl
        from qgis.PyQt.QtGui import QDesktopServices
        
        # Percorso del file di help
        help_file = os.path.join(self.plugin_dir, 'help.html')
        
        # Verifica se il file esiste
        if os.path.exists(help_file):
            # Apri il file HTML nel browser predefinito
            help_url = QUrl.fromLocalFile(help_file)
            QDesktopServices.openUrl(help_url)
        else:
            # Se il file non esiste, mostra un messaggio di errore
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Help File Not Found",
                f"Help documentation file not found at:\n{help_file}\n\n"
                "Please make sure the help.html file is in the plugin directory."
            )

    def setupModelerMonitoring(self):
        """Configura il monitoring delle finestre del Modeler"""
        self.window_timer = QTimer()
        self.window_timer.timeout.connect(self.checkForModelerWidgets)
        self.window_timer.start(500)  # Controlla ogni mezzo secondo

    def checkForModelerWidgets(self):
        """Controlla i widget del Modeler"""
        current_widgets = set()
        
        for widget in QgsApplication.allWidgets():
            if widget and hasattr(widget, 'isVisible') and widget.isVisible():
                if self.isModelerWidget(widget):
                    current_widgets.add(widget)
                    
                    # Se è un nuovo widget, miglioralo
                    if widget not in self.monitored_widgets:
                        self.enhanceModelerWidget(widget)
        
        self.monitored_widgets = current_widgets

    def isModelerWidget(self, widget):
        """Identifica i widget del Modeler"""
        if not widget:
            return False
            
        try:
            window_title = getattr(widget, 'windowTitle', lambda: '')().lower()
            object_name = getattr(widget, 'objectName', lambda: '')().lower()
            
            # Cerca finestre del Modeler con ComboBox
            modeler_indicators = [
                ('tabella' in window_title or 'selezione' in window_title) and len(widget.findChildren(QComboBox)) > 0,
                'modeler' in object_name and len(widget.findChildren(QComboBox)) > 0,
                isinstance(widget, QDialog) and len(widget.findChildren(QComboBox)) > 0 and 'utilizzo del risultato' in window_title.lower()
            ]
            
            return any(modeler_indicators)
            
        except Exception:
            return False

    def enhanceModelerWidget(self, widget):
        """Migliora un widget del Modeler"""
        try:
            # Trova tutti i ComboBox
            combo_boxes = widget.findChildren(QComboBox)
            
            for combo_box in combo_boxes:
                if (combo_box not in self.enhanced_combos and 
                    combo_box.count() > 1 and 
                    not hasattr(combo_box, '_search_enhanced') and
                    self.shouldEnhanceComboBox(combo_box)):
                    
                    self.enhanceComboBox(combo_box)
                    self.enhanced_combos.add(combo_box)
                    combo_box._search_enhanced = True
                    
        except Exception as e:
            print(f"Errore nel miglioramento widget: {e}")

    def shouldEnhanceComboBox(self, combo_box):
        """Determina se un ComboBox dovrebbe essere migliorato con ricerca"""
        try:
            # Controlla il contenuto per identificare se sono input/output del Modeler
            if combo_box.count() == 0:
                return False
            
            # Prendi alcuni elementi di esempio per analizzare il contenuto
            sample_items = []
            for i in range(min(3, combo_box.count())):
                item_text = combo_box.itemText(i)
                if item_text:
                    sample_items.append(item_text.lower())
            
            print(f"Analizzando ComboBox con {combo_box.count()} elementi")
            print(f"Primi elementi: {sample_items}")
            
            # Criteri per identificare ComboBox di input/output del Modeler
            modeler_input_indicators = [
                # Cerca pattern tipici degli output del Modeler
                any('"' in item for item in sample_items),  # Gli output hanno spesso virgolette
                any('dall\'algoritmo' in item for item in sample_items),  # Testo italiano tipico
                any('from algorithm' in item for item in sample_items),  # Testo inglese tipico
                any('output' in item for item in sample_items),  # Contiene "output"
                any('result' in item for item in sample_items),  # Contiene "result"
                any('estratto' in item or 'elementi' in item or 'risultato' in item for item in sample_items),
            ]
            
            # Criteri per ESCLUDERE ComboBox che NON dovrebbero essere migliorati
            exclude_indicators = [
                # Escludi ComboBox con pochi elementi (probabilmente dropdown di configurazione)
                combo_box.count() < 3,
                # Escludi se contiene solo valori numerici o di configurazione
                all(item.isdigit() or item in ['true', 'false', 'yes', 'no'] for item in sample_items if item),
                # Escludi se gli elementi sono molto corti (probabilmente configurazioni)
                all(len(item) < 10 for item in sample_items if item),
                # Escludi ComboBox di dipendenze (spesso vuoti o con pochi elementi standard)
                combo_box.count() == 1 and sample_items and ('dipendenze' in sample_items[0] or 'dependencies' in sample_items[0]),
            ]
            
            # Analizza il parent per contesto aggiuntivo
            parent_context = self.analyzeParentContext(combo_box)
            
            should_enhance = any(modeler_input_indicators) and not any(exclude_indicators) and parent_context
            
            print(f"Decisione: {'MIGLIORA' if should_enhance else 'SALTA'} questo ComboBox")
            print(f"Indicatori modeler: {modeler_input_indicators}")
            print(f"Indicatori esclusione: {exclude_indicators}")
            print(f"Contesto parent: {parent_context}")
            print("---")
            
            return should_enhance
            
        except Exception as e:
            print(f"Errore nell'analisi ComboBox: {e}")
            return False

    def analyzeParentContext(self, combo_box):
        """Analizza il contesto del parent per determinare se è un campo di input"""
        try:
            parent = combo_box.parent()
            if not parent:
                return False
            
            # Cerca label o testi vicini che indicano che è un campo di input
            labels = parent.findChildren(QLabel)
            
            input_context_keywords = [
                'layer in ingresso', 'input layer', 'layer input',
                'utilizzo del risultato', 'use result', 'algorithm result',
                'campo rimanente', 'remaining field',
                'selezione', 'selection', 'choose', 'select'
            ]
            
            exclude_context_keywords = [
                'dependencies', 'dipendenze', 'parameters', 'parametri',
                'configuration', 'configurazione', 'settings', 'impostazioni'
            ]
            
            for label in labels:
                label_text = label.text().lower()
                
                # Se trova keyword di esclusione nel contesto, non migliorare
                if any(keyword in label_text for keyword in exclude_context_keywords):
                    return False
                    
                # Se trova keyword di input nel contesto, migliorare
                if any(keyword in label_text for keyword in input_context_keywords):
                    return True
            
            return True  # Default: migliora se non trova indicatori negativi
            
        except Exception as e:
            print(f"Errore nell'analisi contesto: {e}")
            return True

    def enhanceComboBox(self, combo_box):
        """Migliora un ComboBox rendendolo ricercabile"""
        try:
            # Salva gli elementi esistenti
            original_items = []
            for i in range(combo_box.count()):
                original_items.append(combo_box.itemText(i))
            
            print(f"Elementi originali: {len(original_items)}")
            
            # Rendi il combo editabile se non lo è già
            if not combo_box.isEditable():
                combo_box.setEditable(True)
            
            # Configura il line edit
            line_edit = combo_box.lineEdit()
            if line_edit:
                # Imposta placeholder
                line_edit.setPlaceholderText("🔍 Digita per filtrare...")
                
                # Variabili di controllo per PREVENIRE LOOP
                self._is_updating = False
                self._last_search_text = ""
                
                # Crea un completer SEMPLICE senza modificare il combo
                completer = QCompleter(original_items)
                completer.setCaseSensitivity(Qt.CaseInsensitive)
                completer.setFilterMode(Qt.MatchContains)
                completer.setCompletionMode(QCompleter.PopupCompletion)
                
                # Imposta il completer
                line_edit.setCompleter(completer)
                
                # Funzione di filtro SICURA senza modificare il combo
                def safe_filter():
                    # CONTROLLO ANTI-LOOP
                    if self._is_updating:
                        return
                        
                    current_text = line_edit.text().strip()
                    
                    # Se il testo non è cambiato, non fare nulla
                    if current_text == self._last_search_text:
                        return
                        
                    self._last_search_text = current_text
                    
                    print(f"Filtro sicuro: '{current_text}'")
                    
                    if current_text:
                        # Filtra SOLO per il completer, NON modificare il combo
                        filtered_items = []
                        search_terms = current_text.lower().split()
                        
                        for item in original_items:
                            item_lower = item.lower()
                            if all(term in item_lower for term in search_terms):
                                filtered_items.append(item)
                        
                        print(f"Trovati {len(filtered_items)} risultati")
                        
                        # Aggiorna SOLO il modello del completer
                        if filtered_items:
                            completer_model = QStringListModel(filtered_items)
                            completer.setModel(completer_model)
                            
                            # Mostra il popup del completer
                            if not completer.popup().isVisible():
                                completer.complete()
                        else:
                            # Nessun risultato, nascondi popup
                            completer.popup().hide()
                    else:
                        # Testo vuoto, ripristina completer originale
                        completer_model = QStringListModel(original_items)
                        completer.setModel(completer_model)
                
                # Connetti il filtro SOLO a editingFinished per evitare loop
                line_edit.editingFinished.connect(safe_filter)
                
                # Timer per filtro con delay (per evitare troppi aggiornamenti)
                from qgis.PyQt.QtCore import QTimer
                self._filter_timer = QTimer()
                self._filter_timer.setSingleShot(True)
                self._filter_timer.timeout.connect(safe_filter)
                
                def on_text_changed():
                    # NON chiamare direttamente il filtro, usa il timer
                    if not self._is_updating:
                        self._filter_timer.start(300)  # 300ms delay
                
                line_edit.textChanged.connect(on_text_changed)
                
                # Gestisci la selezione dal completer
                def on_completer_activated(text):
                    print(f"Selezionato dal completer: '{text}'")
                    if text in original_items:
                        self._is_updating = True  # PREVIENI LOOP
                        
                        index = original_items.index(text)
                        combo_box.setCurrentIndex(index)
                        line_edit.setText(text)
                        
                        self._is_updating = False  # FINE AGGIORNAMENTO
                
                completer.activated.connect(on_completer_activated)
                
                # Gestisci la selezione diretta dal combo
                def on_combo_activated(index):
                    if self._is_updating:  # PREVIENI LOOP
                        return
                        
                    if 0 <= index < combo_box.count():
                        selected_text = combo_box.itemText(index)
                        print(f"Selezionato dal combo: '{selected_text}'")
                        
                        self._is_updating = True  # PREVIENI LOOP
                        line_edit.setText(selected_text)
                        self._is_updating = False  # FINE AGGIORNAMENTO
                
                combo_box.activated.connect(on_combo_activated)
                
                # Stile per indicare che è ricercabile
                line_edit.setStyleSheet("""
                    QLineEdit {
                        background-color: #f0f8f0;
                        border: 2px solid #2E8B57;
                        border-radius: 3px;
                        padding: 2px 5px;
                    }
                    QLineEdit:focus {
                        background-color: white;
                        border-color: #228B22;
                    }
                """)
                
                # Politica di inserimento
                combo_box.setInsertPolicy(QComboBox.NoInsert)
                
                print(f"Migliorato ComboBox ANTI-LOOP - {len(original_items)} elementi")
                return True
                
        except Exception as e:
            print(f"Errore nel miglioramento ComboBox: {e}")
            return False

    def unload(self):
        """Rimuove il plugin."""
        # Ferma il timer
        if hasattr(self, 'window_timer'):
            self.window_timer.stop()
            
        # Pulisci i riferimenti
        self.enhanced_combos.clear()
        self.monitored_widgets.clear()
            
        # Rimuovi azioni dal menu e toolbar
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Modeler Search Enhancer'),
                action)
            
            # Rimuovi dalla toolbar solo se è l'azione principale
            if action == getattr(self, 'main_action', None):
                self.iface.removeToolBarIcon(action)