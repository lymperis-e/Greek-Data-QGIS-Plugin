import os

from qgis.PyQt.QtGui import QBrush, QColor, QIcon
from qgis.PyQt.QtWidgets import QHeaderView, QPushButton, QTreeWidgetItem

from ..core.Service import GrdServiceState
from ..core.layer_hierarchy import LayerGroup
from .capabilities_cache import has_capabilities_cache
from .helper_functions import (cache_service_icon, fillServiceLayers,
                               service_qicon, toggle_tree_widget_all)
from .tree_item_roles import (ITEM_KIND_GROUP, ITEM_KIND_LAYER,
                              ITEM_KIND_LAYER_GROUP, ITEM_KIND_SERVICE,
                              ROLE_ITEM_KIND, ROLE_LAYER_INDEX,
                              ROLE_SERVICE_NAME)

_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_loader_icon = os.path.join(_base, "assets/icons/spinner.gif")
_refresh_icon = os.path.join(_base, "assets/icons/refresh_capabilities.svg")
_fetch_icon = os.path.join(_base, "assets/icons/fetch_capabilities.svg")
_add_to_qgis_icon = os.path.join(_base, "assets/icons/add_to_qgs.png")


class ServiceTreeController:
    """Owns all per-service tree-widget UI: column layout, fetch/native buttons,
    lazy capability loading, and state-change reactions."""

    def __init__(self, tree_widget, service_manager, native_datasource_connections, tr):
        self.tree = tree_widget
        self.service_manager = service_manager
        self.native_datasource_connections = native_datasource_connections
        self.tr = tr
        self._setup_columns()

    # ------------------------------------------------------------------
    # Column layout
    # ------------------------------------------------------------------

    def _setup_columns(self):
        # Column 0: name (stretch) | Column 1: Fetch | Column 2: Add-to-QGIS
        self.tree.setColumnCount(3)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.tree.setColumnWidth(1, 26)
        self.tree.setColumnWidth(2, 26)

    # ------------------------------------------------------------------
    # Populate the tree
    # ------------------------------------------------------------------

    def fill(self, reload=False):
        if reload:
            self.service_manager.reloadServices()

        services = self.service_manager.listServices()
        # Sort services alphabetically by name
        services = sorted(services, key=lambda s: (s.name or "").lower())
        self.tree.clear()

        group_nodes = {}
        root = self.tree.invisibleRootItem()
        service_items = []  # Collect service items for button setup after sorting

        for service in services:
            parent = root
            group_path = self._service_group_path(service)

            if group_path:
                segments = [segment.strip() for segment in group_path.split("/") if segment.strip()]
                current_path = []
                for segment in segments:
                    current_path.append(segment)
                    key = "/".join(current_path)
                    group_item = group_nodes.get(key)
                    if group_item is None:
                        group_item = QTreeWidgetItem()
                        group_item.setText(0, segment)
                        group_item.setIcon(0, QIcon.fromTheme("folder"))
                        group_item.setData(0, ROLE_ITEM_KIND, ITEM_KIND_GROUP)
                        parent.addChild(group_item)
                        group_nodes[key] = group_item
                    parent = group_item

            service_item = QTreeWidgetItem()
            service_item.setText(0, service.name)
            service_item.setIcon(0, service_qicon(service))
            service_item.setData(0, ROLE_ITEM_KIND, ITEM_KIND_SERVICE)
            service_item.setData(0, ROLE_SERVICE_NAME, service.name)
            parent.addChild(service_item)
            service_items.append((service_item, service))

            if service.loaded:
                self._populate_loaded_layers(service_item, service, expanded=False)

        # Sort all groups and services alphabetically
        self._sort_tree_items_recursive(self.tree.invisibleRootItem())

        # Set up buttons AFTER sorting to ensure they render properly
        for service_item, service in service_items:
            self._set_fetch_button(service_item, service)
            self._set_native_button(service_item, service)

        # Keep the first grouping level open for discoverability.
        for idx in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(idx)
            if self.is_group_item(item):
                item.setExpanded(True)

    def _service_group_path(self, service):
        config = service.config or {}
        group_path = config.get("group")
        if group_path is None:
            return ""
        return str(group_path).strip()

    def _sort_tree_items_recursive(self, parent_item):
        """Recursively sort all children of a tree item alphabetically by name."""
        # Collect all children with their names
        children_with_names = []
        for idx in range(parent_item.childCount()):
            child = parent_item.child(idx)
            children_with_names.append((child.text(0).lower(), child))

        # Sort by name
        children_with_names.sort(key=lambda x: x[0])

        # Rebuild the children in sorted order
        for sort_idx, (_, child) in enumerate(children_with_names):
            # Qt doesn't have a move method, so we remove and re-add in order
            if parent_item.indexOfChild(child) != sort_idx:
                parent_item.removeChild(child)
                parent_item.insertChild(sort_idx, child)

        # Recursively sort children of each child
        for _, child in children_with_names:
            self._sort_tree_items_recursive(child)

    # ------------------------------------------------------------------
    # Per-item action buttons
    # ------------------------------------------------------------------

    def _item_kind(self, item):
        return item.data(0, ROLE_ITEM_KIND)

    def is_group_item(self, item):
        return item is not None and self._item_kind(item) == ITEM_KIND_GROUP

    def is_service_item(self, item):
        return item is not None and self._item_kind(item) == ITEM_KIND_SERVICE

    def is_layer_item(self, item):
        return item is not None and self._item_kind(item) == ITEM_KIND_LAYER

    def _service_name(self, item):
        return item.data(0, ROLE_SERVICE_NAME) or item.text(0)

    def get_layer_selection(self, item):
        if not self.is_layer_item(item):
            return None, None

        service_name = item.data(0, ROLE_SERVICE_NAME)
        parent = item.parent()
        if not service_name and parent is not None and self.is_service_item(parent):
            service_name = self._service_name(parent)
        if not service_name:
            return None, None

        service = self.service_manager.getService(service_name)
        layer_idx = item.data(0, ROLE_LAYER_INDEX)
        if layer_idx is None:
            layer_idx = parent.indexOfChild(item) if parent is not None else None
        if layer_idx is None:
            return service, None

        return service, service.getLayer(int(layer_idx))

    def filter_services(self, filter_text):
        text = (filter_text or "").strip().lower()
        if text == "":
            toggle_tree_widget_all(self.tree, hidden=False)
            return

        toggle_tree_widget_all(self.tree, hidden=True)

        matched_groups = []
        matched_services = []
        matched_layers = []
        matched_layer_groups = []
        
        for item in self._iter_tree_items():
            name = item.text(0).lower()
            kind = self._item_kind(item)
            if text not in name:
                continue
            if kind == ITEM_KIND_GROUP:
                matched_groups.append(item)
            elif kind == ITEM_KIND_SERVICE:
                matched_services.append(item)
            elif kind == ITEM_KIND_LAYER:
                matched_layers.append(item)
            elif kind == ITEM_KIND_LAYER_GROUP:
                matched_layer_groups.append(item)

        # Show all matched service groups
        for group_item in matched_groups:
            group_item.setHidden(False)

            def show_subtree(node):
                for idx in range(node.childCount()):
                    child = node.child(idx)
                    child.setHidden(False)
                    show_subtree(child)

            show_subtree(group_item)

        # Show all matched services and their children
        for service_item in matched_services:
            service_item.setHidden(False)
            
            def show_subtree(node):
                for idx in range(node.childCount()):
                    child = node.child(idx)
                    child.setHidden(False)
                    show_subtree(child)

            show_subtree(service_item)
            parent = service_item.parent()
            while parent is not None:
                parent.setHidden(False)
                parent = parent.parent()

        # Show matched layer groups and containing parents
        for layer_group_item in matched_layer_groups:
            layer_group_item.setHidden(False)
            
            def show_subtree(node):
                for idx in range(node.childCount()):
                    child = node.child(idx)
                    child.setHidden(False)
                    show_subtree(child)

            show_subtree(layer_group_item)
            parent = layer_group_item.parent()
            while parent is not None:
                parent.setHidden(False)
                parent = parent.parent()

        # Show matched layers and containing parents
        for layer_item in matched_layers:
            layer_item.setHidden(False)
            parent = layer_item.parent()
            while parent is not None:
                parent.setHidden(False)
                parent = parent.parent()

    def _mark_layer_items(self, service_item, service):
        service_name = service.name
        for idx in range(service_item.childCount()):
            child = service_item.child(idx)
            kind = child.data(0, ROLE_ITEM_KIND) if child else None
            if kind == ITEM_KIND_LAYER_GROUP:
                # Recursively mark items in layer groups
                self._mark_layer_items_in_group(child, service_name)
            elif kind == ITEM_KIND_LAYER:
                layer_item = child
                layer_item.setData(0, ROLE_ITEM_KIND, ITEM_KIND_LAYER)
                layer_item.setData(0, ROLE_SERVICE_NAME, service_name)
                layer_item.setData(0, ROLE_LAYER_INDEX, idx)

    def _mark_layer_items_in_group(self, group_item, service_name):
        """Recursively mark layer items within a layer group."""
        for idx in range(group_item.childCount()):
            child = group_item.child(idx)
            kind = child.data(0, ROLE_ITEM_KIND) if child else None
            if kind == ITEM_KIND_LAYER_GROUP:
                # Recurse into nested groups
                self._mark_layer_items_in_group(child, service_name)
            elif kind == ITEM_KIND_LAYER:
                child.setData(0, ROLE_ITEM_KIND, ITEM_KIND_LAYER)
                child.setData(0, ROLE_SERVICE_NAME, service_name)

    def _populate_loaded_layers(self, service_item, service, expanded=True):
        service_item.takeChildren()
        
        # First, try to populate using hierarchical structure if available
        hierarchy = service.get_layer_hierarchy()
        if hierarchy is not None:
            self._populate_layer_hierarchy(service_item, hierarchy, expanded=expanded)
            self._mark_layer_items(service_item, service)
            return
        
        # Fall back to flat layer rendering if no hierarchy exists
        fillServiceLayers(service_item, service, expanded=expanded)
        self._mark_layer_items(service_item, service)

    def _populate_layer_hierarchy(self, parent_item, layer_group, expanded=True):
        """
        Recursively populate tree items from a LayerGroup hierarchy.

        Args:
            parent_item: QTreeWidgetItem to add children to
            layer_group: LayerGroup or Layer object to render
            expanded: Whether to expand the parent item
        """
        if not isinstance(layer_group, LayerGroup):
            return

        for child in layer_group.children:
            if isinstance(child, LayerGroup):
                # Create a folder/group item for nested LayerGroup
                group_item = QTreeWidgetItem()
                group_item.setText(0, child.name)
                group_item.setIcon(0, QIcon.fromTheme("folder"))
                group_item.setData(0, ROLE_ITEM_KIND, ITEM_KIND_LAYER_GROUP)
                parent_item.addChild(group_item)

                # Recursively add children of this group
                self._populate_layer_hierarchy(group_item, child, expanded=expanded)
                group_item.setExpanded(expanded)
            else:
                # It's a Layer object - add it directly
                layer_item = QTreeWidgetItem()
                layer_item.setText(0, child.name)
                layer_item.setIcon(0, QIcon(child.getIcon()))
                layer_item.setToolTip(0, f"{child.name} ({child.type})")
                layer_item.setData(0, ROLE_ITEM_KIND, ITEM_KIND_LAYER)
                parent_item.addChild(layer_item)

        parent_item.setExpanded(expanded)

    def _set_status_text(self, item, text=None):
        base_name = self._service_name(item)
        if text:
            item.setText(0, f"{base_name} ({text})")
            item.setForeground(0, QColor("#e67e22"))
            return

        item.setText(0, base_name)
        item.setForeground(0, QBrush())

    def _set_native_button(self, item, service):
        if not self.is_service_item(item):
            return
        if self.tree.itemWidget(item, 2) is not None:
            return
        button = QPushButton()
        button.setIcon(QIcon(_add_to_qgis_icon))
        button.setFixedWidth(24)
        button.setToolTip(self.tr("Add as native QGIS Browser datasource"))
        button.clicked.connect(
            lambda _, name=service.name: self.native_datasource_connections.add_service_native_datasource(name)
        )
        self.tree.setItemWidget(item, 2, button)

    def _set_fetch_button(self, item, service):
        if not self.is_service_item(item):
            return

        has_cached_capabilities = has_capabilities_cache(service.id)
        if service.loaded and not has_cached_capabilities:
            existing_button = self.tree.itemWidget(item, 1)
            if existing_button is not None:
                self.tree.removeItemWidget(item, 1)
                existing_button.deleteLater()
            return

        existing_button = self.tree.itemWidget(item, 1)
        if existing_button is not None:
            self.tree.removeItemWidget(item, 1)
            existing_button.deleteLater()

        button = QPushButton()
        button.setFixedWidth(24)

        # If capabilities are cached, show a refresh icon that allows the user to force-refresh them.
        if has_cached_capabilities:
            button.setIcon(QIcon.fromTheme("view-refresh", QIcon(_refresh_icon)))
            button.setToolTip(self.tr("Refresh capabilities"))
            button.clicked.connect(
                lambda _, target=item: self.refresh_service_capabilities(target)
            )
        # If not loaded and no cache, show a fetch icon that triggers loading when clicked.
        else:
            button.setIcon(QIcon(_fetch_icon))
            button.setToolTip(self.tr("Fetch capabilities"))
            button.clicked.connect(
                lambda _, target=item: self.fetch_service_capabilities(target)
            )

        self.tree.setItemWidget(item, 1, button)

        button.setEnabled(service.state != GrdServiceState.LOADING)

    def fetch_service_capabilities(self, item):
        if not self.is_service_item(item):
            return
        service = self.service_manager.getService(self._service_name(item))
        service._grdata_pending_action = "fetch"
        self.expand_service(item, fetch_if_needed=True)

    def refresh_service_capabilities(self, item):
        if not self.is_service_item(item):
            return
        service = self.service_manager.getService(self._service_name(item))
        # Force an immediate remote refresh, bypassing normal cache age checks.
        service._grdata_pending_action = "refresh"
        service.loaded = False
        service.updated_at = None
        self.expand_service(item, fetch_if_needed=True, force_refresh=True)

    # ------------------------------------------------------------------
    # Service expansion / lazy loading
    # ------------------------------------------------------------------

    def expand_service(self, item, fetch_if_needed=True, force_refresh=False):
        """Lazy-load a service's layers; optionally trigger a network fetch."""
        if self.is_group_item(item):
            item.setExpanded(True)
            return

        if not self.is_service_item(item):
            return

        if item.childCount() > 0 and not force_refresh:
            item.setExpanded(True)
            return

        name = self._service_name(item)
        icon = item.icon(0)
        service = self.service_manager.getService(name)

        if not fetch_if_needed and not service.loaded:
            self._set_fetch_button(item, service)
            return

        cached_icon_path = cache_service_icon(service)
        if cached_icon_path:
            icon = QIcon(cached_icon_path)
            item.setIcon(0, icon)

        if not service.loaded:
            if not getattr(service, "_grdata_ui_bound", False):
                service.changed.connect(
                    lambda state, srv=service, ready_icon=icon:
                        self._on_service_state_changed(srv, ready_icon, state)
                )
                service._grdata_ui_bound = True

        if service.getLayers() is None:
            self._set_fetch_button(item, service)
            return

        self._populate_loaded_layers(item, service, expanded=True)
        self._set_fetch_button(item, service)

    def _iter_tree_items(self):
        stack = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount() - 1, -1, -1)]
        while stack:
            item = stack.pop()
            if item is None:
                continue
            yield item
            for child_idx in range(item.childCount() - 1, -1, -1):
                stack.append(item.child(child_idx))

    def _find_service_item(self, service):
        for item in self._iter_tree_items():
            if self.is_service_item(item) and self._service_name(item) == service.name:
                return item
        return None

    def _on_service_state_changed(self, service, icon, state):
        item = self._find_service_item(service)
        if item is None:
            return

        if state == GrdServiceState.LOADING:
            action = getattr(service, "_grdata_pending_action", "fetch")
            if action == "refresh":
                self._set_status_text(item, self.tr("Refreshing layers..."))
            else:
                self._set_status_text(item, self.tr("Fetching layers..."))
            item.setIcon(0, QIcon(_loader_icon))
            self._set_fetch_button(item, service)
            return

        if state == GrdServiceState.LOADED:
            service._grdata_pending_action = None
            self._set_status_text(item)
            item.setIcon(0, icon)
            self._populate_loaded_layers(item, service, expanded=True)
            self._set_fetch_button(item, service)
            return

        if state == GrdServiceState.ERROR:
            service._grdata_pending_action = None
            self._set_status_text(item)
            item.setIcon(0, icon)
            self._set_fetch_button(item, service)
