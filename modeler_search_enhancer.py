"""
/***************************************************************************
 ModelerSearchEnhancer
                                 A QGIS plugin
 Search functionality for QGIS Processing Modeler algorithm outputs/inputs
 ***************************************************************************/
"""

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QTimer, Qt, QSortFilterProxyModel, QStringListModel, QUrl
from qgis.PyQt.QtGui import QIcon, QDesktopServices
from qgis.PyQt.QtWidgets import QAction, QDialog, QLabel, QCompleter, QComboBox, QMessageBox
from qgis.core import QgsApplication
import os
import os.path


class SearchableComboBox(QComboBox):
    def __init__(self, parent=None):
        """
        Initializes a custom QComboBox with enhanced search and autocomplete features.
        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        Features:
            - Sets the combo box to be editable and prevents new items from being inserted by the user.
            - Uses a QSortFilterProxyModel to enable case-insensitive filtering of the combo box items.
            - Integrates a QCompleter with unfiltered popup completion mode for improved autocompletion.
            - Connects the line edit's textEdited signal to update the filter string in real time.
            - Connects the completer's activated signal to a custom handler for item selection.
        """
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        
        self.pFilterModel = QSortFilterProxyModel(self)
        self.pFilterModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.pFilterModel.setSourceModel(self.model())
        
        self.completer = QCompleter(self.pFilterModel, self)
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.setCompleter(self.completer)
        
        self.lineEdit().textEdited.connect(self.pFilterModel.setFilterFixedString)
        self.completer.activated.connect(self.onCompleterActivated)

    def onCompleterActivated(self, text):
        """
        Slot called when an item is activated in the completer.
        Args:
            text (str): The text of the activated completer item.
        Returns:
            None
        """
        if text:
            index = self.findText(text)
            if index >= 0:
                self.setCurrentIndex(index)

    def setModel(self, model):
        """
        Sets the given model for the view and updates the proxy filter model and completer accordingly.
        Args:
            model (QAbstractItemModel): The model to be set for the view.
        Returns:
            None
        """
        super().setModel(model)
        self.pFilterModel.setSourceModel(model)
        self.completer.setModel(self.pFilterModel)

    def setModelColumn(self, column):
        """
        Sets the column used for model completion and filtering.
        Args:
            column (int): The index of the column to be used for completion and filtering.
        Returns:
            None
        """
        self.completer.setCompletionColumn(column)
        self.pFilterModel.setFilterKeyColumn(column)
        super().setModelColumn(column)


class ModelerSearchEnhancer:
    def __init__(self, iface):
        """
        Initializes the ModelerSearchEnhancer plugin.
        Args:
            iface: The QGIS interface instance.
        This method sets up the plugin directory, loads the appropriate locale translation if available,
        and initializes internal data structures for actions, monitored widgets, and enhanced combo boxes.
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
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
        """
        Translates the given message string using QGIS's translation system.
        Args:
            message (str): The message string to be translated.
        Returns:
            str: The translated string.
        """
        return QCoreApplication.translate('ModelerSearchEnhancer', message)

    def initGui(self):
        """
        Initializes the plugin's GUI elements and actions.
        This method sets up monitoring for the modeler, creates the main and help actions
        with their respective icons, tooltips, and triggers, and adds them to the QGIS
        plugin menu and toolbar. The actions are also appended to the plugin's actions list.
        Args:
            None
        Returns:
            None
        """
        self.setupModelerMonitoring()
        
        icon_path = ':/plugins/modeler_search_enhancer/icon.png'
        self.main_action = QAction(
            QIcon(icon_path),
            self.tr(u'🔍 Modeler Search Enhancer'),
            self.iface.mainWindow()
        )
        self.main_action.setStatusTip(self.tr(u'Enhanced search for Modeler algorithm inputs/outputs'))
        self.main_action.setEnabled(False)
        self.main_action.triggered.connect(self.showPluginInfo)
        
        self.help_action = QAction(
            QIcon(':/images/themes/default/mActionHelpContents.svg'),
            self.tr(u'Help'),
            self.iface.mainWindow()
        )
        self.help_action.setStatusTip(self.tr(u'Show plugin documentation'))
        self.help_action.triggered.connect(self.showHelp)
        
        self.iface.addPluginToMenu(
            self.tr(u'&Modeler Search Enhancer'),
            self.help_action
        )
        
        self.actions.append(self.help_action)

    def showPluginInfo(self):
        """
        Displays an information message box with details about the Modeler Search Enhancer plugin.
        Args:
            self: The instance of the plugin class, which should have access to the QGIS interface via self.iface.
        Returns:
            None
        """
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
        """
        Displays the help documentation for the plugin.
        This method attempts to open a local 'help.html' file located in the plugin directory.
        If the file exists, it is opened in the default web browser. If not, a warning message is shown to the user.
        Args:
            None
        Returns:
            None
        """
        help_file = os.path.join(self.plugin_dir, 'help.html')
        
        if os.path.exists(help_file):
            help_url = QUrl.fromLocalFile(help_file)
            QDesktopServices.openUrl(help_url)
        else:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Help File Not Found",
                f"Help documentation file not found at:\n{help_file}\n\n"
                "Please make sure the help.html file is in the plugin directory."
            )

    def setupModelerMonitoring(self):
        """
        Sets up a QTimer to periodically check for modeler widgets in the QGIS interface.
        This method initializes a QTimer instance, connects its timeout signal to the
        checkForModelerWidgets method, and starts the timer with a 500 ms interval.
        Args:
            None
        Returns:
            None
        """
        self.window_timer = QTimer()
        self.window_timer.timeout.connect(self.checkForModelerWidgets)
        self.window_timer.start(500)

    def checkForModelerWidgets(self):
        """
        Checks for currently visible Modeler widgets in the QGIS application, enhances any new ones found,
        and updates the set of monitored widgets.
        Iterates through all widgets in the application, identifies those that are Modeler widgets and visible,
        enhances any that are not already being monitored, and updates the internal set of monitored widgets.
        Args:
            None
        Returns:
            None
        """
        current_widgets = set()
        
        for widget in QgsApplication.allWidgets():
            if widget and hasattr(widget, 'isVisible') and widget.isVisible():
                if self.isModelerWidget(widget):
                    current_widgets.add(widget)
                    
                    if widget not in self.monitored_widgets:
                        self.enhanceModelerWidget(widget)
        
        self.monitored_widgets = current_widgets

    def isModelerWidget(self, widget):
        """
        Determines whether the given widget is a "Modeler" widget based on its properties.
        Args:
            widget (QWidget): The widget to check.
        Returns:
            bool: True if the widget is identified as a Modeler widget, False otherwise.
        """
        if not widget:
            return False
            
        try:
            window_title = getattr(widget, 'windowTitle', lambda: '')().lower()
            object_name = getattr(widget, 'objectName', lambda: '')().lower()
            
            modeler_indicators = [
                ('tabella' in window_title or 'selezione' in window_title) and len(widget.findChildren(QComboBox)) > 0,
                'modeler' in object_name and len(widget.findChildren(QComboBox)) > 0,
                isinstance(widget, QDialog) and len(widget.findChildren(QComboBox)) > 0 and 'utilizzo del risultato' in window_title.lower()
            ]
            
            return any(modeler_indicators)
            
        except Exception:
            return False

    def enhanceModelerWidget(self, widget):
        """
        Enhances all QComboBox widgets within the given widget by adding search functionality,
        if they meet certain criteria and have not already been enhanced.
        Args:
            widget (QWidget): The parent widget containing QComboBox children to enhance.
        Returns:
            None
        """
        try:
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
            pass

    def shouldEnhanceComboBox(self, combo_box):
        """
        Determines whether a given QComboBox should be enhanced based on its items and context.
        Args:
            combo_box (QComboBox): The combo box widget to analyze.
        Returns:
            bool: True if the combo box meets the criteria for enhancement, False otherwise.
        The method analyzes the contents of the combo box and its parent context to decide if it is likely
        to represent a modeler input or output, and excludes cases where the combo box is too simple or irrelevant.
        """
        try:
            if combo_box.count() == 0:
                return False
            
            sample_items = []
            for i in range(min(3, combo_box.count())):
                item_text = combo_box.itemText(i)
                if item_text:
                    sample_items.append(item_text.lower())
            
            modeler_input_indicators = [
                any('"' in item for item in sample_items),
                any('dall\'algoritmo' in item for item in sample_items),
                any('from algorithm' in item for item in sample_items),
                any('output' in item for item in sample_items),
                any('result' in item for item in sample_items),
                any('estratto' in item or 'elementi' in item or 'risultato' in item for item in sample_items),
            ]
            
            exclude_indicators = [
                combo_box.count() < 3,
                all(item.isdigit() or item in ['true', 'false', 'yes', 'no'] for item in sample_items if item),
                all(len(item) < 10 for item in sample_items if item),
                combo_box.count() == 1 and sample_items and ('dipendenze' in sample_items[0] or 'dependencies' in sample_items[0]),
            ]
            
            parent_context = self.analyzeParentContext(combo_box)
            
            should_enhance = any(modeler_input_indicators) and not any(exclude_indicators) and parent_context
            
            return should_enhance
            
        except Exception as e:
            return False

    def analyzeParentContext(self, combo_box):
        """
        Analyzes the parent context of a given combo box to determine if it is related to input selection.
        Args:
            combo_box (QComboBox): The combo box whose parent context is to be analyzed.
        Returns:
            bool: True if the parent context suggests an input selection (based on label keywords), 
                  False if it matches any exclusion keywords or has no parent.
        """
        try:
            parent = combo_box.parent()
            if not parent:
                return False
            
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
                
                if any(keyword in label_text for keyword in exclude_context_keywords):
                    return False
                    
                if any(keyword in label_text for keyword in input_context_keywords):
                    return True
            
            return True
            
        except Exception:
            return True

    def enhanceComboBox(self, combo_box):
        """
        Enhances a given QComboBox with advanced search and filtering capabilities.
        This method makes the combo box editable, adds a placeholder, and attaches a QCompleter
        that allows users to filter items by typing. The filtering is case-insensitive and matches
        all search terms. The method also synchronizes the selection between the combo box and the
        completer, and applies custom styling to the line edit.
        Args:
            combo_box (QComboBox): The combo box widget to enhance.
        Returns:
            bool: True if the enhancement was successful, False otherwise.
        """
        try:
            original_items = []
            for i in range(combo_box.count()):
                original_items.append(combo_box.itemText(i))
            
            if not combo_box.isEditable():
                combo_box.setEditable(True)
            
            line_edit = combo_box.lineEdit()
            if line_edit:
                line_edit.setPlaceholderText("🔍 Digita per filtrare...")
                
                self._is_updating = False
                self._last_search_text = ""
                
                completer = QCompleter(original_items)
                completer.setCaseSensitivity(Qt.CaseInsensitive)
                completer.setFilterMode(Qt.MatchContains)
                completer.setCompletionMode(QCompleter.PopupCompletion)
                
                line_edit.setCompleter(completer)
                
                def safe_filter():
                    """
                    Filters the items in the completer based on the current text in the line edit.
                    Updates the completer's model to show only items that match all search terms entered by the user.
                    If the search text is empty, restores the original list of items.
                    Args:
                        None
                    Returns:
                        None
                    """
                    if self._is_updating:
                        return
                        
                    current_text = line_edit.text().strip()
                    
                    if current_text == self._last_search_text:
                        return
                        
                    self._last_search_text = current_text
                    
                    if current_text:
                        filtered_items = []
                        search_terms = current_text.lower().split()
                        
                        for item in original_items:
                            item_lower = item.lower()
                            if all(term in item_lower for term in search_terms):
                                filtered_items.append(item)
                        
                        if filtered_items:
                            completer_model = QStringListModel(filtered_items)
                            completer.setModel(completer_model)
                            
                            if not completer.popup().isVisible():
                                completer.complete()
                        else:
                            completer.popup().hide()
                    else:
                        completer_model = QStringListModel(original_items)
                        completer.setModel(completer_model)
                
                line_edit.editingFinished.connect(safe_filter)
                
                self._filter_timer = QTimer()
                self._filter_timer.setSingleShot(True)
                self._filter_timer.timeout.connect(safe_filter)
                
                def on_text_changed():
                    """
                    Triggered when the text changes in the associated widget. If an update is not already in progress,
                    starts a timer to delay filtering by 300 milliseconds.
                    Args:
                        None
                    Returns:
                        None
                    """
                    if not self._is_updating:
                        self._filter_timer.start(300)
                
                line_edit.textChanged.connect(on_text_changed)
                
                def on_completer_activated(text):
                    """
                    Handles the event when an item is selected from the completer dropdown.
                    Args:
                        text (str): The text selected from the completer.
                    Returns:
                        None
                    """
                    if text in original_items:
                        self._is_updating = True
                        
                        index = original_items.index(text)
                        combo_box.setCurrentIndex(index)
                        line_edit.setText(text)
                        
                        self._is_updating = False
                
                completer.activated.connect(on_completer_activated)
                
                def on_combo_activated(index):
                    """
                    Handles the activation event of the combo box, updating the associated line edit with the selected item's text.
                    Args:
                        index (int): The index of the activated item in the combo box.
                    Returns:
                        None
                    """
                    if self._is_updating:
                        return
                        
                    if 0 <= index < combo_box.count():
                        selected_text = combo_box.itemText(index)
                        self._is_updating = True
                        line_edit.setText(selected_text)
                        self._is_updating = False
                
                combo_box.activated.connect(on_combo_activated)
                
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
                
                combo_box.setInsertPolicy(QComboBox.NoInsert)
                
                return True
                
        except Exception as e:
            return False

    def unload(self):
        """
        Unloads the plugin by stopping timers, clearing internal data structures, and removing plugin actions from the QGIS interface.
        Args:
            None
        Returns:
            None
        """
        if hasattr(self, 'window_timer'):
            self.window_timer.stop()
            
        self.enhanced_combos.clear()
        self.monitored_widgets.clear()
            
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Modeler Search Enhancer'),
                action)