# KiCad Project Initialization Plugin

A vibe-coded KiCad Action Plugin for creating new projects from a given project template from KiCad PCBNew.

## Overview

This plugin is based on the [`init-project.sh`](https://github.com/Kampi/KiCad/tree/master/Scripts) script and offers two main functions:

1. **Create New Project** - Copies the `__Project__` from [KiCad Library](https://github.com/Kampi/KiCad) repository template and initializes all files
2. **Update Existing Project** - Updates metadata of an already opened project

![Create Project](docs/images/Create%20Project.jpg)

![New Project from Template](docs/images/New%20Project%20from%20Template.jpg)

## Features

- ✅ **Complete project creation from template** (like the original script)
- ✅ PCB template selection (various manufacturers, thicknesses, layers)
- ✅ Automatic file renaming (Template → BoardName)
- ✅ Graphical user interface for entering project data
- ✅ Automatic update of `.kicad_pro` file (text_variables)
- ✅ Update of Board Title Block
- ✅ KiBot configuration is automatically adjusted
- ✅ Support for all important metadata fields
- ✅ Validation of required fields
- ✅ Automatic date generation
- ✅ License selection and download (11 open-source licenses)

## Two Modes

### 1. Create New Project

- Copies the complete `__Project__` template structure
- Selects PCB template (e.g., "pcbway_1.6mm_2-layer")
- Renames all files (Template → BoardName)
- Updates all configuration files
- Creates complete project structure with:
  - Hardware (KiCad files)
  - Firmware
  - 3D-Print
  - CAD
  - GitHub Workflows
  - KiBot configuration

### 2. Update Existing Project

- Updates only metadata of an opened project
- Does not change file structure
- Quick update of Project Name, Designer, Company, etc.

## Updated Fields

### In the .kicad_pro file (text_variables)

- `PROJECT_NAME` - Name of the overall project
- `BOARD_NAME` - Name of the PCB/board
- `DESIGNER` - Designer name
- `COMPANY` - Company name (optional)
- `RELEASE_DATE` - Current date (dd-MMM-yyyy format)
- `RELEASE_DATE_NUM` - Current date (yyyy-MM-dd format)
- `REVISION` - Version number (default: 1.0.0)

### In the Board Title Block

- Title (set to BOARD_NAME)
- Company
- Revision
- Date
- Comment1 (Description)

## Installation

### Automatic Installation (KiCad 7.0+)

1. Open KiCad PCBNew
2. Go to **Tools** → **External Plugins** → **Open Plugin Directory**
3. Copy the complete `kicad_project_init_plugin` folder to the plugins directory
4. Restart KiCad or go to **Tools** → **External Plugins** → **Refresh Plugins**

### Manual Installation

The plugin directory is located in different places depending on the operating system:

**Windows:**

```text
%APPDATA%\kicad\...\scripting\plugins\
```

**Linux:**

```text
~/.kicad/scripting/plugins/
```

**macOS:**

```text
~/Library/Application Support/kicad/scripting/plugins/
```

Copy the entire `kicad_project_init_plugin` folder to one of these directories.

## Usage

### Mode 1: Create New Project

1. Open KiCad PCBNew (no project needs to be loaded)
2. Click on the plugin button in the toolbar or go to **Tools** → **External Plugins** → **Initialize Project Metadata**
3. Select **"Create New Project from Template"**
4. Fill in the required fields:
   - **Project Location** - Where the project should be created
   - **Project Name** * (required) - Name of the project folder
   - **Board Name** * (required) - Name of the PCB/circuit
   - **Designer** * (required)
   - **Company** (optional)
   - **Revision** (default: 1.0.0)
   - **PCB Template** * - Select manufacturer/thickness/layers
   - **License** - Select project license (MIT, Apache 2.0, GPL 3.0, etc. or None)
   - **Description** (optional)
5. Click **Create Project**
6. The complete project will be created and can be opened in KiCad

### Mode 2: Update Existing Project

1. Open a KiCad project in PCBNew
2. **Important:** Save the board file first (the plugin needs a saved file path)
3. Click on the plugin button or go to **Tools** → **External Plugins** → **Initialize Project Metadata**
4. Select **"Update Existing Project"**
5. Fill in the required fields (Board Name will be pre-filled automatically)
6. Click **Apply**
7. The metadata will be updated

## Template Requirements

The plugin includes the `__Project__` template directly in the plugin folder:

```text
kicad_project_init_plugin/
├── __init__.py
├── kicad_project_init.py
├── metadata.json
├── icon.png
├── README.md
└── __Project__/          ← Template is included here!
    ├── hardware/
    │   ├── Template.kicad_pro
    │   ├── Template.kicad_sch
    │   ├── Template.kicad_pcb
    │   ├── Template - pcbway_1.6mm_2-layer.kicad_pcb
    │   ├── Template - pcbway_1.6mm_4-layer.kicad_pcb
    │   └── kibot_yaml/
    ├── firmware/
    ├── 3d-print/
    ├── cad/
    └── .github/workflows/
```

The plugin is thus completely portable - no separate template setup required!

## Requirements

- KiCad 7.0 or newer (>9.0 recommended)
- Python 3.x (included with KiCad)
- wxPython (included with KiCad)

## Differences from Original Script

The plugin now offers the **complete functionality** of template-based project creation!

### Implemented Features (like in the script)

- ✅ Create new project from template
- ✅ PCB template selection
- ✅ Automatic file renaming
- ✅ .kicad_pro metadata update
- ✅ Schematic title update
- ✅ KiBot configuration update
- ✅ Project structure creation
- ✅ License selection and download

### Not Implemented Features (remain in the script)

The following features are deliberately **not** included in the plugin, as they are better suited outside of KiCad:

- ❌ Git initialization and first commits
- ❌ GitHub workflow configuration (master_branch, etc.)
- ❌ GitHub remote configuration
- ❌ README.md generation
- ❌ AsciiDoc documentation
- ❌ Commit message template

### When Updating Existing Projects

1. **"No board loaded!"** - Open a PCB file first
2. **"Please save the board first!"** - Save the board file before running the plugin
3. **"Project Name is required!"** - Fill in all required fields
4. **"Failed to update project file!"** - Check write permissions for the `.kicad_pro` file

## Development

### Plugin Structure

The plugin follows the KiCad ActionPlugin API:

```python
class KiCadProjectInit(pcbnew.ActionPlugin):
    def defaults(self):
        # Plugin metadata

    def Run(self):
        # Plugin execution
```

### Debugging

Enable Python scripting output in KiCad:

1. Open the Scripting Console in PCBNew (**Tools** → **Scripting Console**)
2. Error messages will be displayed there

## Contributing

Suggestions for improvements and bug reports are welcome! Create an issue or pull request on GitHub.

## License

GPL-3.0 - See LICENSE file

## Maintainer

**Daniel Kampert**  
📧 [DanielKampert@kampis-elektroecke.de](mailto:DanielKampert@kampis-elektroecke.de)  
🌐 [www.kampis-elektroecke.de](https://www.kampis-elektroecke.de)

## Further Links

- [KiCad Plugin Documentation](https://dev-docs.kicad.org/en/python/pcbnew/)
- [Original init-project.sh Script](../../Scripts/init-project.sh)
- [KiCad Forum - Plugin Development](https://forum.kicad.info/)
