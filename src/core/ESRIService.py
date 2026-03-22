from typing import Dict, List, Union

import requests
from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsTask
from qgis.PyQt.QtCore import pyqtSignal

from ..sub.logger import LOGGER_CATEGORY
from .Layer import Layer
from .layer_hierarchy import LayerGroup, build_hierarchy_from_flat_with_paths
from .Service import GrdService


def clean_esri_attributes(layer_attributes: Dict[str, str]) -> None:
    """
    Modify the layer attributes in place, to remove the "domain" key from the "fields" key, but keep the "domain.description" key
    """
    if not layer_attributes:
        return None

    fields = layer_attributes.get("fields", None)
    if fields is None:
        return layer_attributes

    for field in fields:
        if field.get("domain", None) is not None:
            field["description"] = field["domain"].get("description", None)
            field.pop("domain", None)

    layer_attributes["fields"] = fields

    return layer_attributes


def filter_esri_attributes(attributes: Dict[str, str]) -> Dict[str, str]:
    """
    Only keep desired attributes:
        - extent
        - fields
        - geometryType
        - name
        - type
        - description
        - copyrightText
    """
    return {
        attr: attributes[attr]
        for attr in [
            "extent",
            "fields",
            "geometryType",
            "name",
            "type",
            "description",
            "copyrightText",
        ]
        if attr in attributes
    }


class LoadEsriAsync(QgsTask):
    """
    Asynchronously query an ArcGIS server for available services, using a QgsTask
    """

    loaded = pyqtSignal(list)

    def __init__(self, url):
        super().__init__(f"Loading from {url} (ESRI server)", QgsTask.CanCancel)

        self.url = url
        self.capabilities = dict()
        self.layers = list()
        self.layer_paths = dict()  # Map layer id -> path string for hierarchy
        self.exception = None

    def _get(self, url):
        url = url.rstrip("/")

        # Query the REST endpoint
        payload = {"f": "json"}
        response = requests.get(
            url,
            params=payload,
            headers={"user-agent": "grdata-qgis-plugin/1.0.0"},
            timeout=10,
            allow_redirects=True,
            cookies=None,
        ).json()

        if "error" in response:
            self.exception = Exception(response)
            return None

        return response

    def query_esri_server(self, url, parent_type=None, path_prefix="") -> Dict[str, Dict[str, str]]:
        """
        Recursively query ESRI server.

        Args:
            url: Service URL to query
            parent_type: Service type (Map/Image/Feature)
            path_prefix: Current path in hierarchy (e.g., "Folder A/Folder B")

        Returns:
            Dict of discovered resources at this level
        """
        folders_to_exclude = [
            "Basemap",
            "Utilities",
            "Thematic_Map",
            "TEST_DXF2GDB_SERVICE",
            "temp",
            "PrintLayouts",
            "DIONYSIS",
        ]

        response = self._get(url)
        if response is None:
            return None

        # Initialize the dictionary for this level of the directory
        service_layers = dict()

        # Add any services at this level of the directory to the dictionary
        for service in response.get("services", list()):
            service_name = service["name"].split("/")[-1]
            service_type = service["type"]
            service_url = f"{url}/{service_name}/{service_type}"
            service_path = f"{path_prefix}/{service_name}" if path_prefix else service_name

            _service_layers = self.query_esri_server(service_url, service_type, service_path)
            if not _service_layers:
                continue
            service_layers.update(_service_layers)

            service_layers[service_name] = {
                "name": service_name,
                "type": service_type,
                "url": service_url,
                "layers": service_layers,
            }

        # Recursively add any subdirectories and layers to the dictionary
        for folder in response.get("folders", list()):
            if folder in folders_to_exclude:
                continue
            folder_url = f"{url}/{folder}"
            folder_path = f"{path_prefix}/{folder}" if path_prefix else folder
            folder_dict = self.query_esri_server(folder_url, folder, folder_path)
            if folder_dict:
                service_layers[folder] = folder_dict

        # Add any layers for this service to the dictionary
        for layer in response.get("layers", list()):
            layer_id = int(layer["id"])
            layer_name = layer["name"]
            layer_url = f"{url}/{layer_id}"

            layer_attributes = self._get(layer_url)

            try:
                _filtered_attrs = filter_esri_attributes(layer_attributes)
                _cleaned_attrs = clean_esri_attributes(_filtered_attrs)

            except Exception as e:
                self.exception = e
                QgsMessageLog.logMessage(
                    f"[ESRIService/Loader] Tried to clean fields for layer {layer_name} but failed: {e}",
                    LOGGER_CATEGORY,
                    Qgis.Warning,
                )

            service_layers[layer_id] = {
                "id": layer_id,
                "name": layer_name,
                "url": layer_url,
                "type": parent_type,
                "attributes": _cleaned_attrs,
                "geometryType": _cleaned_attrs.get("geometryType", None),
                "extent": _cleaned_attrs.get("extent", None),
            }

            layer_dict = {
                "id": layer_id,
                "name": layer_name,
                "url": layer_url,
                "type": parent_type,
                "attributes": _cleaned_attrs,
                "geometryType": _cleaned_attrs.get("geometryType", None),
                "extent": _cleaned_attrs.get("extent", None),
            }

            self.layers.append(layer_dict)
            
            # Track the path for this layer to rebuild hierarchy later
            layer_path = f"{path_prefix}/{layer_name}" if path_prefix else layer_name
            self.layer_paths[layer_id] = layer_path

        return service_layers

    def run(self):
        self.capabilities = self.query_esri_server(self.url)
        if self.isCanceled():
            return False
        return True

    def finished(self, result):
        # Success
        if result:
            self.loaded.emit(self.layers)
            QgsMessageLog.logMessage(
                f"[ESRIService/Loader] Succesfully loaded {self.url} (ESRI server)",
                LOGGER_CATEGORY,
                Qgis.Success,
            )
            return

        # Cancelled
        if self.exception is None:
            self.loaded.emit(self.layers)
            QgsMessageLog.logMessage(
                f'[ESRIService/Loader] Request "{self.description()}" not successful but without '
                "exception (probably the task was manually "
                "canceled by the user)",
                LOGGER_CATEGORY,
                Qgis.Warning,
            )
            return

        # Error
        QgsMessageLog.logMessage(
            f"[ESRIService/Loader] Error while loading {self.url} (ESRI server): {self.exception}.",
            LOGGER_CATEGORY,
            Qgis.Critical,
        )


ESRI_GEOMTRY_TYPES = [
    None,  # raster
    "esriGeometryPoint",
    "esriGeometryMultipoint",
    "esriGeometryPolyline",
    "esriGeometryPolygon",
    "esriGeometryEnvelope",
]


class ESRIService(GrdService):
    def __init__(self, name, url, *args, **kwargs) -> GrdService:
        super().__init__(
            name=name,
            url=url,
            service_type="esri",
            loaded=False,
            *args,
            **kwargs,
        )

        self.tm = QgsApplication.taskManager()

    def _layerDataModel(self, layer: Dict[str, str]) -> str:
        if layer["type"] == "MapServer" or layer["type"] == "esri-raster":
            return "esri-raster"
        if layer["type"] == "FeatureServer" or layer["type"] == "esri-vector":
            return "esri-vector"
        return None

    def _layerGeometryType(self, layer: Dict[str, str]) -> str:
        return layer["attributes"].get("geometryType", None)

    def _getRemoteCapabilities(self) -> Dict:
        self._current_esri_task = LoadEsriAsync(self.url)
        self._current_esri_task.loaded.connect(self._on_esri_layers_loaded)
        self.tm.addTask(self._current_esri_task)

    def _on_esri_layers_loaded(self, layers: List) -> None:
        """Handler for ESRI layers loaded signal. Builds hierarchy and calls _setupLayers."""
        # Build hierarchical structure from flat layers and layer_paths
        hierarchy = None
        if hasattr(self, "_current_esri_task") and self._current_esri_task:
            layer_paths = self._current_esri_task.layer_paths
            if layer_paths:
                # Reconstruct Layer objects for hierarchy building
                layer_objs = []
                for layer_dict in layers:
                    layer = Layer(
                        idx=layer_dict.get("id", 0),
                        url=layer_dict.get("url", ""),
                        name=layer_dict.get("name", ""),
                        data_model=layer_dict.get("type", ""),
                        attributes=layer_dict.get("attributes", {}),
                        geometry_type=layer_dict.get("geometryType"),
                    )
                    layer_objs.append(layer)

                hierarchy = build_hierarchy_from_flat_with_paths(layer_objs, layer_paths)

        # Call _setupLayers with both flat layers and hierarchy
        self._setupLayers(layers, export_conf=True, layer_structure=hierarchy)
