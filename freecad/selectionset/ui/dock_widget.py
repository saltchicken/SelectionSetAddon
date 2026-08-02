import FreeCAD as App
import FreeCADGui as Gui

try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets

class SelectionObserver:
    def __init__(self, update_callback):
        self.update_callback = update_callback

    def addSelection(self, *args): self.update_callback()
    def removeSelection(self, *args): self.update_callback()
    def setSelection(self, *args): self.update_callback()
    def clearSelection(self, *args): self.update_callback()


class AdvancedSelectionDock(QtWidgets.QDockWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Selection")
        self.setObjectName("AdvancedSelectionDock")
        self.saved_groups = {} 

        self.tabs = QtWidgets.QTabWidget()
        self.setWidget(self.tabs)

        # === TAB 1: CURRENT SELECTION ===
        self.tab_current = QtWidgets.QWidget()
        self.layout_current = QtWidgets.QVBoxLayout(self.tab_current)
        self.current_list = QtWidgets.QListWidget()
        self.layout_current.addWidget(self.current_list)
        self.tabs.addTab(self.tab_current, "Current Selection")

        # === TAB 2: SAVED GROUPS ===
        self.tab_saved = QtWidgets.QWidget()
        self.layout_saved = QtWidgets.QVBoxLayout(self.tab_saved)

        self.group_list = QtWidgets.QListWidget()
        self.layout_saved.addWidget(self.group_list)

        self.btn_save = QtWidgets.QPushButton("Save Current Selection")
        self.btn_save.clicked.connect(self.save_group)
        self.layout_saved.addWidget(self.btn_save)

        self.btn_restore = QtWidgets.QPushButton("Restore Selection")
        self.btn_restore.clicked.connect(self.restore_group)
        self.layout_saved.addWidget(self.btn_restore)

        self.btn_delete = QtWidgets.QPushButton("Delete Group")
        self.btn_delete.clicked.connect(self.delete_group)
        self.layout_saved.addWidget(self.btn_delete)

        self.tabs.addTab(self.tab_saved, "Saved Groups")

        # === INITIALIZE OBSERVER ===
        self.observer = SelectionObserver(self.update_current_tab)
        Gui.Selection.addObserver(self.observer)
        self.update_current_tab()

    def update_current_tab(self):
        """Refreshes Tab 1 whenever you click something in FreeCAD, if visible."""
        if not self.isVisible():
            return
            
        self.current_list.clear()
        sel_ex = Gui.Selection.getSelectionEx()
        for sel in sel_ex:
            doc, obj, subs = sel.DocumentName, sel.ObjectName, sel.SubElementNames
            if subs:
                for sub in subs:
                    self.current_list.addItem(f"{doc} \u25B8 {obj} \u25B8 {sub}")
            else:
                self.current_list.addItem(f"{doc} \u25B8 {obj}")

    def showEvent(self, event):
        """Forces the current selection tab to update the moment the panel is shown."""
        self.update_current_tab()
        super().showEvent(event)

    def save_group(self):
        sel_ex = Gui.Selection.getSelectionEx()
        if not sel_ex:
            QtWidgets.QMessageBox.warning(self, "Empty Selection", "Select something first.")
            return

        name, ok = QtWidgets.QInputDialog.getText(self, "Save Selection", "Enter group name:")
        if ok and name:
            group_data = [(sel.DocumentName, sel.ObjectName, sel.SubElementNames) for sel in sel_ex]
            if name not in self.saved_groups:
                self.group_list.addItem(name)
            self.saved_groups[name] = group_data

    def restore_group(self):
        current_item = self.group_list.currentItem()
        if not current_item: 
            return
        
        name = current_item.text()
        group_data = self.saved_groups.get(name, [])
        Gui.Selection.clearSelection()
        
        for doc_name, obj_name, sub_names in group_data:
            if sub_names:
                for sub in sub_names:
                    Gui.Selection.addSelection(doc_name, obj_name, sub)
            else:
                Gui.Selection.addSelection(doc_name, obj_name)

    def delete_group(self):
        current_item = self.group_list.currentItem()
        if not current_item: 
            return
        
        name = current_item.text()
        if name in self.saved_groups:
            del self.saved_groups[name]
        self.group_list.takeItem(self.group_list.row(current_item))
