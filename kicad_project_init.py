"""
KiCad Project Initialization Plugin

This plugin allows you to initialize a KiCad project with customizable metadata
directly from within KiCad PCBNew.

The steps are the same as in the init scripts of the KiCad library
(Scripts/init-project.sh and Scripts/init-project.ps1). Keep them in sync.

Author: Daniel Kampert
"""

import pcbnew
import wx
import os
import json
import datetime
import shutil
import re
import urllib.request
import urllib.error
from pathlib import Path

def _parse_git_url(url):
    """Parse GitHub user and repository name from a GitHub URL.
    Returns (git_user, git_repo) or ('', '') if the URL cannot be parsed.
    """
    match = re.search(r'github\.com[:/]([^/]+)/([^/\.]+)', url or '')
    if match:
        return match.group(1), match.group(2).removesuffix('.git')
    return '', ''

def _make_anchor(text):
    """Convert a string to a lowercase Markdown heading anchor."""
    return re.sub(r'[^a-z0-9-]', '', text.lower().replace(' ', '-'))

def _make_identifier(text):
    """Convert a repository name to a lowercase C identifier ('my-repo' -> 'my_repo')."""
    return text.lower().replace('-', '_')

# Project types of the template, same order and meaning as in init-project.sh / init-project.ps1.
# 'firmware_profile' is the directory in __Project__/firmware that is kept.
PROJECT_TYPES = [
    {"name": "Hardware (KiCad project)",
     "has_hardware": True, "firmware_profile": "blank"},
    {"name": "Hardware with PlatformIO firmware (ESP32, ESP-IDF)",
     "has_hardware": True, "firmware_profile": "platformio"},
    {"name": "PlatformIO firmware (ESP32, ESP-IDF)",
     "has_hardware": False, "firmware_profile": "platformio"},
    {"name": "ESP-IDF component",
     "has_hardware": False, "firmware_profile": "esp-idf-component"},
]

COMPONENT_PROFILE = "esp-idf-component"

class ProjectModeDialog(wx.Dialog):
    """Dialog to choose between creating new project or updating existing"""

    def __init__(self, parent):
        super().__init__(parent, title="Project Initialization Mode", 
                        style=wx.DEFAULT_DIALOG_STYLE)

        self.mode = None
        self.init_ui()
        self.Centre()

    def init_ui(self):
        """Initialize the user interface"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(self, label="Choose Project Initialization Mode")
        title_font = title.GetFont()
        title_font.PointSize += 2
        title_font = title_font.Bold()
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        # Options
        self.new_project_btn = wx.Button(self, label="Create New Project from Template", 
                                         size=(300, 50))
        self.new_project_btn.Bind(wx.EVT_BUTTON, self.on_new_project)
        main_sizer.Add(self.new_project_btn, 0, wx.ALL | wx.CENTER, 10)

        new_desc = wx.StaticText(self, 
                                label="Creates a complete new project structure\n"
                                      "from the template in __Project__")
        new_desc.SetForegroundColour(wx.Colour(100, 100, 100))
        main_sizer.Add(new_desc, 0, wx.LEFT | wx.RIGHT | wx.CENTER, 10)

        main_sizer.AddSpacer(20)

        self.update_project_btn = wx.Button(self, label="Update Existing Project", 
                                           size=(300, 50))
        self.update_project_btn.Bind(wx.EVT_BUTTON, self.on_update_project)
        main_sizer.Add(self.update_project_btn, 0, wx.ALL | wx.CENTER, 10)

        update_desc = wx.StaticText(self, 
                                    label="Updates metadata of the currently\n"
                                          "loaded project")
        update_desc.SetForegroundColour(wx.Colour(100, 100, 100))
        main_sizer.Add(update_desc, 0, wx.LEFT | wx.RIGHT | wx.CENTER, 10)

        main_sizer.AddSpacer(10)

        # Cancel button
        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        main_sizer.Add(cancel_btn, 0, wx.ALL | wx.CENTER, 10)

        self.SetSizer(main_sizer)
        self.Fit()

    def on_new_project(self, event):
        """Handle new project button"""
        self.mode = "new"
        self.EndModal(wx.ID_OK)

    def on_update_project(self, event):
        """Handle update project button"""
        self.mode = "update"
        self.EndModal(wx.ID_OK)

class NewProjectDialog(wx.Dialog):
    """Dialog for creating a new project from template"""

    def __init__(self, parent, template_path):
        super().__init__(parent, title="Create New KiCad Project", 
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.template_path = Path(template_path)
        self.pcb_templates = []
        self.init_ui()
        self.SetMinSize((600, 700))
        self.Centre()

    def init_ui(self):
        """Initialize the user interface"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create input fields
        grid_sizer = wx.FlexGridSizer(0, 2, 10, 10)
        grid_sizer.AddGrowableCol(1, 1)

        # Project Location
        grid_sizer.Add(wx.StaticText(self, label="Project Location:*"), 
                      0, wx.ALIGN_CENTER_VERTICAL)
        location_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.project_location = wx.TextCtrl(self, value=str(Path.home()))
        location_sizer.Add(self.project_location, 1, wx.EXPAND)
        browse_btn = wx.Button(self, label="Browse...", size=(80, -1))
        browse_btn.Bind(wx.EVT_BUTTON, self.on_browse)
        location_sizer.Add(browse_btn, 0, wx.LEFT, 5)
        grid_sizer.Add(location_sizer, 1, wx.EXPAND)

        # Project Name
        grid_sizer.Add(wx.StaticText(self, label="Project Name:*"), 
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.project_name = wx.TextCtrl(self)
        grid_sizer.Add(self.project_name, 1, wx.EXPAND)

        # Project Type
        grid_sizer.Add(wx.StaticText(self, label="Project Type:*"),
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.project_type = wx.Choice(self, choices=[t["name"] for t in PROJECT_TYPES])
        self.project_type.SetSelection(0)
        self.project_type.Bind(wx.EVT_CHOICE, self.on_project_type)
        grid_sizer.Add(self.project_type, 1, wx.EXPAND)

        # Board Name
        self.board_name_label = wx.StaticText(self, label="Board Name:*")
        grid_sizer.Add(self.board_name_label, 0, wx.ALIGN_CENTER_VERTICAL)
        self.board_name = wx.TextCtrl(self)
        grid_sizer.Add(self.board_name, 1, wx.EXPAND)

        # Designer
        grid_sizer.Add(wx.StaticText(self, label="Designer:*"), 
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.designer = wx.TextCtrl(self)
        grid_sizer.Add(self.designer, 1, wx.EXPAND)

        # Email
        grid_sizer.Add(wx.StaticText(self, label="Email:*"),
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.email = wx.TextCtrl(self)
        grid_sizer.Add(self.email, 1, wx.EXPAND)

        # GitHub URL
        grid_sizer.Add(wx.StaticText(self, label="GitHub URL:*"),
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.git_url = wx.TextCtrl(self, value="https://github.com/")
        grid_sizer.Add(self.git_url, 1, wx.EXPAND)

        # Master Branch
        grid_sizer.Add(wx.StaticText(self, label="Main Branch:"),
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.master_branch = wx.TextCtrl(self, value="main")
        grid_sizer.Add(self.master_branch, 1, wx.EXPAND)

        # Company
        grid_sizer.Add(wx.StaticText(self, label="Company:"), 
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.company = wx.TextCtrl(self)
        grid_sizer.Add(self.company, 1, wx.EXPAND)

        # Revision
        grid_sizer.Add(wx.StaticText(self, label="Revision:"), 
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.revision = wx.TextCtrl(self, value="1.0.0")
        grid_sizer.Add(self.revision, 1, wx.EXPAND)

        # PCB Template (project types with hardware only)
        grid_sizer.Add(wx.StaticText(self, label="PCB Template:*"), 
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.pcb_templates = self.scan_pcb_templates()
        pcb_choices = [f"{t['manufacturer']} - {t['thickness']} - {t['layers']} layers" 
                      for t in self.pcb_templates]
        if not pcb_choices:
            pcb_choices = ["No templates found"]
        self.pcb_template = wx.Choice(self, choices=pcb_choices)
        if self.pcb_templates:
            self.pcb_template.SetSelection(0)
        grid_sizer.Add(self.pcb_template, 1, wx.EXPAND)

        # License
        grid_sizer.Add(wx.StaticText(self, label="License:"), 
                      0, wx.ALIGN_CENTER_VERTICAL)
        license_choices = [
            "MIT",
            "Apache 2.0",
            "GPL 3.0",
            "LGPL 3.0",
            "BSD 2-Clause",
            "BSD 3-Clause",
            "MPL 2.0",
            "AGPL 3.0",
            "Unlicense",
            "CC0 1.0",
            "None"
        ]
        self.license = wx.Choice(self, choices=license_choices)
        self.license.SetSelection(0)  # Default to MIT
        grid_sizer.Add(self.license, 1, wx.EXPAND)

        # Description
        grid_sizer.Add(wx.StaticText(self, label="Description:"), 
                      0, wx.ALIGN_TOP | wx.TOP, border=5)
        self.description = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 80))
        grid_sizer.Add(self.description, 1, wx.EXPAND)

        main_sizer.Add(grid_sizer, 0, wx.ALL | wx.EXPAND, 10)

        # Info text
        info_text = wx.StaticText(self, 
                                 label="* Required fields\n\n"
                                       "This will create a complete new project structure "
                                       "in the selected location.")
        info_text.SetForegroundColour(wx.Colour(100, 100, 100))
        main_sizer.Add(info_text, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Buttons
        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(self, wx.ID_OK, "Create Project")
        cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizer(main_sizer)
        self.Fit()

    def get_project_type(self):
        """Return the selected entry of PROJECT_TYPES"""
        selection = self.project_type.GetSelection()
        if selection < 0 or selection >= len(PROJECT_TYPES):
            selection = 0
        return PROJECT_TYPES[selection]

    def on_project_type(self, event):
        """The PCB template and the board name are only needed for project types with hardware"""
        has_hardware = self.get_project_type()["has_hardware"]
        self.pcb_template.Enable(has_hardware)
        self.board_name_label.SetLabel("Board Name:*" if has_hardware else "Board Name:")

    def on_browse(self, event):
        """Browse for project location"""
        dlg = wx.DirDialog(self, "Choose project location",
                          self.project_location.GetValue(),
                          style=wx.DD_DEFAULT_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            self.project_location.SetValue(dlg.GetPath())
        dlg.Destroy()

    def scan_pcb_templates(self):
        """Scan for available PCB templates"""
        templates = []
        hardware_path = self.template_path / "hardware"

        if not hardware_path.exists():
            return templates

        # Pattern: Template - manufacturer_thickness_x-layer.kicad_pcb
        pattern = re.compile(r'^Template - ([^_]+)_([^_]+)_(\d+)-layer\.kicad_pcb$')

        for file in hardware_path.glob("Template - *.kicad_pcb"):
            match = pattern.match(file.name)
            if match:
                templates.append({
                    'filename': file.name,
                    'manufacturer': match.group(1),
                    'thickness': match.group(2),
                    'layers': match.group(3)
                })

        return templates

    def get_values(self):
        """Return the entered values as a dictionary"""
        project_type = self.get_project_type()

        selected_template = None
        if (project_type["has_hardware"] and self.pcb_templates
                and self.pcb_template.GetSelection() >= 0):
            selected_template = self.pcb_templates[self.pcb_template.GetSelection()]

        license_selection = self.license.GetSelection()
        license_info = self.get_license_info(license_selection)

        git_url = self.git_url.GetValue().strip().rstrip('/')
        git_user, git_repo = _parse_git_url(git_url)

        return {
            'project_location': self.project_location.GetValue(),
            'project_name': self.project_name.GetValue(),
            'project_type': project_type,
            # Like in the init scripts the board name defaults to the project name
            'board_name': self.board_name.GetValue() or self.project_name.GetValue(),
            'designer': self.designer.GetValue(),
            'email': self.email.GetValue().strip(),
            'company': self.company.GetValue(),
            'revision': self.revision.GetValue() or "1.0.0",
            'description': self.description.GetValue(),
            'git_url': git_url,
            'git_user': git_user,
            'git_repo': git_repo,
            'master_branch': self.master_branch.GetValue().strip() or "main",
            'pcb_template': selected_template,
            'license': license_info
        }

    def get_license_info(self, selection):
        """Get license information based on selection"""
        license_map = {
            0:  {"name": "MIT",         "key": "mit",          "badge": "MIT-yellow"},
            1:  {"name": "Apache 2.0",  "key": "apache-2-0",   "badge": "Apache%202.0-blue"},
            2:  {"name": "GPL 3.0",     "key": "gpl-3-0",      "badge": "GPL%203.0-blue"},
            3:  {"name": "LGPL 3.0",    "key": "lgpl-3-0",     "badge": "LGPL%203.0-blue"},
            4:  {"name": "BSD 2-Clause","key": "bsd-2-clause",  "badge": "BSD%202--Clause-orange"},
            5:  {"name": "BSD 3-Clause","key": "bsd-3-clause",  "badge": "BSD%203--Clause-orange"},
            6:  {"name": "MPL 2.0",     "key": "mpl-2-0",      "badge": "MPL%202.0-brightgreen"},
            7:  {"name": "AGPL 3.0",    "key": "agpl-3-0",     "badge": "AGPL%203.0-blue"},
            8:  {"name": "Unlicense",   "key": "unlicense",    "badge": "Unlicense-blue"},
            9:  {"name": "CC0 1.0",     "key": "cc0-1-0",      "badge": "CC0%201.0-lightgrey"},
            10: {"name": "None",        "key": "none",         "badge": ""}
        }
        return license_map.get(selection, license_map[10])

    def validate_inputs(self):
        """Validate required inputs"""
        if not self.project_location.GetValue():
            wx.MessageBox("Project Location is required!", "Validation Error", 
                         wx.OK | wx.ICON_ERROR)
            return False
        if not self.project_name.GetValue():
            wx.MessageBox("Project Name is required!", "Validation Error", 
                         wx.OK | wx.ICON_ERROR)
            return False
        has_hardware = self.get_project_type()["has_hardware"]
        if has_hardware and not self.board_name.GetValue():
            wx.MessageBox("Board Name is required!", "Validation Error", 
                         wx.OK | wx.ICON_ERROR)
            return False
        if not self.designer.GetValue():
            wx.MessageBox("Designer is required!", "Validation Error", 
                         wx.OK | wx.ICON_ERROR)
            return False
        if not self.email.GetValue().strip():
            wx.MessageBox("Email is required!", "Validation Error",
                         wx.OK | wx.ICON_ERROR)
            return False
        git_url = self.git_url.GetValue().strip()
        if not git_url or 'github.com' not in git_url:
            wx.MessageBox("A valid GitHub URL is required!\n"
                         "Example: https://github.com/user/repo",
                         "Validation Error", wx.OK | wx.ICON_ERROR)
            return False
        if not _parse_git_url(git_url)[0]:
            wx.MessageBox("Could not parse username and repository from URL.\n"
                         "Expected format: https://github.com/user/repo",
                         "Validation Error", wx.OK | wx.ICON_ERROR)
            return False
        if has_hardware and not self.pcb_templates:
            wx.MessageBox("No PCB templates found in template directory!", "Error", 
                         wx.OK | wx.ICON_ERROR)
            return False
        profile = self.template_path / "firmware" / self.get_project_type()["firmware_profile"]
        if not profile.is_dir():
            wx.MessageBox(f"Firmware profile not found in template directory:\n{profile}", "Error",
                         wx.OK | wx.ICON_ERROR)
            return False
        return True

class ProjectInitDialog(wx.Dialog):
    """Dialog for collecting project initialization parameters"""

    def __init__(self, parent):
        super().__init__(parent, title="Initialize KiCad Project", 
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.init_ui()
        self.SetMinSize((500, 600))
        self.Centre()

    def init_ui(self):
        """Initialize the user interface"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create input fields
        grid_sizer = wx.FlexGridSizer(10, 2, 10, 10)
        grid_sizer.AddGrowableCol(1, 1)

        # Project Name
        grid_sizer.Add(wx.StaticText(self, label="Project Name:*"), 
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.project_name = wx.TextCtrl(self)
        grid_sizer.Add(self.project_name, 1, wx.EXPAND)

        # Board Name
        grid_sizer.Add(wx.StaticText(self, label="Board Name:*"), 
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.board_name = wx.TextCtrl(self)
        grid_sizer.Add(self.board_name, 1, wx.EXPAND)

        # Designer
        grid_sizer.Add(wx.StaticText(self, label="Designer:*"), 
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.designer = wx.TextCtrl(self)
        grid_sizer.Add(self.designer, 1, wx.EXPAND)

        # Email
        grid_sizer.Add(wx.StaticText(self, label="Email:*"),
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.email = wx.TextCtrl(self)
        grid_sizer.Add(self.email, 1, wx.EXPAND)

        # GitHub URL
        grid_sizer.Add(wx.StaticText(self, label="GitHub URL:*"),
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.git_url = wx.TextCtrl(self, value="https://github.com/")
        grid_sizer.Add(self.git_url, 1, wx.EXPAND)

        # Master Branch
        grid_sizer.Add(wx.StaticText(self, label="Main Branch:"),
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.master_branch = wx.TextCtrl(self, value="main")
        grid_sizer.Add(self.master_branch, 1, wx.EXPAND)

        # Company
        grid_sizer.Add(wx.StaticText(self, label="Company:"), 
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.company = wx.TextCtrl(self)
        grid_sizer.Add(self.company, 1, wx.EXPAND)

        # Revision
        grid_sizer.Add(wx.StaticText(self, label="Revision:"), 
                      0, wx.ALIGN_CENTER_VERTICAL)
        self.revision = wx.TextCtrl(self, value="1.0.0")
        grid_sizer.Add(self.revision, 1, wx.EXPAND)

        # Description
        grid_sizer.Add(wx.StaticText(self, label="Description:"), 
                      0, wx.ALIGN_TOP | wx.TOP, border=5)
        self.description = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 80))
        grid_sizer.Add(self.description, 1, wx.EXPAND)

        main_sizer.Add(grid_sizer, 0, wx.ALL | wx.EXPAND, 10)

        # Info text
        info_text = wx.StaticText(self, 
                                 label="* Required fields\n\n"
                                       "This will update the current project's metadata.")
        info_text.SetForegroundColour(wx.Colour(100, 100, 100))
        main_sizer.Add(info_text, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Buttons
        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(self, wx.ID_OK, "Apply")
        cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizer(main_sizer)
        self.Fit()

    def get_values(self):
        """Return the entered values as a dictionary"""
        git_url = self.git_url.GetValue().strip().rstrip('/')
        git_user, git_repo = _parse_git_url(git_url)
        return {
            'project_name': self.project_name.GetValue(),
            'board_name': self.board_name.GetValue(),
            'designer': self.designer.GetValue(),
            'email': self.email.GetValue().strip(),
            'company': self.company.GetValue(),
            'revision': self.revision.GetValue() or "1.0.0",
            'description': self.description.GetValue(),
            'git_url': git_url,
            'git_user': git_user,
            'git_repo': git_repo,
            'master_branch': self.master_branch.GetValue().strip() or "main",
        }

    def validate_inputs(self):
        """Validate required inputs"""
        if not self.project_name.GetValue():
            wx.MessageBox("Project Name is required!", "Validation Error", 
                         wx.OK | wx.ICON_ERROR)
            return False
        if not self.board_name.GetValue():
            wx.MessageBox("Board Name is required!", "Validation Error", 
                         wx.OK | wx.ICON_ERROR)
            return False
        if not self.designer.GetValue():
            wx.MessageBox("Designer is required!", "Validation Error", 
                         wx.OK | wx.ICON_ERROR)
            return False
        if not self.email.GetValue().strip():
            wx.MessageBox("Email is required!", "Validation Error",
                         wx.OK | wx.ICON_ERROR)
            return False
        git_url = self.git_url.GetValue().strip()
        if not git_url or 'github.com' not in git_url:
            wx.MessageBox("A valid GitHub URL is required!\n"
                         "Example: https://github.com/user/repo",
                         "Validation Error", wx.OK | wx.ICON_ERROR)
            return False
        if not _parse_git_url(git_url)[0]:
            wx.MessageBox("Could not parse username and repository from URL.\n"
                         "Expected format: https://github.com/user/repo",
                         "Validation Error", wx.OK | wx.ICON_ERROR)
            return False
        return True

class KiCadProjectInit(pcbnew.ActionPlugin):
    """
    Action plugin to initialize KiCad project metadata
    """

    def defaults(self):
        """Plugin metadata"""
        self.name = "Initialize Project Metadata"
        self.category = "Project Management"
        self.description = "Initialize project with custom metadata (PROJECT_NAME, BOARD_NAME, etc.)"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), 'icon.png')

    def Run(self):
        """Execute the plugin"""
        try:
            # First, ask what mode to use
            mode_dialog = ProjectModeDialog(None)
            if mode_dialog.ShowModal() != wx.ID_OK:
                mode_dialog.Destroy()
                return

            mode = mode_dialog.mode
            mode_dialog.Destroy()

            if mode == "new":
                self.create_new_project()
            else:
                self.update_existing_project()

        except Exception as e:
            wx.MessageBox(f"Error: {str(e)}", "Plugin Error", 
                         wx.OK | wx.ICON_ERROR)

    def create_new_project(self):
        """Create a new project from template"""
        # Template is in the plugin directory
        plugin_dir = Path(__file__).parent
        template_path = plugin_dir / "__Project__"

        if not template_path.exists():
            wx.MessageBox(
                f"Template directory not found!\n\n"
                f"Expected: {template_path}\n\n"
                f"Please ensure the __Project__ template is in the plugin directory.\n"
                f"It is the Git submodule of https://github.com/Kampi/Template-Project",
                "Template Not Found", 
                wx.OK | wx.ICON_ERROR
            )
            return

        # Show dialog
        dialog = NewProjectDialog(None, str(template_path))

        if dialog.ShowModal() == wx.ID_OK:
            if not dialog.validate_inputs():
                dialog.Destroy()
                return

            values = dialog.get_values()
            dialog.Destroy()

            # Create the project
            success, project_path = self.copy_and_initialize_template(template_path, values)

            if success:
                message = (
                    f"Project created successfully!\n\n"
                    f"Location: {project_path}\n"
                    f"Project: {values['project_name']}\n"
                    f"Type: {values['project_type']['name']}\n"
                )
                if values['project_type']['has_hardware']:
                    kicad_pro = (project_path / values['board_name'].lower()
                                 / (values['board_name'] + '.kicad_pro'))
                    message += (
                        f"Board: {values['board_name']}\n\n"
                        f"You can now open the project in KiCad:\n"
                        f"{kicad_pro}"
                    )
                wx.MessageBox(message, "Success", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox("Failed to create project!", "Error", 
                            wx.OK | wx.ICON_ERROR)
        else:
            dialog.Destroy()

    def update_existing_project(self):
        """Update existing project metadata and copy missing template files"""
        board = pcbnew.GetBoard()

        if not board:
            wx.MessageBox("No board loaded!", "Error", wx.OK | wx.ICON_ERROR)
            return

        # Get the project file path
        board_filename = board.GetFileName()
        if not board_filename:
            wx.MessageBox("Please save the board first!", "Error", 
                        wx.OK | wx.ICON_ERROR)
            return

        board_dir = Path(board_filename).parent
        project_root = board_dir.parent  # One level up from board directory
        project_name_from_file = Path(board_filename).stem

        # Show important warning about limitations
        warning_msg = wx.MessageDialog(
            None,
            "⚠️ Important Information - Update Existing Project\n\n"
            "What will be updated:\n"
            "✓ Project metadata (PROJECT_NAME, DESIGNER, COMPANY, etc.)\n"
            "✓ Board title block information\n"
            "✓ KiBot configuration (if present)\n\n"
            "What will NOT be changed:\n"
            "✗ Schematic (.kicad_sch) - Your design is safe\n"
            "✗ PCB Layout (.kicad_pcb) - Your design is safe\n"
            "✗ Existing project structure\n\n"
            "⚠️ CI/CD Pipeline Limitations:\n"
            "Some GitHub Actions workflows may not function correctly "
            "if your project is missing elements from the template "
            "(e.g., firmware/, .github/workflows/, scripts/, kibot_yaml/).\n\n"
            "You will have the option to copy missing template files "
            "after updating metadata.\n\n"
            "Continue?",
            "Update Existing Project - Important Notice",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING
        )

        if warning_msg.ShowModal() != wx.ID_YES:
            warning_msg.Destroy()
            return
        warning_msg.Destroy()

        # Show dialog
        dialog = ProjectInitDialog(None)

        # Pre-fill board name from file
        dialog.board_name.SetValue(project_name_from_file)

        if dialog.ShowModal() == wx.ID_OK:
            if not dialog.validate_inputs():
                return

            values = dialog.get_values()

            # Ask if user wants to copy missing template files
            copy_msg = wx.MessageDialog(
                None,
                "Do you also want to copy missing template files?\n\n"
                "This will add:\n"
                "- firmware/ folder (if missing)\n"
                "- 3d-print/ folder (if missing)\n"
                "- cad/ folder (if missing)\n"
                "- .github/ with the workflows and the skills (if missing)\n"
                "- .claude/ with the pointers to the skills (if missing)\n"
                "- scripts/ folder (if missing)\n\n"
                "Existing files will NOT be overwritten.",
                "Copy Template Files?",
                wx.YES_NO | wx.ICON_QUESTION
            )
            copy_files = copy_msg.ShowModal() == wx.ID_YES
            copy_msg.Destroy()

            # Update project file (.kicad_pro)
            success = self.update_project_file(board_dir, 
                                              project_name_from_file, 
                                              values)

            copied_items = []

            if success:
                # Update board metadata
                self.update_board_metadata(board, values)

                # Copy missing template files if requested
                if copy_files:
                    copied_items = self.copy_missing_template_files(project_root, values,
                                                                    board_dir_name=board_dir.name)

                success_msg = (
                    f"Project metadata updated successfully!\n\n"
                    f"Project: {values['project_name']}\n"
                    f"Board: {values['board_name']}\n"
                    f"Designer: {values['designer']}\n"
                    f"Company: {values['company'] or 'N/A'}\n"
                    f"Revision: {values['revision']}"
                )

                if copied_items:
                    success_msg += "\n\nCopied template files:\n" + "\n".join(f"- {item}" for item in copied_items)

                wx.MessageBox(success_msg, "Success", wx.OK | wx.ICON_INFORMATION)

                # Refresh the display
                pcbnew.Refresh()
            else:
                wx.MessageBox("Failed to update project file!", "Error", 
                            wx.OK | wx.ICON_ERROR)

        dialog.Destroy()

    def update_project_file(self, project_path, project_file_name, values):
        """Update the .kicad_pro file with text variables"""
        try:
            kicad_pro_file = project_path / f"{project_file_name}.kicad_pro"

            if not kicad_pro_file.exists():
                return False

            # Read the JSON file
            with open(kicad_pro_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Ensure text_variables exists
            if 'text_variables' not in data:
                data['text_variables'] = {}

            # Update text_variables
            current_date = datetime.date.today()
            data['text_variables']['PROJECT_NAME'] = values['project_name']
            data['text_variables']['BOARD_NAME'] = values['board_name']
            data['text_variables']['DESIGNER'] = values['designer']
            data['text_variables']['COMPANY'] = values['company'] or ''
            data['text_variables']['RELEASE_DATE'] = current_date.strftime("%d-%b-%Y")
            data['text_variables']['RELEASE_DATE_NUM'] = current_date.strftime("%Y-%m-%d")
            data['text_variables']['REVISION'] = values['revision']
            data['text_variables']['GIT_URL'] = values.get('git_url', '')

            # Replace the references to the template project name
            if isinstance(data.get('meta'), dict) and 'filename' in data['meta']:
                data['meta']['filename'] = f"{project_file_name}.kicad_pro"
            for sheet in (data.get('schematic') or {}).get('top_level_sheets') or []:
                if sheet.get('filename') == 'Template.kicad_sch':
                    sheet['filename'] = f"{project_file_name}.kicad_sch"
                if sheet.get('name') == 'Template':
                    sheet['name'] = project_file_name
            for sheet in data.get('sheets') or []:
                if len(sheet) > 1 and sheet[1] == 'Template':
                    sheet[1] = project_file_name

            # Write back to file
            with open(kicad_pro_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"Error updating project file: {e}")
            return False

    def update_board_metadata(self, board, values):
        """Update board title and metadata"""
        try:
            # Update title block
            title_block = board.GetTitleBlock()
            title_block.SetTitle(values['board_name'])

            if values['description']:
                title_block.SetComment(0, values['description'])

            title_block.SetCompany(values['company'])
            title_block.SetRevision(values['revision'])
            title_block.SetDate(datetime.date.today().strftime("%Y-%m-%d"))

            # Mark board as modified
            board.SetModified()

        except Exception as e:
            print(f"Error updating board metadata: {e}")

    def copy_and_initialize_template(self, template_path, values):
        """Copy template and initialize with values (same steps as init-project.sh)"""
        try:
            project_location = Path(values['project_location'])
            project_name = values['project_name']
            board_name = values['board_name']
            project_type = values.get('project_type', PROJECT_TYPES[0])
            has_hardware = project_type['has_hardware']

            # Create project directory
            project_path = project_location / project_name

            if project_path.exists():
                wx.MessageBox(
                    f"Directory already exists:\n{project_path}\n\n"
                    f"Please choose a different name or location.",
                    "Directory Exists", 
                    wx.OK | wx.ICON_ERROR
                )
                return False, None

            # Copy template. The Git data of the template is a directory in a
            # regular clone and a file (gitdir link) when it is a submodule.
            shutil.copytree(template_path, project_path, ignore=shutil.ignore_patterns('.git'))

            # Remove local KiCad files copied from the template
            self.remove_local_kicad_files(project_path / "hardware")

            # Keep the firmware profile, the directories and the workflows of the project type
            self.apply_project_type(project_path, project_type, values.get('git_repo', ''))

            # The hardware directory is named after the board in lowercase,
            # like kibot_input_dir in the workflows (${BOARD_NAME_LOWER})
            board_dir = project_path / board_name.lower()

            if has_hardware:
                hardware_dir = project_path / "hardware"

                # Apply PCB template
                if values['pcb_template']:
                    self.apply_pcb_template(hardware_dir, values['pcb_template'],
                                           board_name, project_name)

                # Rename hardware directory
                if hardware_dir.exists():
                    hardware_dir.rename(board_dir)

                # Rename KiCad project files
                self.rename_project_files(board_dir, board_name)

                # Update schematic title and the project name of the sheet instances
                self.update_schematic_title(board_dir, board_name)

                # Update .kicad_pro file
                self.update_project_file(board_dir, board_name, values)

                # Update kibot_main.yaml if exists
                self.update_kibot_config(board_dir, values)

            # Remove VARIABLES.md from project root
            variables_md = project_path / "VARIABLES.md"
            if variables_md.exists():
                variables_md.unlink()

            # Update GitHub Actions workflow files
            self.update_workflow_files(project_path, values)

            # Create license files if selected
            if values['license']['key'] != 'none':
                self.create_license_files(project_path, board_dir, values)

            # Update commit message template
            self.update_commit_template(project_path, values)

            # Update README.md
            self.update_readme(project_path, values)

            # Replace all ${...} placeholders in remaining text files
            self.replace_all_variables([project_path], values)

            # Create the AsciiDoc documentation scaffolding
            self.create_documentation(project_path, values)

            return True, project_path

        except Exception as e:
            print(f"Error creating project: {e}")
            import traceback
            traceback.print_exc()
            return False, None

    def remove_local_kicad_files(self, hardware_dir):
        """Remove backups, footprint cache, local settings and lock files of the template"""
        if not hardware_dir.exists():
            return
        try:
            for item in hardware_dir.iterdir():
                name = item.name
                if (name.endswith('-backups') or name == 'fp-info-cache'
                        or name.endswith('.kicad_prl') or name.endswith('.lck')):
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
        except Exception as e:
            print(f"Error removing local KiCad files: {e}")

    def apply_project_type(self, project_path, project_type, git_repo):
        """Keep the selected firmware profile and remove the directories and
        workflows of the other project types (apply_project_type in init-project.sh)"""
        has_hardware = project_type['has_hardware']
        profile = project_type['firmware_profile']
        workflows_dir = project_path / ".github" / "workflows"
        firmware_dir = project_path / "firmware"
        profile_path = firmware_dir / profile

        if not profile_path.is_dir():
            raise FileNotFoundError(f"Firmware profile not found: {profile_path}")

        def remove(path):
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()

        def remove_workflows(pattern):
            if workflows_dir.exists():
                for workflow in workflows_dir.glob(pattern):
                    workflow.unlink()

        # Hardware: KiCad project, hardware workflows and the release skills
        if not has_hardware:
            for name in ("hardware", "cad", "3d-print"):
                remove(project_path / name)
            remove(project_path / ".github" / "skills")
            remove(project_path / ".claude" / "skills")
            # .claude only contains the pointers to the skills
            claude_dir = project_path / ".claude"
            if claude_dir.is_dir() and not any(claude_dir.iterdir()):
                claude_dir.rmdir()
            remove_workflows("hw-*.yaml")

        # Workflows of the firmware profiles that are not used
        if profile != "platformio":
            remove_workflows("fw-platformio.yaml")
        if profile != COMPONENT_PROFILE:
            remove_workflows("fw-esp-component*.yaml")

        if profile == COMPONENT_PROFILE:
            # The component is the repository root, the profile brings its own
            # README.md, CHANGELOG.md and .gitignore
            remove_workflows("docs-*.yaml")
            remove(project_path / "README.md")
            remove(project_path / ".gitignore")
            shutil.copytree(profile_path, project_path, dirs_exist_ok=True)
            shutil.rmtree(firmware_dir)

            # Name the sources after the component
            component = _make_identifier(git_repo)
            (project_path / "include" / "template.h").rename(
                project_path / "include" / f"{component}.h")
            (project_path / "src" / "template.c").rename(
                project_path / "src" / f"{component}.c")

            format_workflow = workflows_dir / "fw-format.yaml"
            if format_workflow.exists():
                content = format_workflow.read_text(encoding='utf-8')
                content = re.sub(r'(?m)^  source_dirs: .*$',
                                 '  source_dirs: src include examples', content)
                format_workflow.write_text(content, encoding='utf-8')
        else:
            # The selected profile becomes the content of firmware/
            for item in firmware_dir.iterdir():
                if item.is_dir() and item.name != profile:
                    shutil.rmtree(item)
            shutil.copytree(profile_path, firmware_dir, dirs_exist_ok=True)
            shutil.rmtree(profile_path)

        # README badges of removed workflows
        readme = project_path / "README.md"
        if readme.exists():
            lines = readme.read_text(encoding='utf-8').splitlines(keepends=True)
            for workflow_name in ("hw-pcb.yaml", "fw-platformio.yaml", "fw-esp-component.yaml"):
                if not (workflows_dir / workflow_name).exists():
                    lines = [line for line in lines
                             if f"actions/workflows/{workflow_name}" not in line]
            if not has_hardware:
                pattern = re.compile(r'^- \*\*`(3d-print|cad|\$\{BOARD_NAME_LOWER\})`\*\*')
                lines = [line for line in lines if not pattern.match(line)]
            readme.write_text(''.join(lines), encoding='utf-8')

    def apply_pcb_template(self, board_dir, template_info, board_name, project_name):
        """Apply selected PCB template"""
        try:
            source_pcb = board_dir / template_info['filename']
            target_pcb = board_dir / "Template.kicad_pcb"

            if source_pcb.exists():
                # Copy selected template
                shutil.copy2(source_pcb, target_pcb)

                # Update board name in PCB file
                content = target_pcb.read_text(encoding='utf-8')
                content = content.replace('BOARD_NAME" "Template"', f'BOARD_NAME" "{board_name}"')
                content = content.replace('PROJECT_NAME" "Template"', f'PROJECT_NAME" "{project_name}"')
                target_pcb.write_text(content, encoding='utf-8')

                # Remove all other template files
                for pattern in ("Template - *.kicad_pcb", "Template - *.kicad_pro"):
                    for template_file in board_dir.glob(pattern):
                        template_file.unlink()

        except Exception as e:
            print(f"Error applying PCB template: {e}")

    def rename_project_files(self, board_dir, board_name):
        """Rename Template.* files to board_name.*"""
        try:
            for template_file in board_dir.glob("Template.*"):
                new_name = board_dir / template_file.name.replace("Template", board_name)
                template_file.rename(new_name)
        except Exception as e:
            print(f"Error renaming project files: {e}")

    def update_schematic_title(self, board_dir, board_name):
        """Update title in main schematic file"""
        try:
            sch_file = board_dir / f"{board_name}.kicad_sch"
            if sch_file.exists():
                content = sch_file.read_text(encoding='utf-8')
                content = re.sub(r'\(title "Template"\)', f'(title "{board_name}")', content)
                sch_file.write_text(content, encoding='utf-8')

            # Sheet instances (page numbers) are stored per project name
            for sheet in board_dir.glob("*.kicad_sch"):
                content = sheet.read_text(encoding='utf-8')
                updated = content.replace('(project "Template"', f'(project "{board_name}"')
                if updated != content:
                    sheet.write_text(updated, encoding='utf-8')
        except Exception as e:
            print(f"Error updating schematic title: {e}")

    def update_kibot_config(self, board_dir, values):
        """Update kibot_main.yaml configuration"""
        try:
            kibot_file = board_dir / "kibot_yaml" / "kibot_main.yaml"
            if not kibot_file.exists():
                return

            content = kibot_file.read_text(encoding='utf-8')

            # Update definitions
            content = re.sub(r'PROJECT_NAME: Project', 
                           f'PROJECT_NAME: {values["project_name"]}', content)
            content = re.sub(r'BOARD_NAME: Board', 
                           f'BOARD_NAME: {values["board_name"]}', content)
            content = re.sub(r'COMPANY: Kampis-Elektroecke', 
                           f'COMPANY: {values["company"] or ""}', content)
            content = re.sub(r'DESIGNER: Daniel Kampert', 
                           f'DESIGNER: {values["designer"]}', content)
            content = re.sub(r"GIT_URL: 'https://github\.com/Kampi/KiCad'",
                           f"GIT_URL: '{values.get('git_url', '')}'", content)

            kibot_file.write_text(content, encoding='utf-8')

        except Exception as e:
            print(f"Error updating kibot config: {e}")

    def copy_missing_template_files(self, project_root, values, board_dir_name=None):
        """Copy missing directories and files from template to existing project.
        An existing project is a hardware project: the copied directories get the
        blank firmware profile and only the workflows of that project type.
        'board_dir_name' is the name of the existing hardware directory."""
        try:
            plugin_dir = Path(__file__).parent
            template_path = plugin_dir / "__Project__"

            if not template_path.exists():
                return ["Error: Template not found in plugin directory"]

            copied_items = []
            copied_paths = []

            # Directories to copy if missing. The workflows need the scripts.
            dirs_to_copy = ['firmware', '3d-print', 'cad', '.github', '.claude', 'scripts']

            for dir_name in dirs_to_copy:
                src_dir = template_path / dir_name
                dst_dir = project_root / dir_name

                if src_dir.exists() and not dst_dir.exists():
                    try:
                        shutil.copytree(src_dir, dst_dir)
                        copied_items.append(f"{dir_name}/ (complete folder)")
                        copied_paths.append(dst_dir)
                    except Exception as e:
                        print(f"Error copying {dir_name}: {e}")

            # Firmware: keep the blank profile as content of firmware/
            firmware_dir = project_root / 'firmware'
            if firmware_dir in copied_paths:
                profile_path = firmware_dir / 'blank'
                for item in firmware_dir.iterdir():
                    if item.is_dir() and item.name != 'blank':
                        shutil.rmtree(item)
                if profile_path.is_dir():
                    shutil.copytree(profile_path, firmware_dir, dirs_exist_ok=True)
                    shutil.rmtree(profile_path)

            # Workflows: remove the ones of the other firmware profiles
            workflows_dir = project_root / '.github' / 'workflows'
            if (project_root / '.github') in copied_paths and workflows_dir.exists():
                for pattern in ("fw-platformio.yaml", "fw-esp-component*.yaml"):
                    for workflow in workflows_dir.glob(pattern):
                        workflow.unlink()
                self.update_workflow_files(project_root, values)
                self.update_commit_template(project_root, values)

            # Update README.md if it doesn't exist
            readme_src = template_path / "README.md"
            readme_dst = project_root / "README.md"
            if readme_src.exists() and not readme_dst.exists():
                try:
                    shutil.copy2(readme_src, readme_dst)
                    lines = readme_dst.read_text(encoding='utf-8').splitlines(keepends=True)
                    for workflow_name in ("fw-platformio.yaml", "fw-esp-component.yaml"):
                        lines = [line for line in lines
                                 if f"actions/workflows/{workflow_name}" not in line]
                    readme_dst.write_text(''.join(lines), encoding='utf-8')
                    self.update_readme(project_root, values)
                    copied_items.append("README.md")
                    copied_paths.append(readme_dst)
                except Exception as e:
                    print(f"Error copying README: {e}")

            # Copy .gitignore if missing
            gitignore_src = template_path / ".gitignore"
            gitignore_dst = project_root / ".gitignore"
            if gitignore_src.exists() and not gitignore_dst.exists():
                try:
                    shutil.copy2(gitignore_src, gitignore_dst)
                    copied_items.append(".gitignore")
                except Exception as e:
                    print(f"Error copying .gitignore: {e}")

            # Set the ${...} placeholders in the copied files only
            if copied_paths:
                self.replace_all_variables(copied_paths, values, board_name_lower=board_dir_name)

            return copied_items if copied_items else ["No missing files found"]

        except Exception as e:
            print(f"Error copying template files: {e}")
            import traceback
            traceback.print_exc()
            return [f"Error: {str(e)}"]

    def create_license_files(self, project_root, board_dir, values):
        """Create license files in project and subdirectories"""
        try:
            license_key = values['license']['key']
            license_name = values['license']['name']
            designer = values['designer']
            year = datetime.date.today().year

            # Try to download license from GitHub
            license_text = self.download_license(license_key, year, designer)

            if license_text:
                # Create license in project root
                license_file = project_root / "LICENSE"
                license_file.write_text(license_text, encoding='utf-8')

                # Create license in subdirectories
                subdirs = [board_dir, project_root / 'firmware', 
                          project_root / '3d-print', project_root / 'cad']

                for subdir in subdirs:
                    if subdir.exists():
                        sub_license = subdir / "LICENSE"
                        sub_license.write_text(license_text, encoding='utf-8')

                print(f"License files created: {license_name}")
            else:
                print(f"Could not create license files for: {license_name}")

        except Exception as e:
            print(f"Error creating license files: {e}")

    def download_license(self, license_key, year, copyright_holder):
        """Download license template from GitHub"""
        try:
            url = f"https://raw.githubusercontent.com/licenses/license-templates/master/templates/{license_key}.txt"

            # Download license
            with urllib.request.urlopen(url, timeout=10) as response:
                license_text = response.read().decode('utf-8')

            # Replace placeholders
            license_text = license_text.replace('[year]', str(year))
            license_text = license_text.replace('[fullname]', copyright_holder)
            license_text = license_text.replace('[email]', '')

            return license_text

        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            print(f"Failed to download license from {url}: {e}")
            # Create placeholder license
            return self.create_placeholder_license(license_key, year, copyright_holder)
        except Exception as e:
            print(f"Error downloading license: {e}")
            return self.create_placeholder_license(license_key, year, copyright_holder)

    def create_placeholder_license(self, license_key, year, copyright_holder):
        """Create a placeholder license if download fails"""
        return f"""License: {license_key}

Copyright (c) {year} {copyright_holder}

All rights reserved.

Please visit https://opensource.org/licenses/ for full license text.
"""

    # ------------------------------------------------------------------
    # New helper methods matching init-project.sh logic
    # ------------------------------------------------------------------

    def update_workflow_files(self, project_path, values):
        """Update GitHub Actions workflow files with project-specific values.
        The board name and the directories are ${...} placeholders, they are
        set by replace_all_variables()."""
        workflows_dir = project_path / ".github" / "workflows"
        if not workflows_dir.exists():
            return

        master_branch = values.get('master_branch', 'main')

        for wf_file in workflows_dir.glob("*.yaml"):
            try:
                content = wf_file.read_text(encoding='utf-8')

                # Update master branch in all workflow files
                content = re.sub(r'master_branch:\s*main', f'master_branch: {master_branch}', content)
                content = re.sub(r'master_branch:\s*master', f'master_branch: {master_branch}', content)

                if wf_file.name == "hw-pcb.yaml":
                    # New projects start in DRAFT state
                    content = re.sub(r'kibot_variant:\s*PRELIMINARY',
                                     'kibot_variant: DRAFT', content)

                wf_file.write_text(content, encoding='utf-8')
            except Exception as e:
                print(f"Error updating workflow {wf_file.name}: {e}")

    def update_commit_template(self, project_path, values):
        """Update .github/.commit-msg-template with designer sign-off"""
        template_file = project_path / ".github" / ".commit-msg-template"
        if not template_file.exists():
            return
        try:
            content = template_file.read_text(encoding='utf-8')
            content = re.sub(r'Signed-off-by:.*',
                             f'Signed-off-by: {values["designer"]} <{values.get("email", "")}>',
                             content)
            template_file.write_text(content, encoding='utf-8')
        except Exception as e:
            print(f"Error updating commit template: {e}")

    def update_readme(self, project_path, values):
        """Set the license badge of the README.md. All other placeholders are
        set by replace_all_variables()."""
        readme = project_path / "README.md"
        if not readme.exists():
            return
        try:
            content = readme.read_text(encoding='utf-8')

            license_info = values.get('license', {})
            license_badge = license_info.get('badge', '')
            license_key = license_info.get('key', '')

            if license_badge:
                license_link = f'https://opensource.org/license/{license_key}/'
            else:
                license_badge = 'No-License-lightgrey'
                license_link = 'https://choosealicense.com/no-permission/'

            content = content.replace('${LICENSE_BADGE}', license_badge)
            content = content.replace('${LICENSE_LINK}', license_link)

            readme.write_text(content, encoding='utf-8')
        except Exception as e:
            print(f"Error updating README.md: {e}")

    def replace_all_variables(self, paths, values, board_name_lower=None):
        """Replace all ${...} template placeholders in all text files below the
        given files and directories. 'board_name_lower' overrides the name of the
        hardware directory for existing projects."""
        skip_extensions = {
            '.kicad_pcb', '.kicad_sch', '.kicad_pro', '.kicad_prl',
            '.kicad_wks', '.png', '.jpg', '.jpeg', '.gif', '.pdf',
            '.zip', '.gz', '.o', '.so', '.dll', '.exe', '.pyc',
        }
        skip_dirs = {'.git', '__pycache__', 'node_modules', '.svn'}

        release_date = datetime.date.today().strftime('%d-%b-%Y')
        release_date_num = datetime.date.today().strftime('%Y-%m-%d')
        current_year = str(datetime.date.today().year)
        project_name_anchor = _make_anchor(values['project_name'])
        board_name_anchor = _make_anchor(values['board_name'])
        git_repo = values.get('git_repo', '')
        git_url = values.get('git_url', '').rstrip('/').removesuffix('.git')
        if board_name_lower is None:
            board_name_lower = values['board_name'].lower()

        replacements = {
            '${PROJECT_NAME}':        values['project_name'],
            '${BOARD_NAME}':          values['board_name'],
            '${DESIGNER}':            values['designer'],
            '${EMAIL}':               values.get('email', ''),
            '${COMPANY}':             values.get('company', ''),
            '${REVISION}':            values['revision'],
            '${RELEASE_DATE}':        release_date,
            '${RELEASE_DATE_NUM}':    release_date_num,
            '${CURRENT_DATE}':        release_date,
            '${CURRENT_YEAR}':        current_year,
            '${GIT_URL}':             git_url,
            '${GIT_USER}':            values.get('git_user', ''),
            '${GIT_REPO}':            git_repo,
            # Repository name as C identifier (file names, functions, CMake variables)
            '${GIT_REPO_LOWER}':      _make_identifier(git_repo),
            '${GIT_REPO_UPPER}':      _make_identifier(git_repo).upper(),
            '${MASTER_BRANCH}':       values.get('master_branch', 'main'),
            '${PROJECT_NAME_ANCHOR}': project_name_anchor,
            '${BOARD_NAME_ANCHOR}':   board_name_anchor,
            '${BOARD_NAME_LOWER}':    board_name_lower,
            # Legacy "$..." placeholders
            '"$Project"':             values['project_name'],
            '"$Designer"':            values['designer'],
            '"$Email"':               values.get('email', ''),
            '"$User"':                values.get('git_user', ''),
        }

        files = []
        for path in paths:
            path = Path(path)
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                files.extend(p for p in path.rglob('*') if p.is_file())

        for file_path in files:
            # Skip hidden/special directories
            if any(part in skip_dirs for part in file_path.parts):
                continue
            if file_path.suffix.lower() in skip_extensions:
                continue
            # Skip backup files
            if file_path.name.endswith('~') or file_path.name.endswith('.bak'):
                continue
            try:
                # newline='' keeps the line endings of the template
                with open(file_path, 'r', encoding='utf-8', newline='') as f:
                    content = f.read()
                updated = content
                for placeholder, value in replacements.items():
                    updated = updated.replace(placeholder, value)
                if updated != content:
                    with open(file_path, 'w', encoding='utf-8', newline='') as f:
                        f.write(updated)
            except (UnicodeDecodeError, PermissionError):
                pass  # Skip binary or unreadable files
            except Exception as e:
                print(f"Error replacing variables in {file_path}: {e}")

    def create_documentation(self, project_path, values):
        """Create the AsciiDoc documentation scaffolding in firmware/docs/.
        The ESP-IDF component documents itself in the README.md."""
        project_type = values.get('project_type', PROJECT_TYPES[0])
        if project_type['firmware_profile'] == COMPONENT_PROFILE:
            return
        try:
            docs_dir = project_path / "firmware" / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)

            today = datetime.date.today().strftime('%Y-%m-%d')
            license_name = values.get('license', {}).get('name') or 'TBD'
            git_url = values.get('git_url', '').rstrip('/').removesuffix('.git')

            content = f"""= {values['project_name']} Documentation
{values['designer']} <{values.get('email', '')}>
v1.0, {today}
:toc: left
:toclevels: 3
:icons: font
:source-highlighter: highlight.js

== Overview

This document provides comprehensive documentation for the *{values['project_name']}* hardware project.

== Project Information

[cols="1,2"]
|===
|Project Name |{values['project_name']}
|Board Name |{values['board_name']}
|Designer |{values['designer']}
|Email |{values.get('email', '')}
|Company |{values.get('company') or 'N/A'}
|Repository |{git_url}
|License |{license_name}
|===

== Getting Started

=== Prerequisites

* KiCad 7.0 or later
* Basic understanding of PCB design

=== Project Structure

Refer to the main README.md for detailed information about the project structure.

== Hardware Design

=== Schematic

TBD - Add schematic overview and block diagrams

=== PCB Layout

TBD - Add PCB layout information and design considerations

=== Bill of Materials (BoM)

TBD - Add component list and sourcing information

== Assembly Instructions

TBD - Add assembly steps and guidelines

== Testing & Validation

TBD - Add testing procedures and validation criteria

== Revision History

[cols="1,2,2,3"]
|===
|Version |Date |Author |Changes

|1.0
|{today}
|{values['designer']}
|Initial release

|===
"""
            with open(docs_dir / "index.adoc", 'w', encoding='utf-8', newline='\n') as f:
                f.write(content)
        except Exception as e:
            print(f"Error creating documentation: {e}")
