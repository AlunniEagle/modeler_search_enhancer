# Modeler Search Enhancer — riprogettazione

Data: 2026-09-10
Stato: approvato, in attesa di piano di implementazione

## 1. Problema

Il plugin aggiunge una ricerca ai combo dei parametri del Processing Modeler. Nella versione 1.2 presenta tre classi di difetti:

1. **Fa crashare QGIS.** Segnalato dalla community su QGIS 3.44.1 (Qt 5.15.13) con `access violation` e `Windows fatal exception 0x80010108`.
2. **La ricerca non funziona in modo affidabile.** Il filtro si applica a un solo combo, a volte non si applica affatto, e la voce selezionata può non essere quella cercata.
3. **È inerte su QGIS 4.0 / Qt6.** Si carica senza errori visibili e non fa nulla.

L'obiettivo è un plugin senza crash, con una ricerca corretta e prevedibile, su una codebase unica compatibile Qt5 e Qt6.

## 2. Evidenze raccolte

Tutte le affermazioni di questa sezione sono state verificate eseguendo codice contro le installazioni locali QGIS 3.34.15 (Qt 5.15.13 / PyQt 5.15.11), 3.40.2 (Qt 5.15.13 / PyQt 5.15.10) e 4.0.0 (Qt 6.8.1 / PyQt 6.10.2).

### 2.1 Struttura reale dei widget

Aprendo un vero `ModelerParametersDialog` in modalità offscreen, ogni combo rilevante si trova in questa catena, **identica** su 3.34, 3.40 e 4.0:

```
ModelerParametersDialog                     objectName == "ModelerParametersDialog"
  └── QgsProcessingModelerParameterWidget
        └── QStackedWidget                  una pagina per tipo di sorgente
              └── QWidget
                    └── QComboBox           <- il combo da migliorare
```

`objectName()` è impostato esplicitamente dal codice QGIS (`self.setObjectName("ModelerParametersDialog")`) in tutte e tre le versioni: è un aggancio stabile e indipendente dalla lingua.

### 2.2 QGIS legge il valore via `currentData()`, non per indice

I combo delle sorgenti portano `itemData`:

| Tipo di voce | `itemText` | `itemData` |
|---|---|---|
| Output di algoritmo | `“Buffered” from algorithm “Buffer step one”` | `['buffer_1', 'OUTPUT']` |
| Input del modello | `Input layer` | `'INPUT_LAYER'` |
| Parametro booleano | `Yes` / `No` | `True` / `False` |

Conseguenza vincolante per il design: la selezione va risolta **sempre** sul combo vivo, mai su una lista fotografata in precedenza.

### 2.3 Effetti di `setEditable()`

Verificato su QGIS 3.40 con un combo a tre voci, selezione su indice 1:

| Azione | `currentIndex` | `currentText` | `currentData` |
|---|---|---|---|
| stato iniziale | 1 | `Beta layer` | `BETA_LAYER` |
| dopo `setEditable(True)` | 1 | `Beta layer` | `BETA_LAYER` |
| dopo testo libero, `NoInsert` | 1 | `testo libero inesistente` | `BETA_LAYER` |
| dopo `setEditable(False)` | 1 | `Beta layer` | `BETA_LAYER` |

Tre conclusioni: rendere editabile il combo **non** altera il valore del modello; il testo libero fa **divergere** `currentText()` da `currentData()` senza corrompere il dato; `setEditable(False)` ripristina il testo corretto, quindi `unload()` può fare una pulizia completa.

### 2.4 Enum: forma scoped su entrambe le versioni

| Forma | PyQt5 5.15.11 | PyQt6 6.10.2 |
|---|---|---|
| `Qt.CaseSensitivity.CaseInsensitive` | OK | OK |
| `Qt.CaseInsensitive` | OK | `AttributeError` |
| `QComboBox.InsertPolicy.NoInsert` | OK | OK |
| `QComboBox.NoInsert` | OK | `AttributeError` |
| `QCompleter.CompletionMode.PopupCompletion` | OK | OK |
| `QCompleter.PopupCompletion` | OK | `AttributeError` |
| `Qt.MatchFlag.MatchContains` | OK | OK |
| `Qt.MatchContains` | OK | `AttributeError` |

La forma scoped funziona su entrambe: **una sola codebase, nessun branching**. Nota collaterale: su PyQt6 gli enum sono `enum.Enum` e non `IntEnum`, quindi `int(membro)` solleva `TypeError` — serve `.value` se si vuole l'intero.

### 2.5 Import di sip

| Forma | PyQt5 | PyQt6 |
|---|---|---|
| `import sip` | OK | `ModuleNotFoundError` |
| `from qgis.PyQt import sip` | OK | OK |

Si usa la seconda.

### 2.6 API disponibili

| API | 3.34.15 | 3.40.2 | 4.0.0 |
|---|---|---|---|
| `from qgis.gui import QgsProcessingModelerParameterWidget` | OK | OK | OK |
| `Qgis.MessageLevel.Warning` / `.Critical` | OK | OK | OK |
| `QComboBox.popupAboutToBeShown` | **inesistente** | **inesistente** | **inesistente** |

La classe del widget di parametro è esposta a Python su tutte le versioni: la scoperta strutturale può usare `isinstance()` invece di confrontare `type(w).__name__`.

`QComboBox` **non** ha alcun segnale `popupAboutToBeShown`: non esiste in Qt e non è aggiunto da QGIS. Il design non può dipenderne (cfr. 4.5).

### 2.7 Il framework di test disponibile è `unittest`

`pytest` non è installato in nessuna delle due distribuzioni QGIS locali; `unittest` della standard library sì. La suite si scrive con `unittest`.

È stato verificato che l'intero meccanismo di rilevamento è testabile headless su Qt5 e Qt6: con `QT_QPA_PLATFORM=offscreen`, un `QEvent.Show` su un dialog con `objectName` corretto raggiunge un event filter installato sull'applicazione, un dialog con altro `objectName` viene ignorato, e il `QTimer.singleShot(0, ...)` viene eseguito da `processEvents()`.

### 2.8 Le virgolette non sono ASCII

Le etichette generate da QGIS usano `U+201C`/`U+201D`, non `"`. Verificato: `'"' in label` è `False`, `'“' in label` è `True`.

## 3. Cause radice

### CR-1 — Il polling di `allWidgets()` fa crashare QGIS

`setupModelerMonitoring()` avvia un `QTimer` a 500 ms che itera `QgsApplication.allWidgets()` e chiama `isVisible()`, `windowTitle()`, `findChildren()` su ogni widget restituito.

`allWidgets()` restituisce *ogni* `QWidget` esistente in quell'istante, inclusi quelli **a metà costruzione** e quelli già distrutti in C++ il cui wrapper sip è ancora vivo. Chiamare metodi su questi dereferenzia memoria non valida.

Lo stack trace della segnalazione mostra entrambi i rami del difetto:

- il callback del plugin compare **sopra** `QFileDialog.getSaveFileName`, cioè il timer scatta dentro l'event loop annidato di un dialog nativo Windows basato su COM; da qui `0x80010108` (`RPC_E_DISCONNECTED`);
- l'`access violation` avviene dentro il costruttore di `QgsProcessingMapLayerComboBox` (`qgsprocessingmaplayercombobox.cpp:196`) mentre `ModelerParametersDialog.setupUi` sta ancora costruendo i widget.

Aggravante: `enhanced_combos` non viene mai ripulito durante la sessione, quindi accumula wrapper penzolanti a ogni apertura di dialog.

### CR-2 — Stato di ricerca condiviso sul singleton del plugin

`_is_updating`, `_last_search_text` e `_filter_timer` sono attributi di `self`, cioè dell'unica istanza del plugin, non del singolo combo. Tre conseguenze:

- `self._filter_timer` viene **riassegnato** a ogni combo migliorato: solo l'ultimo filtra ancora;
- `_last_search_text` è condiviso, quindi la guardia `if current_text == self._last_search_text: return` fa uscire subito `safe_filter` quando si digita la stessa stringa in un secondo combo — **nessun filtro**;
- `_is_updating` condiviso produce interferenze tra combo diversi.

### CR-3 — Lista di voci fotografata una volta sola

`original_items` è catturato al momento dell'enhancement e mai aggiornato, ma il modeler **ripopola** i combo quando cambiano gli algoritmi a monte. Alla selezione, `original_items.index(text)` seguito da `setCurrentIndex(index)` punta a una posizione di uno snapshot obsoleto. Combinato con 2.2, questo **collega la sorgente sbagliata nel modello**: è corruzione di dato, non un fastidio estetico.

### CR-4 — Rilevamento fragile e legato alla lingua

- Il gate primario di `shouldEnhanceComboBox` cerca `"` ASCII, che non compare mai nelle etichette reali (2.8).
- Gli altri indicatori sono stringhe hardcoded italiane e inglesi: su QGIS in tedesco, francese o spagnolo nessun indicatore corrisponde e il plugin non fa nulla.
- `isModelerWidget` cerca `'tabella'`, `'selezione'`, `'utilizzo del risultato'` nei titoli tradotti delle finestre.
- `all(len(item) < 10 ...)` tra le esclusioni scarta combo legittimi con nomi brevi, campionando peraltro solo le prime 3 voci.
- `enhanceModelerWidget` richiede `count() > 1` ma `shouldEnhanceComboBox` esclude `count() < 3`: i combo a 2 voci passano il primo gate e vengono poi scartati.
- `analyzeParentContext` restituisce `True` sia sul percorso di default sia nel gestore di eccezioni, quindi il gate di contesto è di fatto sempre vero.

### CR-5 — Enum non scoped: plugin inerte su Qt6

Sette usi di enum non scoped (righe 32, 35, 39, 404, 405, 406, 522) sollevano `AttributeError` su PyQt6. Le eccezioni vengono inghiottite dai blocchi `except Exception: return False`, quindi su QGIS 4.0 il plugin si carica e non fa nulla **in silenzio**.

### CR-6 — `TypeError` al caricamento su profilo nuovo

`QSettings().value('locale/userLocale')[0:2]` solleva `TypeError: 'NoneType' object is not subscriptable` quando la chiave non è impostata, cioè su un profilo QGIS appena creato. Verificato. Il plugin non si carica affatto.

### CR-7 — Difetti minori

- `SearchableComboBox` (righe 17–80) non è mai istanziato: 65 righe di codice morto.
- `main_action` viene creata ma mai aggiunta a un menu né a `self.actions`: resta orfana.
- `unload()` non ripristina i combo né disconnette i segnali.
- Lo stylesheet ha colori chiari fissi (`#f0f8f0`, bordo `#2E8B57`): illeggibile su tema scuro.
- `enhanceComboBox` restituisce `True` solo dentro `if line_edit:`, altrimenti `None`.
- Il placeholder è solo in italiano.

## 4. Design

### 4.1 Rilevamento event-driven, al posto del polling

Il `QTimer` a 500 ms e ogni uso di `allWidgets()` vengono eliminati. Al loro posto un event filter installato sull'istanza di applicazione che reagisce **solo** a `QEvent.Type.Show`; quando il widget mostrato ha `objectName() == "ModelerParametersDialog"`, l'enhancement viene rimandato con `QTimer.singleShot(0, ...)`.

Perché questo chiude CR-1:

- non enumeriamo mai liste globali di widget, quindi non incontriamo mai oggetti altrui a metà costruzione o già distrutti;
- il rinvio a `singleShot(0)` garantisce che il dialog sia **completamente costruito** prima che lo tocchiamo;
- reagiamo soltanto allo `Show` di un dialog che sappiamo identificare, quindi non giriamo dentro event loop annidati di dialog nativi.

Il punto cruciale è l'ordine degli eventi. Lo stack trace del crash mostra che la costruzione dei widget avviene in `setupUi`, cioè dentro `__init__`, **prima** che il dialog venga mostrato. Un `QEvent.Show` è quindi per costruzione posteriore al completamento di `__init__`: quando lo riceviamo, tutti i figli del dialog esistono già. Il rinvio con `singleShot(0)` aggiunge un margine per eventuali popolamenti differiti dei combo e ci sposta fuori dallo stack di consegna dell'evento, dove il dialog è ancora a metà del proprio `showEvent`.

Costo: il filtro ritorna immediatamente per ogni evento che non è `Show`, cioè un singolo confronto di interi.

### 4.2 Scoperta strutturale

Dentro *quel solo* dialog si cercano i `QgsProcessingModelerParameterWidget` e, in ciascuno, i `QComboBox` discendenti del suo `QStackedWidget`. Nessuna stringa localizzata, nessun match su titoli di finestra. Chiude la parte di CR-4 relativa al rilevamento.

La classe è importabile da `qgis.gui` su tutte le versioni supportate (2.6), quindi la ricerca usa `findChildren(QgsProcessingModelerParameterWidget)` e `isinstance()`, non un confronto su `type(w).__name__`. Un confronto sul nome sarebbe silenziosamente falsificabile da qualunque altra classe omonima e non verrebbe segnalato da alcuno strumento di analisi statica.

### 4.3 Criterio di selezione dei combo

Un combo viene migliorato se e solo se:

1. discende da un `QgsProcessingModelerParameterWidget`;
2. `count() >= SEARCH_MIN_ITEMS` (default 5; sotto questa soglia la tendina nativa è già adeguata);
3. `itemData(0)` è un riferimento a sorgente, cioè un'istanza di `str` oppure di `list`.

Il criterio 3 è una **lista chiusa di tipi ammessi**, non una lista di esclusioni: passa solo `str` o `list`, quindi `bool`, `int` e `None` sono esclusi per costruzione. Questo elimina, senza alcuna euristica sul testo, sia i combo booleani Sì/No (`itemData` `True`/`False`, cfr. 2.2) sia i combo di parametri enumerati, il cui `itemData` è l'indice intero dell'opzione.

La forma ad allowlist va preferita a un controllo per esclusione proprio perché in Python `bool` è sottoclasse di `int`: un `isinstance(data, int)` usato come esclusione catturerebbe anche i booleani solo per caso, e l'ordine dei controlli diventerebbe significativo. Con l'allowlist la questione non si pone.

L'esclusione degli enumerati è una scelta deliberata: l'ambito concordato sono i nomi di algoritmi e input, cioè le sorgenti. Se in futuro si volesse cercare anche fra le opzioni di un enumerato lungo, è sufficiente ampliare la lista dei tipi ammessi nel criterio 3, senza toccare il resto della logica.

Il criterio sostituisce integralmente `shouldEnhanceComboBox` e `analyzeParentContext`, chiudendo il resto di CR-4.

### 4.4 Un controller per combo

Si introduce `ComboSearchController(QObject)`, istanziato una volta per combo e **parentato al combo stesso**. Possiede il proprio `_updating`, `_last_query` e `QTimer` di debounce.

- Chiude CR-2 alla radice: non esiste più stato di ricerca condiviso.
- Chiude la parte di CR-1 relativa ai riferimenti penzolanti: essendo figlio Qt del combo, il controller viene distrutto insieme a esso, quindi non serve più alcun set di bookkeeping (`monitored_widgets`, `enhanced_combos` spariscono).

Interfaccia pubblica del controller: `attach()`, `detach()`. Dipendenze: il solo `QComboBox` che gli è stato passato.

### 4.5 Risoluzione sempre sul combo vivo

Il controller **non conserva alcuna cache**. La lista candidati viene riletta dal combo vivo a ogni passata di filtro, cioè a ogni scatto del debounce, e la selezione viene risolta con `findText()` sul combo vivo al momento della scelta.

Questa è la formulazione più semplice possibile, ed è anche la più corretta:

- non esiste uno snapshot che possa diventare obsoleto, quindi CR-3 è chiuso per costruzione;
- copre gratuitamente il caso in cui QGIS **sostituisca** l'intero modello del combo, che spezzerebbe qualunque sottoscrizione a segnali del modello precedente;
- non dipende da alcun segnale di "popup in apertura". Vale la pena esplicitarlo: `QComboBox` **non** espone `popupAboutToBeShown` (cfr. 2.6), quindi un design che vi si appoggiasse non sarebbe implementabile senza sottoclassare il combo — cosa preclusa, dato che i combo appartengono a QGIS.

Il costo è trascurabile: un combo del modeler contiene al massimo qualche decina di voci, rilette non più di una volta ogni 300 ms di debounce.

Il valore effettivo resta quello che QGIS legge, `currentData()`. Nessun `index()` su liste memorizzate.

Resta un solo scoperto noto, accettato: se il modello cambia mentre il popup è già aperto e l'utente non digita nulla, il popup mostra voci obsolete fino al tasto successivo. Sottoscrivere `rowsInserted`/`rowsRemoved`/`modelReset` per coprirlo introdurrebbe la riconnessione alla sostituzione del modello, complessità non giustificata da questo caso limite.

### 4.6 Nessun testo divergente

Su `editingFinished` e alla perdita del focus, se il testo del line edit non corrisponde a nessuna voce esistente, viene riportato a `combo.currentText()`. Dato 2.3, `currentData()` conserva già il valore valido: il ripristino del testo rende il widget onesto verso l'utente invece di mostrargli una stringa che non corrisponde a ciò che il modello userà.

### 4.7 Compatibilità Qt5 / Qt6

- Tutti gli enum in forma scoped (2.4).
- `from qgis.PyQt import sip` (2.5).
- Nessun branching di versione, nessun `try/except ImportError` sugli enum.
- `qgisMinimumVersion` resta `3.34`.

Chiude CR-5.

### 4.8 Gestione degli errori

I blocchi `except Exception: pass` / `return False` vengono rimossi. Gli errori inattesi vengono registrati in `QgsMessageLog` con il tag del plugin. Sono esattamente questi blocchi ad aver reso invisibile la rottura su Qt6 (CR-5): un guasto silenzioso è peggio di un guasto rumoroso.

Difesa a più livelli per l'accesso ai widget, applicata solo dove serve davvero:

1. `sip.isdeleted()` come pre-controllo economico;
2. `try/except RuntimeError` attorno all'accesso ai widget, che è ciò che PyQt solleva sui wrapper distrutti;
3. connessione a `destroyed` per rilasciare i riferimenti in modo deterministico.

### 4.9 Pulizia e presentazione

- `unload()` invoca `detach()` su ogni controller: `setEditable(False)` (2.3), rimozione del completer, azzeramento dello stylesheet, disconnessione dei segnali.
- Rimozione dell'event filter dall'applicazione.
- Stylesheet derivato dalla palette corrente invece dei colori chiari fissi, così da restare leggibile su tema scuro.
- Rimozione di `SearchableComboBox` e della `main_action` orfana.
- Correzione di `locale/userLocale` con un default sicuro (CR-6).
- Placeholder passato da `tr()`.

Chiude CR-6 e CR-7.

## 5. Flusso dei dati

```
QEvent.Show su widget
  └─> objectName() == "ModelerParametersDialog"?
        └─> QTimer.singleShot(0)                      [dialog ora costruito]
              └─> per ogni QgsProcessingModelerParameterWidget del dialog
                    └─> per ogni QComboBox sotto il suo QStackedWidget
                          └─> criterio 4.3 soddisfatto?
                                └─> ComboSearchController(combo).attach()

digitazione dell'utente
  └─> debounce per-combo (QTimer del controller)
        └─> ricostruzione candidati dal combo VIVO
              └─> filtro AND su tutti i termini, case-insensitive
                    └─> popup del completer

selezione dell'utente
  └─> findText() sul combo VIVO -> setCurrentIndex()
        └─> QGIS legge currentData()                  [valore corretto per costruzione]

focus-out con testo non corrispondente
  └─> line edit riportato a combo.currentText()

chiusura del dialog
  └─> Qt distrugge i combo -> distrugge i controller figli
```

## 6. Strategia di test

Il repository non ha test. Si aggiunge un harness headless (`QT_QPA_PLATFORM=offscreen`) che costruisce un vero `QgsProcessingModelAlgorithm` con più input e più algoritmi figli, apre un vero `ModelerParametersDialog` e verifica il comportamento del plugin.

Casi di test, ciascuno legato alla causa radice che presidia:

| Test | Presidia |
|---|---|
| Il codice non contiene `allWidgets()` né timer ricorrenti | CR-1 |
| Aprire e chiudere N dialog non lascia riferimenti vivi e non solleva | CR-1 |
| Due combo migliorati filtrano **entrambi** in modo indipendente | CR-2 |
| La stessa query digitata in un secondo combo filtra comunque | CR-2 |
| Dopo un ripopolamento del combo, selezionare una voce dà il `currentData()` corretto | CR-3 |
| I combo sorgente vengono agganciati; quelli booleani Sì/No no | CR-4 |
| Un combo di enumerato con almeno 5 opzioni non viene agganciato | CR-4, 4.3 |
| Etichette con virgolette tipografiche vengono riconosciute | CR-4, 2.8 |
| L'enhancement avviene con locale non italiana | CR-4 |
| La suite passa su PyQt5 **e** PyQt6 | CR-5 |
| `locale/userLocale` assente non impedisce il caricamento | CR-6 |
| `unload()` riporta `isEditable()` a `False` e il testo originale | CR-7 |

La suite va eseguita contro QGIS 3.40.2 (Qt5) e QGIS 4.0.0 (Qt6).

## 7. Fuori ambito

- La ricerca nell'albero degli algoritmi del pannello di sinistra: ha già una casella nativa, ed è stato confermato che non è oggetto di questo lavoro.
- Il passaggio all'opzione non distruttiva (filtro sul popup senza rendere il combo editabile), valutata e scartata in favore dell'approccio editable + completer.
- Traduzioni: si predispone `tr()` ma non si aggiungono file `.qm`.
- Le tre modifiche di whitespace non committate nel working tree restano tali: sono intenzionali.

## 8. Rischi residui

- L'approccio scelto mantiene `setEditable(True)`, cioè una mutazione di un widget di QGIS. È reversibile (2.3) e verificata innocua sul valore, ma resta più invasiva dell'alternativa non distruttiva. Se in futuro QGIS cambiasse la struttura interna di `QgsProcessingModelerParameterWidget`, il criterio 4.3 andrebbe rivisto.
- L'event filter a livello di applicazione riceve tutti gli eventi. Il costo è un confronto di interi per evento, ma va evitato di far crescere quel percorso.
- `SEARCH_MIN_ITEMS = 5` è una scelta di prodotto, non tecnica: è una costante isolata per poterla cambiare senza toccare la logica.
