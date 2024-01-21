from typing import Dict, List, Union

import requests
from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsTask
from qgis.PyQt.QtCore import pyqtSignal

from .Layer import Layer

MESSAGE_CATEGORY = "GreekData-GetCapabilities (ArcGIS server)"


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

    def query_esri_server(
        self, url, parent_url=None, parent_type=None
    ) -> Dict[str, Dict[str, str]]:
        # Clean url
        url = url.rstrip("/")

        # Query the REST endpoint
        payload = {"f": "pjson"}
        response = requests.get(
            url,
            params=payload,
            headers={"user-agent": "grdata-qgis-plugin/1.0.0"},
            timeout=10,
        ).json()

        if "error" in response:
            self.exception = Exception(response)
            return None

        # Initialize the dictionary for this level of the directory
        service_layers = dict()

        # Add any services at this level of the directory to the dictionary
        for service in response.get("services", []):
            service_name = service["name"].split("/")[-1]
            service_type = service["type"]
            service_url = f"{url}/{service_name}/{service_type}"

            service_layers = self.query_esri_server(service_url, url, service_type)

            service_layers[service_name] = {
                "name": service_name,
                "type": service_type,
                "url": service_url,
                "layers": service_layers,
            }

        # Recursively add any subdirectories and layers to the dictionary
        for folder in response.get("folders", []):
            folder_url = f"{url}/{folder}"
            folder_dict = self.query_esri_server(folder_url, url, folder)
            if folder_dict:
                service_layers[folder] = folder_dict

        # Add any layers for this service to the dictionary
        for layer in response.get("layers", []):
            layer_id = int(layer["id"])
            layer_name = layer["name"]
            layer_url = f"{url}/{layer_id}"

            service_layers[layer_id] = {
                "id": layer_id,
                "name": layer_name,
                "url": layer_url,
                "type": parent_type,
            }

            self.layers.append(
                {
                    "id": layer_id,
                    "name": layer_name,
                    "url": layer_url,
                    "type": parent_type,
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
            f"Error while loading {self.url} (ESRI server): {self.exception}",
            MESSAGE_CATEGORY,
            Qgis.Critical,
        )


class ESRIService:
    def __init__(self, name, url):
        self.name = name
        self.url = url

        self.capabilities = dict()
        self.available_layers = list()
        self.layers = list()

        self.tm = QgsApplication.taskManager()
        self.loaded = False

    def getType(self, layer: Dict[str, str]) -> str:
        if layer["type"] == "MapServer":
            return "esri-map"
        if layer["type"] == "FeatureServer":
            return "esri-feature"
        return None

    def getCapabilities(self) -> Dict:
        capabilities_request = LoadEsriAsync(self.url)
        capabilities_request.loaded.connect(self.setupLayers)
        self.tm.addTask(capabilities_request)

    def setupLayers(self, available_layers) -> None:
        for layer in available_layers:
            ltype = self.getType(layer)
            if not ltype:
                continue
            layer_instance = Layer(layer["url"], layer["name"], ltype)
            self.layers.append(layer_instance)

        # Set loaded to true
        self.loaded = True

    def load(self) -> None:
        self.getCapabilities()

    def getLayers(self) -> List[Layer]:
        if not self.loaded:
            self.load()

        return self.layers

    def getLayer(self, idx: int) -> Layer:
        if not self.loaded:
            self.load()

        return self.layers[idx]
