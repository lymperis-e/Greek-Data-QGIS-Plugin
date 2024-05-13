import json
import time
from os.path import dirname, join
from typing import Dict, List

from qgis.PyQt.QtCore import QObject, pyqtSignal

from .Layer import Layer

CONFIG_FILE = join(dirname(dirname(__file__)), "assets", "settings", "services.json")


class ServiceNotExists(Exception):
    """Raised when a requested service does not exist."""

    def __init__(self, service_name):
        self.service_name = service_name

    def __str__(self):
        return f"Service '{self.service_name}' does not exist."


# loaded, loading, error, not_loaded
class GrdServiceState:
    LOADED = "loaded"
    LOADING = "loading"
    ERROR = "error"
    NOT_LOADED = "not_loaded"


class GrdService(QObject):
    """
    Base class for all services

    Attributes:
        - name: The name of the service
        - url: The url of the service
        - type: The type of the service (esri, ogc)
        - loaded: A boolean indicating if the service is loaded
        - capabilities: The capabilities of the service
        - available_layers: The available layers of the service
        - layers: The layers of the service
        - manager: The service manager
    """

    changed = pyqtSignal(str)

    def __init__(
        self,
        name,
        url,
        service_type,
        manager=None,
        config=None,
        loaded=False,
    ):
        super().__init__()

        self.name = name
        self.url = url
        self.type = service_type
        self.loaded = loaded
        self.manager = manager
        self.config = config
        self.updated_at = None
        self.layers = None
        self.capabilities = None
        self.available_layers = None
        self.icon = None
        self.selectedLayer = None

        self.loaded = loaded
        self.state = GrdServiceState.LOADED if loaded else GrdServiceState.NOT_LOADED

        self._loadConfig()

    def _loadConfig(self) -> None:
        """
        Load the service from the local config file
        """
        serviceConf = self.config
        if not serviceConf:
            return

        self.updated_at: int = serviceConf.get("updated_at", None)
        self.capabilities = serviceConf.get("capabilities")
        self.available_layers: List = serviceConf.get("available_layers")
        self.icon: str = serviceConf.get("icon")
        self._setupLayers(serviceConf.get("layers"), export_conf=False)

    def __str__(self):
        return self.name

    def _layerDataModel(self, layer) -> str:
        """
        Returns the type of the layer (raster, vector)
        """
        raise NotImplementedError

    def _layerGeometryType(self, layer) -> str:
        """
        Returns the geometry type of the layer (point, line, polygon, raster)
        """
        raise NotImplementedError

    def _getRemoteCapabilities(self) -> Dict:
        raise NotImplementedError

    def _setupLayers(self, available_layers, export_conf=True) -> None:
        """
        Setup the layers of the service, based on the available layers
        """

        lrs = available_layers if available_layers else []

        self.layers = [
            Layer(
                idx=i,
                **layer,
                data_model=self._layerDataModel(layer),
                geometry_type=self._layerGeometryType(layer),
            )
            for i, layer in enumerate(lrs)
        ]

        if len(self.layers) > 0:
            self.loaded = True
            self.state = GrdServiceState.LOADED
            self.changed.emit(GrdServiceState.LOADED)

            if export_conf:
                self.exportConfig()

    def _fetchRemoteConfig(self) -> None:
        """
        Fetch the remote config of the service (e.g. GetCapabilities, ESRI capabilities, etc.)
        """

        self.state = GrdServiceState.LOADING
        self.changed.emit(GrdServiceState.LOADING)

        self._getRemoteCapabilities()
        self.updated_at = int(time.time())

    def setSelectedLayer(self, idx: int) -> None:
        if idx is None:
            self.selectedLayer = None
        self.selectedLayer = self.layers[idx]

    def __layersExpired(self) -> bool:
        """
        The service's layers have not been updated recently (1 week)
        and need to be refreshed from the server.
        """
        MAX_AGE = 604800  # 1 week

        unix_time_now = int(time.time())
        if self.updated_at is None:
            return True

        return unix_time_now - self.updated_at > MAX_AGE

    def getLayers(self) -> List[Layer]:
        if not self.loaded or self.__layersExpired() or len(self.layers) == 0:
            self._fetchRemoteConfig()

        return self.layers

    def getLayer(self, idx: int) -> Layer:
        if not self.loaded or self.__layersExpired():
            self._fetchRemoteConfig()

        if idx >= len(self.layers):
            raise ServiceNotExists(self.name)

        return self.layers[idx]

    def toJson(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "type": self.type,
            "updated_at": self.updated_at,
            "capabilities": self.capabilities,
            "available_layers": self.available_layers,
            "icon": self.icon,
            "layers": [layer.toJson() for layer in self.layers] if self.layers else [],
        }

    def exportConfig(self) -> None:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            current_config = json.load(f)
            services = current_config.get("services", None)

            if not services:
                current_config["services"] = [self.toJson()]
            else:
                for idx, service in enumerate(services):
                    if service.get("name", None) == self.name:
                        services[idx] = self.toJson()
                        break
                else:
                    current_config["services"].append(self.toJson())

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current_config, f, indent=4)
