from typing import Dict, List, Union

import requests
from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsTask
from qgis.PyQt.QtCore import pyqtSignal

from ..sub.xml import xmltodict
from .Layer import DataModel, Layer
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


def bbox_from_corners(bbox) -> str:
    """
    Convert WFS repr :
    <ows:LowerCorner>20.786230268362047 36.20732655645524</ows:LowerCorner>
    <ows:UpperCorner>28.15668655964659 41.55731605723071</ows:UpperCorner>

    to:
    "spatialReference": {
        "wkid": 4326
    },
    "xmax": 23.348496228518172,
    "xmin": 23.236629377543807,
    "ymax": 39.03960686276656,
    "ymin": 38.990246073097865
    """

    lower_corner = bbox.get("ows:LowerCorner", None)
    upper_corner = bbox.get("ows:UpperCorner", None)

    if lower_corner is None or upper_corner is None:
        return None

    lower_corner = [float(x) for x in lower_corner.split()]
    upper_corner = [float(x) for x in upper_corner.split()]

    return {
        "xmin": lower_corner[0],
        "xmax": upper_corner[0],
        "ymin": lower_corner[1],
        "ymax": upper_corner[1],
        "spatialReference": {"wkid": 4326},
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

    def _get_wfs(self, url):
        url = url.rstrip("/")

        # Query the REST endpoint
        payload = {"request": "GetCapabilities", "service": "WFS"}
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

    def _get_wms(self, url):
        url = url.rstrip("/")
        # Query the REST endpoint
        payload = {"request": "GetCapabilities", "service": "WMS"}
        response = requests.get(
            url,
            params=payload,
            headers={"user-agent": "grdata-qgis-plugin/1.0.0"},
            timeout=10,
            allow_redirects=True,
            cookies=None,
        )

        service_dict = xmltodict.parse(response.content)
        # print(
        #     f"Number of layers: {len(service_dict['WMS_Capabilities']['Capability']['Layer'])}"
        # )

        services = service_dict["WMS_Capabilities"]["Capability"]["Layer"]

        if "error" in response:
            self.exception = Exception(response)
            return None

        return services

    def query_OGC_server(self, url) -> Dict[str, Dict[str, str]]:

        wfs_resp = self._get_wfs(url)
        wms_resp = self._get_wms(url)

        if wfs_resp is None and wms_resp is None:
            return None

        # Add any services at this level of the directory to the dictionary
        for idx, layer in enumerate(wfs_resp):
            self.layers.append(
                {
                    "id": idx,
                    "name": layer.get("Title", layer.get("Name", None)),
                    "url": f"{url}?typename={layer['Name']}",
                    "type": "wfs",
                    "attributes": {
                        "crs": layer.get("DefaultCRS", None),
                        "title": layer.get("Title", None),
                        "description": layer.get("Abstract", None),
                        "extent": bbox_from_corners(
                            layer.get("ows:WGS84BoundingBox", None)
                        ),
                    },
                    "geometryType": None,
                }
            )

        for idx, layer in enumerate(wms_resp):
            self.layers.append(
                {
                    "id": idx,
                    "name": layer.get("Title", layer.get("Name", None)),
                    "url": f"{url}?typename={layer['Name']}",
                    "type": "wms",
                    "attributes": {
                        "crs": layer.get("DefaultCRS", None),
                        "title": layer.get("Title", None),
                        "description": layer.get("Abstract", None),
                        "extent": bbox_from_corners(
                            layer.get("ows:WGS84BoundingBox", None)
                        ),
                    },
                    "geometryType": None,
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
            service_type="ogc",
            loaded=False,
            *args,
            **kwargs,
        )

        self.tm = QgsApplication.taskManager()

    def _layerDataModel(self, layer: Dict[str, str]) -> str:
        if layer["type"] == "wfs":
            return DataModel.wfs

        if layer["type"] == "wms":
            return DataModel.wms

        return None

    def _layerGeometryType(self, layer: Dict[str, str]) -> str:
        return layer["attributes"].get("geometryType", None)

    def _getRemoteCapabilities(self) -> Dict:
        capabilities_request = LoadOGCAsync(self.url)
        capabilities_request.loaded.connect(self._setupLayers)
        self.tm.addTask(capabilities_request)
