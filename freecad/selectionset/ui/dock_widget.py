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


class CollapsibleSection(QtWidgets.QWidget):
    """A professional collapsible widget using standard Qt arrows."""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # The header toggle button
        self.toggle_button = QtWidgets.QToolButton(self)
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(QtCore.Qt.DownArrow)
        
        # Make the button span the entire width
        self.toggle_button.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Fixed)
        self.toggle_button.setStyleSheet("""
            QToolButton {
                border: none;
                font-weight: bold;
                padding: 6px;
                text-align: left;
                background-color: transparent;
            }
            QToolButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
                border-radius: 4px;
            }
        """)

        # The container for the actual content
        self.content_area = QtWidgets.QWidget(self)
        self.content_layout = QtWidgets.QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(8, 4, 8, 8)
        self.content_layout.setSpacing(8)

        self.layout.addWidget(self.toggle_button)
        self.layout.addWidget(self.content_area)

        self.toggle_button.toggled.connect(self.on_toggled)

    def on_toggled(self, checked):
        # Swap the arrow direction and toggle content visibility
        self.toggle_button.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)
        self.content_area.setVisible(checked)

    def addWidget(self, widget):
        self.content_layout.addWidget(widget)


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
        self.group_current = CollapsibleSection("Current Selection")
        
        self.current_tree = QtWidgets.QTreeWidget()
        self.current_tree.setHeaderHidden(True)
        self.group_current.addWidget(self.current_tree)
        
        self.main_layout.addWidget(self.group_current)

        # --- SECTION 2: SAVED GROUPS ---
        self.group_saved = CollapsibleSection("Saved Groups")
        
        self.group_list = QtWidgets.QListWidget()
        self.group_saved.addWidget(self.group_list)

        # --- SECTION 3: ACTION BUTTONS ---
        # Wrap the layout in a QWidget so we can add it to the collapsible section
        self.buttons_widget = QtWidgets.QWidget()
        self.buttons_layout = QtWidgets.QHBoxLayout(self.buttons_widget)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)

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

        # Add the unified button widget to the Saved Groups section
        self.group_saved.addWidget(self.buttons_widget)
        
        self.main_layout.addWidget(self.group_saved)

        # Push everything to the top when space allows
        self.main_layout.addStretch()

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
