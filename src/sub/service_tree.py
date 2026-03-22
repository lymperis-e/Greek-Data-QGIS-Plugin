import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QBrush, QColor, QIcon
from qgis.PyQt.QtWidgets import QHeaderView, QPushButton

from ..core.Service import GrdServiceState
from .capabilities_cache import has_capabilities_cache
from .helper_functions import (cache_service_icon, fillServiceLayers,
                               fillServices)

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
        self.tree.clear()
        fillServices(self.tree, services)

        for idx in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(idx)
            service = self.service_manager.getService(item.text(0))
            item.setData(0, Qt.UserRole, service.name)
            self._set_fetch_button(item, service)
            self._set_native_button(item, service)

    # ------------------------------------------------------------------
    # Per-item action buttons
    # ------------------------------------------------------------------

    def _service_name(self, item):
        return item.data(0, Qt.UserRole) or item.text(0)

    def _set_status_text(self, item, text=None):
        base_name = self._service_name(item)
        if text:
            item.setText(0, f"{base_name} ({text})")
            item.setForeground(0, QColor("#e67e22"))
            return

        item.setText(0, base_name)
        item.setForeground(0, QBrush())

    def _set_native_button(self, item, service):
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
        service = self.service_manager.getService(self._service_name(item))
        service._grdata_pending_action = "fetch"
        self.expand_service(item, fetch_if_needed=True)

    def refresh_service_capabilities(self, item):
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

        fillServiceLayers(item, service)
        self._set_fetch_button(item, service)

    def _find_service_item(self, service):
        for idx in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(idx)
            if item is None:
                continue
            if self._service_name(item) == service.name:
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
            item.takeChildren()
            fillServiceLayers(item, service, expanded=True)
            self._set_fetch_button(item, service)
            return

        if state == GrdServiceState.ERROR:
            service._grdata_pending_action = None
            self._set_status_text(item)
            item.setIcon(0, icon)
            self._set_fetch_button(item, service)
