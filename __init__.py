"""
KiCad Project Initialization Plugin
Initializes a new KiCad project with customizable metadata.
"""
from .kicad_project_init import KiCadProjectInit

# Register the plugin
KiCadProjectInit().register()
