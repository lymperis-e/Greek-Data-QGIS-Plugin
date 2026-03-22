import time
from typing import Dict, List, Optional, Union
from urllib.parse import parse_qs, unquote, urlparse

import requests
from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsTask
from qgis.PyQt.QtCore import pyqtSignal

from ..sub.logger import LOGGER_CATEGORY
from ..sub.xml import xmltodict
from .Layer import DataModel, Layer
from .layer_hierarchy import LayerGroup
from .Service import GrdService


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

    @staticmethod
    def _as_list(value):
        """Normalize xmltodict nodes to a list for safe iteration."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def _infer_wfs_geometry_from_layer(self, layer: Dict[str, str]) -> Optional[str]:
        """
        Best-effort geometry inference for WFS layers when explicit geometryType
        is missing in capabilities responses.
        """
        url = str(layer.get("url") or "")
        if not url:
            return None

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        raw_typename = query.get("typename", query.get("typeName", [""]))[0]
        typename = unquote(str(raw_typename or "")).lower()
        if not typename:
            return None

        point_tokens = ["_poi", "poi_", ":poi", "_point", "point_"]
        line_tokens = ["_lin", "lin_", ":lin", "_line", "line_"]
        polygon_tokens = ["_pol", "pol_", ":pol", "_poly", "poly_"]

        if any(token in typename for token in point_tokens):
            return "Point"
        if any(token in typename for token in line_tokens):
            return "LineString"
        if any(token in typename for token in polygon_tokens):
            return "Polygon"

        return None

    def _request_capabilities(self, url, payload, service_label):
        """Request OGC capabilities with a one-time SSL-verification fallback."""
        base_kwargs = {
            "params": payload,
            "headers": {"user-agent": "grdata-qgis-plugin/1.0.0"},
            "timeout": 10,
            "allow_redirects": True,
            "cookies": None,
        }

        try:
            response = requests.get(url, **base_kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.SSLError as err:
            QgsMessageLog.logMessage(
                f"[OGCService/Loader] {service_label} SSL verification failed for {url}; retrying without certificate verification: {err}",
                LOGGER_CATEGORY,
                Qgis.Warning,
            )
            response = requests.get(url, verify=False, **base_kwargs)
            response.raise_for_status()
            return response

    def _get_wfs(self, url):
        url = url.rstrip("/")

        try:
            payload = {"request": "GetCapabilities", "service": "WFS"}
            response = self._request_capabilities(url, payload, "WFS")

            service_dict = xmltodict.parse(response.content)
            capabilities = service_dict.get("wfs:WFS_Capabilities", {})
            feature_type_list = capabilities.get("FeatureTypeList", {})
            services = feature_type_list.get("FeatureType")
            return self._as_list(services)
        except requests.exceptions.RequestException as e:
            self.exception = e
            QgsMessageLog.logMessage(
                f"[OGCService/Loader] WFS capabilities request failed for {url}: {e}",
                LOGGER_CATEGORY,
                Qgis.Warning,
            )
            return None
        except Exception as e:
            self.exception = e
            QgsMessageLog.logMessage(
                f"[OGCService/Loader] WFS capabilities parse failed for {url}: {e}",
                LOGGER_CATEGORY,
                Qgis.Warning,
            )
            return None

    def _get_wms(self, url):
        url = url.rstrip("/")
        try:
            payload = {"request": "GetCapabilities", "service": "WMS"}
            response = self._request_capabilities(url, payload, "WMS")

            service_dict = xmltodict.parse(response.content)
            capabilities = service_dict.get("WMS_Capabilities", {})
            capability = capabilities.get("Capability", {})
            services = capability.get("Layer")
            return self._as_list(services)
        except requests.exceptions.RequestException as e:
            self.exception = e
            QgsMessageLog.logMessage(
                f"[OGCService/Loader] WMS capabilities request failed for {url}: {e}",
                LOGGER_CATEGORY,
                Qgis.Warning,
            )
            return None
        except Exception as e:
            self.exception = e
            QgsMessageLog.logMessage(
                f"[OGCService/Loader] WMS capabilities parse failed for {url}: {e}",
                LOGGER_CATEGORY,
                Qgis.Warning,
            )
            return None

    def query_OGC_server(self, url) -> Dict[str, Dict[str, str]]:

        wfs_resp = self._get_wfs(url)
        wms_resp = self._get_wms(url)

        if wfs_resp is None and wms_resp is None:
            return None

        # Add any services at this level of the directory to the dictionary
        for idx, layer in enumerate(wfs_resp or []):
            if not isinstance(layer, dict):
                continue

            type_name = layer.get("Name")
            if not type_name:
                continue

            self.layers.append(
                {
                    "id": idx,
                    "name": layer.get("Title", type_name),
                    "url": f"{url}?typename={type_name}",
                    "type": "wfs",
                    "attributes": {
                        "crs": layer.get("DefaultCRS", None),
                        "title": layer.get("Title", None),
                        "description": layer.get("Abstract", None),
                        "extent": bbox_from_corners(
                            layer.get("ows:WGS84BoundingBox", None)
                        ),
                    },
                    "geometryType": self._infer_wfs_geometry_from_layer(
                        {
                            "type": "wfs",
                            "url": f"{url}?typename={type_name}",
                        }
                    ),
                }
            )

        for idx, layer in enumerate(wms_resp or []):
            if not isinstance(layer, dict):
                continue

            # Some WMS capabilities include group layers without Name; skip those.
            layer_name = layer.get("Name")
            if not layer_name:
                continue

            self.layers.append(
                {
                    "id": idx,
                    "name": layer.get("Title", layer_name),
                    "url": f"{url}?typename={layer_name}",
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
        if self.capabilities is None or len(self.layers) == 0:
            return False
        return True

    def finished(self, result):
        # Success
        if result:
            self.loaded.emit(self.layers)
            QgsMessageLog.logMessage(
                f"[OGCService/Loader] Succesfully loaded {self.url} (OGC server)",
                LOGGER_CATEGORY,
                Qgis.Success,
            )
            return

        # Cancelled
        if self.exception is None:
            # Emit empty payload so downstream service transitions out of LOADING.
            self.loaded.emit([])
            QgsMessageLog.logMessage(
                f'[OGCService/Loader] Request "{self.description()}" not successful but without '
                "exception (probably the task was manually "
                "canceled by the user)",
                LOGGER_CATEGORY,
                Qgis.Warning,
            )
            return

        # Error
        # Emit empty payload so downstream service transitions out of LOADING.
        self.loaded.emit([])
        QgsMessageLog.logMessage(
            f"[OGCService/Loader] Error while loading {self.url} (OGC server): {self.exception}.",
            LOGGER_CATEGORY,
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

        # OGC hierarchy is not yet supported; ignore any legacy cached hierarchy.
        self.layer_structure = None

        self.tm = QgsApplication.taskManager()

    def _layerDataModel(self, layer: Dict[str, str]) -> str:
        if layer["type"] == "wfs":
            return DataModel.wfs

        if layer["type"] == "wms":
            return DataModel.wms

        return None

    def _infer_wfs_geometry_from_layer(self, layer: Dict[str, str]) -> Optional[str]:
        """
        Best-effort geometry inference for WFS layers when explicit geometryType
        is missing in capabilities/cache. Many Greek municipal services encode
        geometry in typename tokens (e.g. _poi_, _lin_, _pol_).
        """
        url = str(layer.get("url") or "")
        if not url:
            return None

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        raw_typename = query.get("typename", query.get("typeName", [""]))[0]
        typename = unquote(str(raw_typename or "")).lower()
        if not typename:
            return None

        point_tokens = ["_poi", "poi_", ":poi", "_point", "point_"]
        line_tokens = ["_lin", "lin_", ":lin", "_line", "line_"]
        polygon_tokens = ["_pol", "pol_", ":pol", "_poly", "poly_"]

        if any(token in typename for token in point_tokens):
            return "Point"
        if any(token in typename for token in line_tokens):
            return "LineString"
        if any(token in typename for token in polygon_tokens):
            return "Polygon"

        return None

    def _layerGeometryType(self, layer: Dict[str, str]) -> str:
        attributes = layer.get("attributes") or {}
        geometry = attributes.get(
            "geometryType",
            layer.get("geometryType", layer.get("geometry_type", None)),
        )
        if geometry:
            return geometry

        if layer.get("type") == "wfs":
            return self._infer_wfs_geometry_from_layer(layer)

        return None

    def _getRemoteCapabilities(self) -> Dict:
        self._current_ogc_task = LoadOGCAsync(self.url)
        self._current_ogc_task.loaded.connect(self._on_ogc_layers_loaded)
        self.tm.addTask(self._current_ogc_task)

    def _on_ogc_layers_loaded(self, layers: List) -> None:
        """Handler for OGC layers loaded signal. Calls _setupLayers (no hierarchy extraction yet)."""
        # OGC servers don't have clear hierarchy structure like ESRI, so we don't extract hierarchy
        # Fall back to flat rendering
        self._setupLayers(layers, export_conf=True, layer_structure=None)
