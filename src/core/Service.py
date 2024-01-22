import json
from os.path import dirname, join
from typing import Dict, List, Union

import requests

from ..sub.helper_functions import get_base_url
from .Layer import Layer

CONFIG_FILE = join(dirname(dirname(__file__)), "assets", "settings", "services.json")


class ServiceNotExists(Exception):
    """Raised when a requested service does not exist."""

    def __init__(self, service_name):
        self.service_name = service_name

    def __str__(self):
        return f"Service '{self.service_name}' does not exist."


class GrdService:
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

    def __init__(
        self,
        name,
        url,
        service_type,
        capabilities,
        available_layers,
        layers,
        manager=None,
        loaded=False,
    ):
        self.name = name
        self.url = url
        self.type = service_type
        self.loaded = loaded
        self.capabilities = capabilities
        self.available_layers = available_layers
        self.layers = layers
        self.manager = manager
        self.icon = None

        self._loadConfig()

    def __str__(self):
        return self.name

    def _getLayerType(self, layer) -> str:
        raise NotImplementedError

    def _getRemoteCapabilities(self) -> Dict:
        raise NotImplementedError

    def _getConfigFile(self) -> str:
        """
        Get the path to the config file
        """
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def _readServiceJSON(self) -> Union[Dict, None]:
        """
        Get the capabilities of the service from the local config file
        """
        config = self._getConfigFile()
        services = config.get("services")
        if not services:
            return None
        for service in services:
            if service.get("name") == self.name:
                return service
        return None

    def _setupLayers(self, available_layers, export=True) -> None:
        """
        Setup the layers of the service, based on the available layers
        """
        self.layers = [
            Layer(**layer, feature_type=self._getLayerType(layer))
            for layer in available_layers
        ]

        if len(self.layers) > 0:
            self.loaded = True

            if export:
                self.exportConfig()

    def _loadConfig(self) -> None:
        """
        Load the service from the local config file
        """
        serviceConf = self._readServiceJSON()
        if not serviceConf:
            return

        self.capabilities = serviceConf.get("capabilities")
        self.available_layers = serviceConf.get("available_layers")
        self.icon = serviceConf.get("icon")
        self._setupLayers(serviceConf.get("layers"), export=False)

    def _fetchRemoteConfig(self) -> None:
        """
        Fetch the remote config of the service
        """
        self._getRemoteCapabilities()
        self.__getIcon()

    def getLayers(self) -> List[Layer]:
        if not self.loaded or len(self.layers) == 0:
            self._fetchRemoteConfig()

        return self.layers

    def getLayer(self, idx: int) -> Layer:
        if not self.loaded:
            self._fetchRemoteConfig()

        return self.layers[idx]

    def toJson(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "type": self.type,
            "capabilities": self.capabilities,
            "available_layers": self.available_layers,
            "icon": self.icon,
            "layers": [layer.toJson() for layer in self.layers],
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

    def __getIcon(self) -> str:
        names_to_try = [
            "favicon.ico",
            "favicon.png",
            "favicon.gif",
            "favicon.jpg",
            "icon.ico",
            "icon.png",
            "icon.gif",
            "ico.png",
            "ico.gif",
            "ico.jpg",
            "logo.png",
            "logo.gif",
            "logo.jpg",
            "logo.ico",
        ]

        for name in names_to_try:
            ico_url = get_base_url(self.url) + "/" + name
            response = requests.get(ico_url, timeout=5)
            if response.status_code == 200:
                self.icon = ico_url
                self.exportConfig()
                return
