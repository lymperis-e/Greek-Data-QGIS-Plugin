import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QHeaderView, QPushButton

from ..core.Service import GrdServiceState
from .helper_functions import (cache_service_icon, fillServiceLayers,
                               fillServices)

_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_loader_icon = os.path.join(_base, "assets/icons/spinner.gif")
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
        # Column 0: name (stretch)  |  Column 1: Fetch  |  Column 2: Add-to-QGIS
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
            self._set_fetch_button(item, service)
            self._set_native_button(item, service)

    # ------------------------------------------------------------------
    # Per-item action buttons
    # ------------------------------------------------------------------

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
        if service.loaded:
            self.tree.removeItemWidget(item, 1)
            return

        button = self.tree.itemWidget(item, 1)
        if not isinstance(button, QPushButton):
            button = QPushButton()
            button.setIcon(QIcon(_fetch_icon))
            button.setFixedWidth(24)
            button.setToolTip(self.tr("Fetch capabilities"))
            button.clicked.connect(
                lambda _, target=item: self.expand_service(target, fetch_if_needed=True)
            )
            self.tree.setItemWidget(item, 1, button)

        button.setEnabled(service.state != GrdServiceState.LOADING)

    # ------------------------------------------------------------------
    # Service expansion / lazy loading
    # ------------------------------------------------------------------

    def expand_service(self, item, fetch_if_needed=True):
        """Lazy-load a service's layers; optionally trigger a network fetch."""
        if item.childCount() > 0:
            item.setExpanded(True)
            return

        name = item.text(0)
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
                    lambda state, tree_item=item, srv=service, ready_icon=icon:
                        self._on_service_state_changed(tree_item, srv, ready_icon, state)
                )
                service._grdata_ui_bound = True

        if service.getLayers() is None:
            self._set_fetch_button(item, service)
            return

        fillServiceLayers(item, service)
        self._set_fetch_button(item, service)

    def _on_service_state_changed(self, item, service, icon, state):
        if state == GrdServiceState.LOADING:
            item.setIcon(0, QIcon(_loader_icon))
            self._set_fetch_button(item, service)
            return

        if state == GrdServiceState.LOADED:
            item.setIcon(0, icon)
            if item.childCount() == 0:
                fillServiceLayers(item, service, expanded=True)
            self._set_fetch_button(item, service)
            return

        if state == GrdServiceState.ERROR:
            item.setIcon(0, icon)
            self._set_fetch_button(item, service)
