"""
KiCad Project Initialization Plugin

This plugin allows you to initialize a KiCad project with customizable metadata
directly from within KiCad PCBNew.

Author: Based on init-project.sh script
Version: 1.0.0
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
        grid_sizer = wx.FlexGridSizer(9, 2, 10, 10)
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
        
        # PCB Template
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
        selected_template = None
        if self.pcb_templates and self.pcb_template.GetSelection() >= 0:
            selected_template = self.pcb_templates[self.pcb_template.GetSelection()]
        
        license_selection = self.license.GetSelection()
        license_info = self.get_license_info(license_selection)
            
        return {
            'project_location': self.project_location.GetValue(),
            'project_name': self.project_name.GetValue(),
            'board_name': self.board_name.GetValue(),
            'designer': self.designer.GetValue(),
            'company': self.company.GetValue(),
            'revision': self.revision.GetValue() or "1.0.0",
            'description': self.description.GetValue(),
            'pcb_template': selected_template,
            'license': license_info
        }
    
    def get_license_info(self, selection):
        """Get license information based on selection"""
        license_map = {
            0: {"name": "MIT", "key": "mit"},
            1: {"name": "Apache 2.0", "key": "apache-2-0"},
            2: {"name": "GPL 3.0", "key": "gpl-3-0"},
            3: {"name": "LGPL 3.0", "key": "lgpl-3-0"},
            4: {"name": "BSD 2-Clause", "key": "bsd-2-clause"},
            5: {"name": "BSD 3-Clause", "key": "bsd-3-clause"},
            6: {"name": "MPL 2.0", "key": "mpl-2-0"},
            7: {"name": "AGPL 3.0", "key": "agpl-3-0"},
            8: {"name": "Unlicense", "key": "unlicense"},
            9: {"name": "CC0 1.0", "key": "cc0-1-0"},
            10: {"name": "None", "key": "none"}
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
        if not self.board_name.GetValue():
            wx.MessageBox("Board Name is required!", "Validation Error", 
                         wx.OK | wx.ICON_ERROR)
            return False
        if not self.designer.GetValue():
            wx.MessageBox("Designer is required!", "Validation Error", 
                         wx.OK | wx.ICON_ERROR)
            return False
        if not self.pcb_templates:
            wx.MessageBox("No PCB templates found in template directory!", "Error", 
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
        grid_sizer = wx.FlexGridSizer(7, 2, 10, 10)
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
        return {
            'project_name': self.project_name.GetValue(),
            'board_name': self.board_name.GetValue(),
            'designer': self.designer.GetValue(),
            'company': self.company.GetValue(),
            'revision': self.revision.GetValue() or "1.0.0",
            'description': self.description.GetValue()
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
                f"You can copy it from D:\\KiCad\\__Project__",
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
                wx.MessageBox(
                    f"Project created successfully!\n\n"
                    f"Location: {project_path}\n"
                    f"Project: {values['project_name']}\n"
                    f"Board: {values['board_name']}\n\n"
                    f"You can now open the project in KiCad:\n"
                    f"{project_path / values['board_name'] / (values['board_name'] + '.kicad_pro')}",
                    "Success", 
                    wx.OK | wx.ICON_INFORMATION
                )
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
            "(e.g., firmware/, .github/workflows/, kibot_yaml/).\n\n"
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
                "- .github/workflows/ (if missing)\n\n"
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
                    copied_items = self.copy_missing_template_files(project_root, values)
                
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
            data['text_variables']['COMPANY'] = values['company'] if values['company'] else 'null'
            data['text_variables']['RELEASE_DATE'] = current_date.strftime("%d-%b-%Y")
            data['text_variables']['RELEASE_DATE_NUM'] = current_date.strftime("%Y-%m-%d")
            data['text_variables']['REVISION'] = values['revision']
            
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
        """Copy template and initialize with values"""
        try:
            project_location = Path(values['project_location'])
            project_name = values['project_name']
            board_name = values['board_name']
            
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
            
            # Copy template
            shutil.copytree(template_path, project_path)
            
            # Rename hardware directory to board_name
            hardware_dir = project_path / "hardware"
            board_dir = project_path / board_name
            if hardware_dir.exists():
                hardware_dir.rename(board_dir)
            
            # Apply PCB template
            if values['pcb_template']:
                self.apply_pcb_template(board_dir, values['pcb_template'], 
                                       board_name, project_name)
            
            # Rename KiCad project files
            self.rename_project_files(board_dir, board_name)
            
            # Update schematic title
            self.update_schematic_title(board_dir, board_name)
            
            # Update .kicad_pro file
            self.update_project_file(board_dir, board_name, values)
            
            # Update kibot_main.yaml if exists
            self.update_kibot_config(board_dir, values)
            
            # Create license files if selected
            if values['license']['key'] != 'none':
                self.create_license_files(project_path, board_dir, values)
            
            return True, project_path
            
        except Exception as e:
            print(f"Error creating project: {e}")
            import traceback
            traceback.print_exc()
            return False, None
    
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
                for template_file in board_dir.glob("Template - *.kicad_pcb"):
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
                           f'COMPANY: {values["company"] or "null"}', content)
            content = re.sub(r'DESIGNER: Daniel Kampert', 
                           f'DESIGNER: {values["designer"]}', content)
            
            kibot_file.write_text(content, encoding='utf-8')
            
        except Exception as e:
            print(f"Error updating kibot config: {e}")
    
    def copy_missing_template_files(self, project_root, values):
        """Copy missing directories and files from template to existing project"""
        try:
            plugin_dir = Path(__file__).parent
            template_path = plugin_dir / "__Project__"
            
            if not template_path.exists():
                return ["Error: Template not found in plugin directory"]
            
            copied_items = []
            
            # Directories to copy if missing
            dirs_to_copy = ['firmware', '3d-print', 'cad', '.github']
            
            for dir_name in dirs_to_copy:
                src_dir = template_path / dir_name
                dst_dir = project_root / dir_name
                
                if src_dir.exists() and not dst_dir.exists():
                    try:
                        shutil.copytree(src_dir, dst_dir)
                        copied_items.append(f"{dir_name}/ (complete folder)")
                    except Exception as e:
                        print(f"Error copying {dir_name}: {e}")
            
            # Update README.md if it doesn't exist
            readme_src = template_path / "README.md"
            readme_dst = project_root / "README.md"
            if readme_src.exists() and not readme_dst.exists():
                try:
                    shutil.copy2(readme_src, readme_dst)
                    # Update placeholders in README
                    content = readme_dst.read_text(encoding='utf-8')
                    content = content.replace('"$Project"', values['project_name'])
                    content = content.replace('"$Designer"', values['designer'])
                    content = content.replace('"$User"', values['designer'])
                    readme_dst.write_text(content, encoding='utf-8')
                    copied_items.append("README.md")
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
