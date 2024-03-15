from typing import Dict, List, Union

import requests
from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsTask
from qgis.PyQt.QtCore import pyqtSignal

from .Layer import Layer
from .Service import GrdService

MESSAGE_CATEGORY = "GreekData-GetCapabilities (ArcGIS server)"


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

    def query_esri_server(self, url, parent_type=None) -> Dict[str, Dict[str, str]]:
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

            _service_layers = self.query_esri_server(service_url, service_type)
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
            folder_dict = self.query_esri_server(folder_url, folder)
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
                    f"Tried to clean fields for layer {layer_name} but failed: {e}",
                    MESSAGE_CATEGORY,
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

            self.layers.append(
                {
                    "id": layer_id,
                    "name": layer_name,
                    "url": layer_url,
                    "type": parent_type,
                    "attributes": _cleaned_attrs,
                    "geometryType": _cleaned_attrs.get("geometryType", None),
                    "extent": _cleaned_attrs.get("extent", None),
                }
            )

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
                f"Succesfully loaded {self.url} (ESRI server)",
                MESSAGE_CATEGORY,
                Qgis.Success,
            )
            return

        # Cancelled
        if self.exception is None:
            self.loaded.emit(self.layers)
            QgsMessageLog.logMessage(
                f'Request "{self.description()}" not successful but without '
                "exception (probably the task was manually "
                "canceled by the user)",
                MESSAGE_CATEGORY,
                Qgis.Warning,
            )
            return

        # Error
        QgsMessageLog.logMessage(
            f"Error while loading {self.url} (ESRI server): {self.exception}.",
            MESSAGE_CATEGORY,
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
            capabilities=dict(),
            available_layers=list(),
            layers=list(),
            *args,
            **kwargs,
        )

        self.tm = QgsApplication.taskManager()

    def _getLayerType(self, layer: Dict[str, str]) -> str:
        if layer["type"] == "MapServer" or layer["type"] == "esri-map":
            return "esri-map"
        if layer["type"] == "FeatureServer" or layer["type"] == "esri-feature":
            return "esri-feature"
        return None

    def _getRemoteCapabilities(self) -> Dict:
        capabilities_request = LoadEsriAsync(self.url)
        capabilities_request.loaded.connect(self._setupLayers)
        self.tm.addTask(capabilities_request)
