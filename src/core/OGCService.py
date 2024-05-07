from typing import Dict, List, Union

import requests
from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsTask
from qgis.PyQt.QtCore import pyqtSignal

from ..sub.xml import xmltodict
from .Layer import Layer
from .Service import GrdService

MESSAGE_CATEGORY = "GreekData-GetCapabilities (ArcGIS server)"


def clean_OGC_attributes(layer_attributes: Dict[str, str]) -> None:
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


def filter_OGC_attributes(attributes: Dict[str, str]) -> Dict[str, str]:
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


class LoadOGCAsync(QgsTask):
    """
    Asynchronously query an ArcGIS server for available services, using a QgsTask
    """

    loaded = pyqtSignal(list)

    def __init__(self, url):
        super().__init__(f"Loading from {url} (OGC server)", QgsTask.CanCancel)

        self.url = url
        self.capabilities = dict()
        self.layers = list()
        self.exception = None

    def _get(self, url):
        url = url.rstrip("/")

        # Query the REST endpoint
        payload = {"f": "json", "request": "GetCapabilities", "service": "WFS"}
        response = requests.get(
            url,
            params=payload,
            headers={"user-agent": "grdata-qgis-plugin/1.0.0"},
            timeout=10,
            allow_redirects=True,
            cookies=None,
        )

        service_dict = xmltodict.parse(response.content)
        services = service_dict["wfs:WFS_Capabilities"]["FeatureTypeList"][
            "FeatureType"
        ]

        if "error" in response:
            self.exception = Exception(response)
            return None

        return services

    def query_OGC_server(self, url) -> Dict[str, Dict[str, str]]:

        response = self._get(url)
        if response is None:
            return None

        # Initialize the dictionary for this level of the directory

        # Add any services at this level of the directory to the dictionary
        for idx, layer in enumerate(response):

            self.layers.append(
                {
                    "id": idx,
                    "name": layer.get("Title", layer.get("Name", None)),
                    "url": f"{url}/{layer['Name']}",
                    "type": "vector",
                    "attributes": {
                        "title": layer.get("Title", None),
                        "description": layer.get("Abstract", None),
                        "extent": layer.get("LatLongBoundingBox", None),
                    },
                    "geometryType": None,
                    "extent": layer.get("ows:WGS84BoundingBox", None),
                }
            )

        return self.layers

    def run(self):
        self.capabilities = self.query_OGC_server(self.url)
        if self.isCanceled():
            return False
        return True

    def finished(self, result):
        # Success
        if result:
            self.loaded.emit(self.layers)
            QgsMessageLog.logMessage(
                f"Succesfully loaded {self.url} (OGC server)",
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
            f"Error while loading {self.url} (OGC server): {self.exception}.",
            MESSAGE_CATEGORY,
            Qgis.Critical,
        )


OGC_GEOMETRY_TYPES = [
    None,  # raster
    "Point",
    "Multipoint",
    "LineString",
    "Polygon",
    "MultiLineString",
    "MultiPolygon",
]


class OGCService(GrdService):
    def __init__(self, name, url, *args, **kwargs) -> GrdService:
        super().__init__(
            name=name,
            url=url,
            service_type="OGC",
            loaded=False,
            *args,
            **kwargs,
        )

        self.tm = QgsApplication.taskManager()

    def _layerDataModel(self, layer: Dict[str, str]) -> str:
        if layer["type"] == "vector":
            return "OGC-Vector"

        if layer["type"] == "raster":
            return "OGC-Raster"

        return None

    def _layerGeometryType(self, layer: Dict[str, str]) -> str:
        return layer["attributes"].get("geometryType", None)

    def _getRemoteCapabilities(self) -> Dict:
        capabilities_request = LoadOGCAsync(self.url)
        capabilities_request.loaded.connect(self._setupLayers)
        self.tm.addTask(capabilities_request)
