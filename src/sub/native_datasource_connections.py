from urllib.parse import urlsplit, urlunsplit

from qgis.core import Qgis, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QMenu


class NativeDatasourceConnections:
    def __init__(self, iface, service_manager, tr):
        self.iface = iface
        self.service_manager = service_manager
        self.tr = tr

    def configure_tree_widget(self, tree_widget):
        tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        tree_widget.customContextMenuRequested.connect(
            lambda position: self.show_connections_context_menu(tree_widget, position)
        )

    def _sanitize_connection_name(self, value: str) -> str:
        for c in ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]:
            value = value.replace(c, "-")
        return " ".join(value.split()).strip()

    def _strip_query_and_fragment(self, url: str) -> str:
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))

    def _save_native_connection(self, provider: str, conn_name: str, **values):
        # QgsSettings is profile-aware and writes to the active QGIS profile ini.
        settings = QgsSettings()

        stale_groups_by_provider = {
            "wms": [f"connections/WMS/{conn_name}", f"WMS/{conn_name}"],
            "wfs": [f"connections/WFS/{conn_name}", f"WFS/{conn_name}"],
            "arcgisfeatureserver": [
                f"ARCGISFEATURESERVER/{conn_name}",
                f"connections/ARCGISFEATURESERVER/{conn_name}",
            ],
            "arcgismapserver": [
                f"ARCGISMAPSERVER/{conn_name}",
                f"connections/ARCGISMAPSERVER/{conn_name}",
            ],
        }
        for stale_group in stale_groups_by_provider.get(provider, []):
            settings.remove(stale_group)
        modern_defaults_by_provider = {
            "wms": {
                "authcfg": "",
                "dpi-mode": 7,
                "http-header": {},
                "ignore-axis-orientation": False,
                "ignore-get-feature-info-uri": False,
                "ignore-get-map-uri": False,
                "invert-axis-orientation": False,
                "password": "",
                "reported-layer-extents": False,
                "smooth-pixmap-transform": False,
                "tile-pixel-ratio": 0,
                "username": "",
            },
            "wfs": {
                "authcfg": "",
                "ignore-axis-orientation": False,
                "invert-axis-orientation": False,
                "max-num-features": "",
                "page-size": "",
                "paging-enabled": True,
                "password": "",
                "prefer-coordinates-for-wfs-T11": False,
                "username": "",
                "version": "auto",
            },
            "xyz": {
                "authcfg": "",
                "hidden": False,
                "http-header": {},
                "interpretation": "",
                "password": "",
                "tile-pixel-ratio": 0,
                "username": "",
                "zmax": -1,
                "zmin": -1,
            },
            "arcgisfeatureserver": {
                "authcfg": "",
                "community-endpoint": "",
                "content-endpoint": "",
                "http-header": {},
                "password": "",
                "username": "",
            },
            "arcgismapserver": {
                "authcfg": "",
                "community-endpoint": "",
                "content-endpoint": "",
                "http-header": {},
                "password": "",
                "username": "",
            },
        }

        modern_group_by_provider = {
            "wms": f"connections/ows/items/wms/connections/items/{conn_name}",
            "wfs": f"connections/ows/items/wfs/connections/items/{conn_name}",
            "xyz": f"connections/xyz/items/{conn_name}",
            "arcgisfeatureserver": f"connections/arcgisfeatureserver/items/{conn_name}",
            "arcgismapserver": f"connections/arcgismapserver/items/{conn_name}",
        }

        modern_values = dict(modern_defaults_by_provider.get(provider, {}))
        modern_values.update(values)

        modern_group = modern_group_by_provider.get(provider)
        if modern_group:
            settings.beginGroup(modern_group)
            try:
                for key, value in modern_values.items():
                    settings.setValue(key, value)
            finally:
                settings.endGroup()

            # Keep the latest connection selected in the source selector dialogs.
            selected_group_by_provider = {
                "wms": "connections/ows/items/wms/connections",
                "wfs": "connections/ows/items/wfs/connections",
                "xyz": "connections/xyz",
                "arcgisfeatureserver": "connections/arcgisfeatureserver",
                "arcgismapserver": "connections/arcgismapserver",
            }
            selected_group = selected_group_by_provider.get(provider)
            if selected_group:
                settings.setValue(f"{selected_group}/selected", conn_name)

        # Also write legacy keys for compatibility with existing profiles.
        legacy_group = f"connections-{provider}/{conn_name}"
        settings.beginGroup(legacy_group)
        try:
            for key, value in values.items():
                settings.setValue(key, value)
        finally:
            settings.endGroup()

        settings.sync()

    def show_connections_context_menu(self, tree_widget, position):
        item = tree_widget.itemAt(position)
        if item is None:
            return

        # Only show the action on top-level service rows, not on layer children
        if item.parent() is not None:
            return

        service_name = item.text(0)

        menu = QMenu(tree_widget)
        add_action = menu.addAction(self.tr("Add As Native QGIS Browser Datasource"))
        add_action.triggered.connect(
            lambda _, name=service_name: self.add_service_native_datasource(name)
        )

        menu.exec_(tree_widget.viewport().mapToGlobal(position))

    def add_service_native_datasource(self, service_name: str):
        service = self.service_manager.getService(service_name)
        base_name = self._sanitize_connection_name(f"grData - {service.name}")
        clean_url = self._strip_query_and_fragment(service.url.rstrip("/"))

        created_connections = []

        if service.type == "ogc":
            self._save_native_connection(
                "wms",
                base_name,
                url=clean_url,
            )
            self._save_native_connection(
                "wfs",
                base_name,
                url=clean_url,
            )
            created_connections.extend(["WMS", "WFS"])

        elif service.type == "esri":
            self._save_native_connection(
                "arcgismapserver",
                base_name,
                url=clean_url,
            )
            self._save_native_connection(
                "arcgisfeatureserver",
                base_name,
                url=clean_url,
            )
            created_connections.extend(["ArcGIS MapServer", "ArcGIS FeatureServer"])

        elif (
            service.type == "xyz"
            or "{x}" in service.url.lower()
            and "{y}" in service.url.lower()
            and "{z}" in service.url.lower()
        ):
            self._save_native_connection(
                "xyz",
                base_name,
                url=service.url,
                zmin=0,
                zmax=22,
            )
            created_connections.append("XYZ")

        if len(created_connections) == 0:
            self.iface.messageBar().pushMessage(
                "grData",
                f"Unsupported datasource type for service '{service.name}'",
                level=Qgis.Warning,
                duration=5,
            )
            return

        if hasattr(self.iface, "reloadConnections"):
            self.iface.reloadConnections()

        self.iface.messageBar().pushMessage(
            "grData",
            f"Added native datasource connection(s): {', '.join(created_connections)}",
            level=Qgis.Success,
            duration=5,
        )
