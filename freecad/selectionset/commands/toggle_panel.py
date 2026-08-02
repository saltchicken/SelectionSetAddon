import FreeCAD as App
import FreeCADGui as Gui

try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets

from freecad.selectionset.ui.dock_widget import AdvancedSelectionDock

class ToggleSelectionPanelCommand:
    Name = "SelectionSet_Toggle"

    def GetResources(self):
        return {
            "Pixmap": "SelectionSet",
            "MenuText": "Advanced Selection",
            "ToolTip": "Toggle the Advanced Selection panel"
        }

    def Activated(self):
        main_window = Gui.getMainWindow()
        
        # Check if it already exists to toggle visibility
        for child in main_window.findChildren(QtWidgets.QDockWidget, "AdvancedSelectionDock"):
            if child.isVisible():
                child.hide()
            else:
                child.show()
                child.raise_()
            return
            
        # If it doesn't exist, create it
        dock = AdvancedSelectionDock()
        main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)

    def IsActive(self):
        return True # Can be opened even without an active document

    @classmethod
    def Install(cls):
        if App.GuiUp:
            Gui.addCommand(cls.Name, cls())
