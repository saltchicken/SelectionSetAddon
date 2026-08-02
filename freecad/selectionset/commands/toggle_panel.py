import FreeCAD as App
import FreeCADGui as Gui

try:
    from PySide6 import QtCore
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtCore
    from PySide2 import QtWidgets


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

        # Simply toggle visibility
        for child in main_window.findChildren(QtWidgets.QDockWidget,
                                              "AdvancedSelectionDock"):
            if child.isVisible():
                child.hide()
            else:
                child.show()
                child.raise_()
            return

    def IsActive(self):
        return True

    @classmethod
    def Install(cls):
        if App.GuiUp:
            Gui.addCommand(cls.Name, cls())
