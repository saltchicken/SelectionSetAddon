import FreeCAD as App
import FreeCADGui as Gui

try:
    from PySide6 import QtCore
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtCore
    from PySide2 import QtWidgets


class SelectionObserver:

    def __init__(self, update_callback):
        self.update_callback = update_callback

    def addSelection(self, *args):
        self.update_callback()

    def removeSelection(self, *args):
        self.update_callback()

    def setSelection(self, *args):
        self.update_callback()

    def clearSelection(self, *args):
        self.update_callback()


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

        # --- Main Layout Setup ---
        self.main_widget = QtWidgets.QWidget()
        self.main_layout = QtWidgets.QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(12)

        # Apply structural styling
        self.main_widget.setStyleSheet("""
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

        self.setWidget(self.main_widget)

        # --- SECTION 1: CURRENT SELECTION ---
        self.group_current = QtWidgets.QGroupBox("Current Selection")

        # Make the header clickable (toggleable) and default to shown
        self.group_current.setCheckable(True)
        self.group_current.setChecked(True)

        self.layout_current = QtWidgets.QVBoxLayout(self.group_current)
        self.layout_current.setContentsMargins(8, 12, 8, 8)
        self.layout_current.setSpacing(8)

        self.current_tree = QtWidgets.QTreeWidget()
        self.current_tree.setHeaderHidden(True)
        self.layout_current.addWidget(self.current_tree)

        self.main_layout.addWidget(self.group_current)

        # Connect the header toggle to hide/show the tree widget
        self.group_current.toggled.connect(self.current_tree.setVisible)

        # --- SECTION 2: SAVED GROUPS ---
        self.group_saved = QtWidgets.QGroupBox("Saved Groups")

        # Make the header clickable (toggleable) and default to shown (checked)
        self.group_saved.setCheckable(True)
        self.group_saved.setChecked(True)

        self.layout_saved = QtWidgets.QVBoxLayout(self.group_saved)
        self.layout_saved.setContentsMargins(8, 12, 8, 8)
        self.layout_saved.setSpacing(8)

        self.group_list = QtWidgets.QListWidget()
        self.layout_saved.addWidget(self.group_list)

        self.main_layout.addWidget(self.group_saved)

        # --- SECTION 3: ACTION BUTTONS ---
        # Wrap the layout in a QWidget so we can toggle its visibility
        self.buttons_widget = QtWidgets.QWidget()
        self.buttons_layout = QtWidgets.QHBoxLayout(self.buttons_widget)
        self.buttons_layout.setContentsMargins(0, 0, 0,
                                               0)  # No extra margin needed

        self.btn_prev = QtWidgets.QPushButton("Restore Prev")
        self.btn_prev.setEnabled(False)
        self.btn_prev.clicked.connect(self.restore_previous_selection)
        self.buttons_layout.addWidget(self.btn_prev)

        self.btn_save = QtWidgets.QPushButton("Save Current")
        self.btn_save.clicked.connect(self.save_group)
        self.buttons_layout.addWidget(self.btn_save)

        self.btn_restore = QtWidgets.QPushButton("Restore")
        self.btn_restore.clicked.connect(self.restore_group)
        self.buttons_layout.addWidget(self.btn_restore)

        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_delete.clicked.connect(self.delete_group)
        self.buttons_layout.addWidget(self.btn_delete)

        # Add the unified button widget to the very bottom of the dock
        self.main_layout.addWidget(self.buttons_widget)

        # Connect the header click event to hide/show both the list and the buttons widget
        self.group_saved.toggled.connect(self.group_list.setVisible)
        self.group_saved.toggled.connect(self.buttons_widget.setVisible)

        # === INITIALIZE OBSERVER ===
        self.observer = SelectionObserver(self.update_current_view)
        Gui.Selection.addObserver(self.observer)
        self._handle_selection_settled()

    def update_current_view(self):
        """Triggered by FreeCAD selection events. Debounces rapid changes."""
        if not self._is_restoring:
            self.debounce_timer.start(50)  # Wait 50ms for events to settle

    def _handle_selection_settled(self):
        """Called when selection changes have completed their firing cycle."""
        sel_ex = Gui.Selection.getSelectionEx()

        # Enforce tuple for SubElementNames to ensure exact equality checks work
        new_state = [(sel.DocumentName, sel.ObjectName,
                      tuple(sel.SubElementNames)) for sel in sel_ex]

        if new_state != self.current_selection_state:
            # Only save the previous selection if it contained items (prevents losing history on clear)
            if self.current_selection_state:
                self.previous_selection = self.current_selection_state
            self.current_selection_state = new_state

        if self.isVisible():
            self._populate_current_tree()

    def _populate_current_tree(self):
        """Updates the UI tree for the current selection."""
        self.current_tree.clear()

        # Dictionary to track parent nodes so we can group cleanly
        # Structure: { "DocName": { "item": QTreeWidgetItem, "objs": { "ObjName": QTreeWidgetItem } } }
        doc_nodes = {}

        for doc_name, obj_name, sub_names in self.current_selection_state:
            # 1. Get or create Document Node
            if doc_name not in doc_nodes:
                doc_item = QtWidgets.QTreeWidgetItem(self.current_tree,
                                                     [doc_name])
                doc_item.setExpanded(True)
                doc_nodes[doc_name] = {'item': doc_item, 'objs': {}}

            doc_data = doc_nodes[doc_name]

            # 2. Get or create Object Node
            if obj_name not in doc_data['objs']:
                obj_item = QtWidgets.QTreeWidgetItem(doc_data['item'],
                                                     [obj_name])
                obj_item.setExpanded(True)
                doc_data['objs'][obj_name] = obj_item

            obj_item = doc_data['objs'][obj_name]

            # 3. Add SubElements (Faces, Edges, Vertices) as leaf nodes
            if sub_names:
                for sub in sub_names:
                    QtWidgets.QTreeWidgetItem(obj_item, [sub])

        self.btn_prev.setEnabled(bool(self.previous_selection))

    def showEvent(self, event):
        """Forces the current selection view to update the moment the panel is shown."""
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
            QtWidgets.QMessageBox.warning(self, "Empty Selection",
                                          "Select something first.")
            return

        name, ok = QtWidgets.QInputDialog.getText(self, "Save Selection",
                                                  "Enter group name:")
        if ok and name:
            group_data = [(sel.DocumentName, sel.ObjectName,
                           sel.SubElementNames) for sel in sel_ex]
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
        self.update_current_view()

    def delete_group(self):
        current_item = self.group_list.currentItem()
        if not current_item:
            return

        name = current_item.text()
        if name in self.saved_groups:
            del self.saved_groups[name]
        self.group_list.takeItem(self.group_list.row(current_item))
