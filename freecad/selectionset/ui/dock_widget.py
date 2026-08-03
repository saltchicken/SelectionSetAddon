import json
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


class HighlightTreeWidget(QtWidgets.QTreeWidget):
    """Custom TreeWidget that clears its selection when losing focus."""
    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        # Clearing selection here triggers the cleanup of the purple highlight 
        # and flawlessly restores the FreeCAD selection so tools work normally.
        self.clearSelection()


class AdvancedSelectionDock(QtWidgets.QDockWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Selection")
        self.setObjectName("AdvancedSelectionDock")
        self.saved_groups = {}

        # State tracking
        self.previous_selection = []
        self.current_selection_state = []
        self._is_restoring = False
        self._observer_active = False
        
        # State tracking for temporary highlight
        self.temp_highlight_name = None
        self._highlight_active = False
        self.shape_cache = {}

        # Timer to debounce rapid FreeCAD selection events
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
        
        # Use our custom tree widget
        self.current_tree = HighlightTreeWidget()
        self.current_tree.setHeaderHidden(True)
        self.current_tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self.group_current.addWidget(self.current_tree)
        
        # Clear Selection Button
        self.btn_clear = QtWidgets.QPushButton("Clear All")
        self.btn_clear.clicked.connect(lambda: Gui.Selection.clearSelection())
        self.group_current.addWidget(self.btn_clear)
        
        self.main_layout.addWidget(self.group_current)

        # --- SECTION 2: SAVED GROUPS ---
        self.group_saved = CollapsibleSection("Saved Groups")
        
        self.group_list = QtWidgets.QListWidget()
        self.group_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.group_list.customContextMenuRequested.connect(self.show_context_menu)
        self.group_list.itemDoubleClicked.connect(lambda: self.restore_group())
        self.group_saved.addWidget(self.group_list)

        # --- SECTION 3: ACTION BUTTONS ---
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

        self.group_saved.addWidget(self.buttons_widget)
        self.main_layout.addWidget(self.group_saved)
        self.main_layout.addStretch()

        # === INITIALIZE OBSERVER ===
        self.observer = SelectionObserver(self.update_current_view)
        self._load_groups()

    # --- Persistence Handlers ---
    def _get_param_group(self):
        return App.ParamGet("User parameter:BaseApp/Preferences/Mod/SelectionSet")

    def _load_groups(self):
        param = self._get_param_group()
        groups_json = param.GetString("SavedGroups", "{}")
        try:
            self.saved_groups = json.loads(groups_json)
            for name in self.saved_groups:
                self.group_list.addItem(name)
        except Exception as e:
            print(f"SelectionSet: Failed to load saved groups - {e}")
            self.saved_groups = {}

    def _save_groups(self):
        param = self._get_param_group()
        param.SetString("SavedGroups", json.dumps(self.saved_groups))

    # --- Highlight Logic ---
    def _clear_highlight(self):
        """Cleans up the temporary purple highlight object."""
        if self.temp_highlight_name:
            doc = App.ActiveDocument
            if doc:
                obj = doc.getObject(self.temp_highlight_name)
                if obj:
                    doc.removeObject(self.temp_highlight_name)
            self.temp_highlight_name = None

    def _restore_real_selection(self):
        """Puts the underlying FreeCAD selection back in place after scrubbing finishes."""
        doc = App.ActiveDocument
        if not doc:
            return
            
        self._is_restoring = True
        Gui.Selection.clearSelection()
        
        for obj_name, sub_names in self.current_selection_state:
            if sub_names:
                for sub in sub_names:
                    Gui.Selection.addSelection(doc.Name, obj_name, sub)
            else:
                Gui.Selection.addSelection(doc.Name, obj_name)
                
        self._is_restoring = False

    def _on_tree_selection_changed(self):
        """Highlights the selected item in the 3D view temporarily."""
        selected_items = self.current_tree.selectedItems()
        
        # Scenario 1: Focus lost or tree clicked empty. Cleanup & restore state.
        if not selected_items:
            self._clear_highlight()
            if self._highlight_active:
                self._restore_real_selection()
                self._highlight_active = False
            return

        # Scenario 2: Item clicked. Hide FreeCAD's selection so purple stands alone.
        if not self._highlight_active:
            self._is_restoring = True
            Gui.Selection.clearSelection()
            self._is_restoring = False
            self._highlight_active = True

        self._clear_highlight()

        item = selected_items[0]
        parent = item.parent()
        if not parent:
            obj_name = item.text(0)
            sub_name = None
        else:
            obj_name = parent.text(0)
            sub_name = item.text(0)

        # Retrieve the exact geometry shape from our cache
        target_shape = self.shape_cache.get((obj_name, sub_name))

        if target_shape:
            doc = App.ActiveDocument
            if not doc:
                return
                
            temp_obj = doc.addObject("Part::Feature", "SelectionHighlight_Temp")
            temp_obj.Label = "SelectionHighlight_Temp"
            
            try:
                temp_obj.Shape = target_shape
            except Exception:
                doc.removeObject(temp_obj.Name)
                return
            
            if hasattr(temp_obj, "ViewObject") and temp_obj.ViewObject:
                temp_obj.ViewObject.Selectable = False
                
                purple = (0.7, 0.0, 1.0)
                temp_obj.ViewObject.LineColor = purple
                temp_obj.ViewObject.PointColor = purple
                temp_obj.ViewObject.ShapeColor = purple
                
                temp_obj.ViewObject.LineWidth = 4.0
                temp_obj.ViewObject.PointSize = 8.0
                temp_obj.ViewObject.Transparency = 20
            
            self.temp_highlight_name = temp_obj.Name

    # --- Lifecycle Hooks to Manage the Observer ---
    def showEvent(self, event):
        if not self._observer_active:
            Gui.Selection.addObserver(self.observer)
            self._observer_active = True
        self._handle_selection_settled()
        super().showEvent(event)

    def hideEvent(self, event):
        self._clear_highlight()
        if self._observer_active:
            Gui.Selection.removeObserver(self.observer)
            self._observer_active = False
        super().hideEvent(event)

    def closeEvent(self, event):
        self._clear_highlight()
        if self._observer_active:
            Gui.Selection.removeObserver(self.observer)
            self._observer_active = False
        super().closeEvent(event)

    # --- Selection Handling ---
    def update_current_view(self):
        if not self._is_restoring:
            self.debounce_timer.start(50)

    def _handle_selection_settled(self):
        self._clear_highlight()
        self._highlight_active = False  # Reset in case selection legitimately changed via 3D view
        
        sel_ex = Gui.Selection.getSelectionEx()
        new_state = [(sel.ObjectName, tuple(sel.SubElementNames)) for sel in sel_ex]

        if new_state != self.current_selection_state:
            if self.current_selection_state:
                self.previous_selection = self.current_selection_state
            self.current_selection_state = new_state

        if self.isVisible():
            self._populate_current_tree()

    def _populate_current_tree(self):
        self.current_tree.itemSelectionChanged.disconnect(self._on_tree_selection_changed)
        self.current_tree.clear()
        self.shape_cache.clear()
        
        obj_nodes = {}
        sel_ex = Gui.Selection.getSelectionEx()

        for sel in sel_ex:
            obj_name = sel.ObjectName
            if obj_name not in obj_nodes:
                obj_item = QtWidgets.QTreeWidgetItem(self.current_tree, [obj_name])
                obj_item.setExpanded(True)
                obj_nodes[obj_name] = obj_item
                
                if hasattr(sel.Object, "Shape"):
                    self.shape_cache[(obj_name, None)] = sel.Object.Shape

            obj_item = obj_nodes[obj_name]

            if sel.HasSubObjects:
                for idx, sub_name in enumerate(sel.SubElementNames):
                    QtWidgets.QTreeWidgetItem(obj_item, [sub_name])
                    if len(sel.SubObjects) > idx:
                        self.shape_cache[(obj_name, sub_name)] = sel.SubObjects[idx]

        self.btn_prev.setEnabled(bool(self.previous_selection))
        self.current_tree.itemSelectionChanged.connect(self._on_tree_selection_changed)

    # --- Selection State Restorations ---
    def _apply_selection_state(self, state_data):
        doc = App.ActiveDocument
        if not doc:
            QtWidgets.QMessageBox.warning(self, "No Document", "No active document found to restore selection.")
            return False

        self._is_restoring = True
        Gui.Selection.clearSelection()

        for obj_name, sub_names in state_data:
            if not doc.getObject(obj_name):
                print(f"SelectionSet: Object '{obj_name}' missing in active document. Skipping.")
                continue

            if sub_names:
                for sub in sub_names:
                    Gui.Selection.addSelection(doc.Name, obj_name, sub)
            else:
                Gui.Selection.addSelection(doc.Name, obj_name)

        self._is_restoring = False
        self.update_current_view()
        return True

    def restore_previous_selection(self):
        if not self.previous_selection:
            return

        if self._apply_selection_state(self.previous_selection):
            temp = self.current_selection_state
            self.current_selection_state = self.previous_selection
            self.previous_selection = temp

    # --- Saved Groups Logic ---
    def save_group(self):
        sel_ex = Gui.Selection.getSelectionEx()
        if not sel_ex:
            QtWidgets.QMessageBox.warning(self, "Empty Selection", "Select something first.")
            return

        name, ok = QtWidgets.QInputDialog.getText(self, "Save Selection", "Enter group name:")
        if ok and name:
            group_data = [(sel.ObjectName, tuple(sel.SubElementNames)) for sel in sel_ex]
            if name not in self.saved_groups:
                self.group_list.addItem(name)
            self.saved_groups[name] = group_data
            self._save_groups()

    def restore_group(self):
        current_item = self.group_list.currentItem()
        if not current_item:
            return

        name = current_item.text()
        group_data = self.saved_groups.get(name, [])
        self._apply_selection_state(group_data)

    # --- Context Menu Handling ---
    def show_context_menu(self, position):
        item = self.group_list.itemAt(position)
        if not item:
            return

        menu = QtWidgets.QMenu()
        rename_action = menu.addAction("Rename")
        update_action = menu.addAction("Update with Current Selection")
        delete_action = menu.addAction("Delete")

        action = menu.exec_(self.group_list.mapToGlobal(position))

        if action == rename_action:
            self.rename_group_item(item)
        elif action == update_action:
            self.update_group_item(item)
        elif action == delete_action:
            self.delete_group_item(item)

    def rename_group_item(self, item):
        old_name = item.text()
        new_name, ok = QtWidgets.QInputDialog.getText(self, "Rename Group", "New name:", text=old_name)
        if ok and new_name and new_name != old_name:
            self.saved_groups[new_name] = self.saved_groups.pop(old_name)
            item.setText(new_name)
            self._save_groups()

    def update_group_item(self, item):
        sel_ex = Gui.Selection.getSelectionEx()
        if not sel_ex:
            QtWidgets.QMessageBox.warning(self, "Empty Selection", "Make a selection in FreeCAD first to update this group.")
            return
            
        name = item.text()
        group_data = [(sel.ObjectName, tuple(sel.SubElementNames)) for sel in sel_ex]
        self.saved_groups[name] = group_data
        print(f"SelectionSet: Updated group '{name}' with current selection.")
        self._save_groups()

    def delete_group_item(self, item):
        name = item.text()
        if name in self.saved_groups:
            del self.saved_groups[name]
        self.group_list.takeItem(self.group_list.row(item))
        self._save_groups()
