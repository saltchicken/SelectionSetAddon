import FreeCAD as App
import FreeCADGui as Gui

from .commands import ToggleSelectionPanelCommand
from .resources import Resources

try:
    from PySide6 import QtCore
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtCore
    from PySide2 import QtWidgets

# 1. Register icons so FreeCAD can find the command's icon
Resources.gui_register_icons()

# 2. Install the command into FreeCAD's internal command list
ToggleSelectionPanelCommand.Install()


# 3. Create a Workbench Manipulator to add a global toolbar
class SelectionSetManipulator:

    def modifyToolBars(self):
        return [{
            "append": ToggleSelectionPanelCommand.Name,
            "toolBar": "AdvancedSelection"
        }]

    def modifyMenuBar(self):
        return []

    def modifyContextMenu(self, recipient):
        return []


if App.GuiUp:
    manipulator = SelectionSetManipulator()
    Gui.addWorkbenchManipulator(manipulator)

    from freecad.selectionset.ui.dock_widget import AdvancedSelectionDock
    main_window = Gui.getMainWindow()

    # Only add it if it doesn't already exist
    if not main_window.findChild(QtWidgets.QDockWidget,
                                 "AdvancedSelectionDock"):
        dock = AdvancedSelectionDock()
        main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
