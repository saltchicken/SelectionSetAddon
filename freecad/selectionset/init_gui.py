import FreeCAD as App
import FreeCADGui as Gui

from .commands import ToggleSelectionPanelCommand
from .resources import Resources

# 1. Register icons so FreeCAD can find the command's icon
Resources.gui_register_icons()

# 2. Install the command into FreeCAD's internal command list
ToggleSelectionPanelCommand.Install()

# 3. Create a Workbench Manipulator to add a global toolbar
class SelectionSetManipulator:
    def modifyToolBars(self):
        # Creates a new toolbar called "AdvancedSelection" containing our button
        return [{"append": ToggleSelectionPanelCommand.Name, "toolBar": "AdvancedSelection"}]

    def modifyMenuBar(self):
        return []

    def modifyContextMenu(self, recipient):
        return []

if App.GuiUp:
    manipulator = SelectionSetManipulator()
    Gui.addWorkbenchManipulator(manipulator)
