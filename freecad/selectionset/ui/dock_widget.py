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
        
        # State tracking for "Previous Selection"
        self.previous_selection = []
        self.current_selection_state = []
        self._is_restoring = False
        
        # Timer to debounce rapid FreeCAD selection events (like clear -> add)
        self.debounce_timer = QtCore.QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._handle_selection_settled)

        self.tabs = QtWidgets.QTabWidget()
        
        # Move the tabs to the bottom of the widget
        self.tabs.setTabPosition(QtWidgets.QTabWidget.South)
        
        # Apply structural styling (padding, margins, radius) without hardcoding colors
        # so it inherently respects FreeCAD's active dark/light themes. Added QTreeWidget.
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 8px 16px;
                min-width: 100px;
                font-weight: bold;
            }
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
            }
            QListWidget, QTreeWidget {
                border-radius: 4px;
                padding: 4px;
                margin-top: 4px;
            }
        """)
        
        self.setWidget(self.tabs)

        # === TAB 1: CURRENT SELECTION ===
        self.tab_current = QtWidgets.QWidget()
        self.layout_current = QtWidgets.QVBoxLayout(self.tab_current)
        self.layout_current.setContentsMargins(10, 10, 10, 10)
        self.layout_current.setSpacing(8)
        
        self.btn_prev = QtWidgets.QPushButton("Restore Previous Selection")
        self.btn_prev.setEnabled(False)
        self.btn_prev.clicked.connect(self.restore_previous_selection)
        self.layout_current.addWidget(self.btn_prev)
        
        # Replaced QListWidget with QTreeWidget
        self.current_tree = QtWidgets.QTreeWidget()
        self.current_tree.setHeaderHidden(True)
        self.layout_current.addWidget(self.current_tree)
        self.tabs.addTab(self.tab_current, "Current Selection")

        # === TAB 2: SAVED GROUPS ===
        self.tab_saved = QtWidgets.QWidget()
        self.layout_saved = QtWidgets.QVBoxLayout(self.tab_saved)
        self.layout_saved.setContentsMargins(10, 10, 10, 10)
        self.layout_saved.setSpacing(8)

        self.group_list = QtWidgets.QListWidget()
        self.layout_saved.addWidget(self.group_list)

        # Create a horizontal layout for the buttons
        self.buttons_layout = QtWidgets.QHBoxLayout()

        self.btn_save = QtWidgets.QPushButton("Save Current Selection")
        self.btn_save.clicked.connect(self.save_group)
        self.buttons_layout.addWidget(self.btn_save)

        self.btn_restore = QtWidgets.QPushButton("Restore Selection")
        self.btn_restore.clicked.connect(self.restore_group)
        self.buttons_layout.addWidget(self.btn_restore)

        self.btn_delete = QtWidgets.QPushButton("Delete Group")
        self.btn_delete.clicked.connect(self.delete_group)
        self.buttons_layout.addWidget(self.btn_delete)

        # Add the horizontal layout to the tab's main layout
        self.layout_saved.addLayout(self.buttons_layout)

        self.tabs.addTab(self.tab_saved, "Saved Groups")

        # === INITIALIZE OBSERVER ===
        self.observer = SelectionObserver(self.update_current_tab)
        Gui.Selection.addObserver(self.observer)
        self._handle_selection_settled()

    def update_current_tab(self):
        """Triggered by FreeCAD selection events. Debounces rapid changes."""
        if not self._is_restoring:
            self.debounce_timer.start(50)  # Wait 50ms for events to settle

    def _handle_selection_settled(self):
        """Called when selection changes have completed their firing cycle."""
        sel_ex = Gui.Selection.getSelectionEx()
        
        # Enforce tuple for SubElementNames to ensure exact equality checks work
        new_state = [(sel.DocumentName, sel.ObjectName, tuple(sel.SubElementNames)) for sel in sel_ex]

        if new_state != self.current_selection_state:
            # Only save the previous selection if it contained items (prevents losing history on clear)
            if self.current_selection_state: 
                self.previous_selection = self.current_selection_state
            self.current_selection_state = new_state

        if self.isVisible():
            self._populate_current_tree()

    def _populate_current_tree(self):
        """Updates the UI tree for the current selection tab."""
        self.current_tree.clear()
        
        # Dictionary to track parent nodes so we can group cleanly
        # Structure: { "DocName": { "item": QTreeWidgetItem, "objs": { "ObjName": QTreeWidgetItem } } }
        doc_nodes = {}
        
        for doc_name, obj_name, sub_names in self.current_selection_state:
            # 1. Get or create Document Node
            if doc_name not in doc_nodes:
                doc_item = QtWidgets.QTreeWidgetItem(self.current_tree, [doc_name])
                doc_item.setExpanded(True)
                doc_nodes[doc_name] = {'item': doc_item, 'objs': {}}
            
            doc_data = doc_nodes[doc_name]
            
            # 2. Get or create Object Node
            if obj_name not in doc_data['objs']:
                obj_item = QtWidgets.QTreeWidgetItem(doc_data['item'], [obj_name])
                obj_item.setExpanded(True)
                doc_data['objs'][obj_name] = obj_item
                
            obj_item = doc_data['objs'][obj_name]
            
            # 3. Add SubElements (Faces, Edges, Vertices) as leaf nodes
            if sub_names:
                for sub in sub_names:
                    QtWidgets.QTreeWidgetItem(obj_item, [sub])
                    
        self.btn_prev.setEnabled(bool(self.previous_selection))

    def showEvent(self, event):
        """Forces the current selection tab to update the moment the panel is shown."""
        self._populate_current_tree()
        super().showEvent(event)

    def restore_previous_selection(self):
        """Restores the last known valid selection and swaps state to enable toggling."""
        if not self.previous_selection:
            return
            
        self._is_restoring = True
        
        Gui.Selection.clearSelection()
        for doc_name, obj_name, sub_names in self.previous_selection:
            if sub_names:
                for sub in sub_names:
                    Gui.Selection.addSelection(doc_name, obj_name, sub)
            else:
                Gui.Selection.addSelection(doc_name, obj_name)
                
        # Swap current and previous states so the user can repeatedly toggle between the two
        temp = self.current_selection_state
        self.current_selection_state = self.previous_selection
        self.previous_selection = temp
        
        if self.isVisible():
            self._populate_current_tree()
            
        self._is_restoring = False

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
        
        self._is_restoring = True
        Gui.Selection.clearSelection()
        for doc_name, obj_name, sub_names in group_data:
            if sub_names:
                for sub in sub_names:
                    Gui.Selection.addSelection(doc_name, obj_name, sub)
            else:
                Gui.Selection.addSelection(doc_name, obj_name)
                
        # Fire manually since we paused observer callbacks
        self._is_restoring = False
        self.update_current_tab()

    def delete_group(self):
        current_item = self.group_list.currentItem()
        if not current_item: 
            return
        
        name = current_item.text()
        if name in self.saved_groups:
            del self.saved_groups[name]
        self.group_list.takeItem(self.group_list.row(current_item))
