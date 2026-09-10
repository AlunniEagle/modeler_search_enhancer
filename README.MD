# 🔍 Modeler Search Enhancer Plugin

**Advanced search functionality for QGIS Processing Modeler algorithm inputs and outputs**

![QGIS Plugin](https://img.shields.io/badge/QGIS-Plugin-green)
![Version](https://img.shields.io/badge/version-2.0-blue)
![License](https://img.shields.io/badge/license-GPL--2.0-orange)

## 📖 Overview

The **Modeler Search Enhancer** plugin provides intelligent search capabilities for QGIS Processing Modeler ComboBox fields. It automatically detects and enhances algorithm input/output selection ComboBoxes with real-time filtering functionality, making it easier to find and select the outputs you need when building complex models.

### 🎯 Key Features

- **🔍 Smart Search** - Adds intelligent search capabilities to Modeler input/output ComboBoxes
- **⚡ Real-time Filtering** - Filters results as you type
- **🎯 Intelligent Detection** - Only enhances relevant ComboBoxes (algorithm inputs/outputs)
- **🚫 Non-intrusive** - Ignores configuration and dependency ComboBoxes
- **🔤 Case-insensitive** - Search works regardless of capitalization
- **📝 Multi-term Search** - Search for multiple words simultaneously
- **🎨 Visual Indicators** - Enhanced ComboBoxes have a highlighted border and search placeholders

## 🚀 Installation

### From QGIS Plugin Repository
1. Open QGIS
2. Go to **Plugins** → **Manage and Install Plugins**
3. Search for "Modeler Search Enhancer"
4. Click **Install Plugin**

### Manual Installation
1. Download the plugin files
2. Extract to your QGIS plugins directory:
   - **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
3. Restart QGIS
4. Enable the plugin in **Plugins** → **Manage and Install Plugins** → **Installed**

## 📋 Usage

### Quick Start

1. **Open the Processing Modeler**
   ```
   Processing → Graphical Modeler
   ```

2. **Create or open a model** with multiple algorithms

3. **Add a new algorithm** to your model

4. **Click on any input ComboBox** that contains algorithm outputs

5. **Start typing** to filter the available options!

### 🔍 Search Examples

| Search Query | Results |
|--------------|---------|
| `buffer` | All outputs containing "buffer" |
| `clip merge` | Outputs containing both "clip" AND "merge" |
| `estrai` | All Italian outputs containing "estrai" |
| `result operation` | Outputs with both "result" and "operation" |

### Visual Indicators

- **🔲 Highlighted Border:** Indicates a ComboBox has been enhanced with search
- **🔍 Placeholder Text:** Shows "🔍 Type to filter..." in enhanced ComboBoxes  
- **🌗 Theme Aware:** The highlight follows your QGIS colour theme, so it stays readable in dark mode

## ⚙️ How It Works

The plugin operates automatically in the background:

1. **🔍 Detects** - Activates as soon as an algorithm configuration window opens in the Modeler
2. **🧠 Analyzes** - Identifies ComboBoxes that contain algorithm outputs
3. **⚡ Enhances** - Adds search functionality only to relevant ComboBoxes
4. **🎯 Filters** - Provides real-time filtering based on your input

### Intelligent Detection

Detection is structural rather than text-based, so it behaves the same in every interface language:

#### ✅ **Enhanced ComboBoxes:**
- Fields listing the model's own inputs
- Fields listing outputs of upstream algorithms
- Only when they hold at least five entries

#### ❌ **Ignored ComboBoxes:**
- Boolean dropdowns (yes/no)
- Enumerated parameter dropdowns
- Anything with fewer than five entries

## 🛠️ Technical Details

### System Requirements
- **QGIS:** 3.34 or higher, including the 4.x series built on Qt6
- **Python:** 3.6+
- **Qt:** 5.15+ or 6.x

### Architecture
- **Language:** Python
- **Framework:** PyQt5/6
- **Integration:** QGIS Plugin API
- **Detection:** Structural widget inspection, independent of interface language
- **Search:** QCompleter with custom filtering

## 🎨 Search Capabilities

### Advanced Features

- **Partial Matching:** Search finds text anywhere in the algorithm name
- **Multi-word Search:** Space-separated terms must all be present
- **Case Insensitive:** "BUFFER", "buffer", and "Buffer" all work the same
- **Auto-completion:** Popup shows filtered results as you type
- **Smart Selection:** Click any result to select it
- **Performance Optimized:** Minimal impact on QGIS performance

### Filter Logic

```python
# Example: Search for "buffer clip"
search_terms = ["buffer", "clip"]
for algorithm_output in outputs:
    if all(term in algorithm_output.lower() for term in search_terms):
        # Include in filtered results
```

## 🐛 Troubleshooting

### Common Issues

**❓ Search doesn't appear**
- ✅ Ensure you're in a Modeler window with algorithm inputs/outputs
- ✅ Check that the ComboBox contains algorithm outputs (not configuration options)
- ✅ Restart QGIS if the plugin seems unresponsive

**❓ Plugin not in menu**
- ✅ Check if plugin is enabled in Plugin Manager
- ✅ Verify installation directory is correct
- ✅ Check QGIS Python console for error messages

**❓ Search is slow**
- ✅ Normal behavior with very large models (1000+ algorithms)
- ✅ Try more specific search terms to narrow results
- ✅ Consider breaking large models into smaller sub-models

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/AlunniEagle/modeler-search-enhancer.git
   cd modeler-search-enhancer
   ```

2. **Create development environment**
   ```bash
   # Link to QGIS plugins directory
   ln -s $(pwd) ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/modeler_search_enhancer
   ```

3. **Test the plugin**
   - Open QGIS
   - Enable Plugin Reloader plugin for development
   - Test changes in Processing Modeler

### Contribution Process

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

## 📄 License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as by the Free Software Foundation, either version 2 of the License, or (at your option) any later version. <br><br>This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details. <br><br>You should have received a copy of the GNU General Public License along with this program. - see the [LICENSE](LICENSE) file for details.

### License Summary
- ✅ **Use** - Commercial and private use allowed
- ✅ **Modify** - Modification and distribution allowed
- ✅ **Distribute** - Distribution allowed
- ❗ **Disclose source** - Source code must be made available
- ❗ **License and copyright notice** - Must include license and copyright notice
- ❗ **Same license** - Derivative works must use the same license

## 📞 Support & Contact

### Getting Help

- **📖 Documentation:** Built-in Help (Plugins → Modeler Search Enhancer → Help)
- **🐛 Issues:** [GitHub Issues](https://github.com/AlunniEagle/modeler_search_enhancer/issues)
- **💬 Discussions:** [GitHub Discussions](https://github.com/AlunniEagle/modeler_search_enhancer/wiki)
- **📧 Email:** gis@eagleprojects.it

### Reporting Bugs

When reporting bugs, please include:
- **QGIS version** and operating system
- **Plugin version**
- **Steps to reproduce** the issue
- **Expected vs actual behavior**
- **Screenshots** if applicable
- **Error messages** from QGIS log

---

<div align="center">

**Made with ❤️ for the QGIS Community**

[⭐ Star this repository](https://github.com/AlunniEagle/modeler-search-enhancer) if you find it useful!

</div>