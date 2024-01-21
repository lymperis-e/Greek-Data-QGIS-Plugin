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

        self.load()

    def __str__(self):
        return self.name

    def getLayerType(self, layer) -> str:
        raise NotImplementedError

    def getRemoteCapabilities(self) -> Dict:
        raise NotImplementedError

    def getConfigFile(self) -> str:
        """
        Get the path to the config file
        """
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def getLocalCapabilities(self) -> Union[Dict, None]:
        """
        Get the capabilities of the service from the local config file
        """
        config = self.getConfigFile()
        services = config.get("services", None)
        if not services:
            return None
        for service in services:
            if service.get("name", None) == self.name:
                return service
        return None

    def setupLayers(self, available_layers) -> None:
        """
        Setup the layers of the service, based on the available layers
        """
        for layer in available_layers:
            ltype = self.getLayerType(layer)
            if not ltype:
                continue
            layer_instance = Layer(**layer, feature_type=ltype)
            self.layers.append(layer_instance)

        # Export the config & set the loaded flag
        self.manager.exportConfig()
        self.loaded = True

    def load(self, remote=False) -> None:
        localCapabilities = self.getLocalCapabilities()
        if not localCapabilities:
            if remote:
                self.__getIcon()
                self.getRemoteCapabilities()
            return

        if (
            localCapabilities.get("layers") is None
            or localCapabilities.get("layers") == []
        ):
            if remote:
                self.getRemoteCapabilities()
            return

        if localCapabilities.get("icon") is None:
            if remote:
                self.__getIcon()
            return

        self.icon = localCapabilities.get("icon", None)
        availableLayers = localCapabilities.get("available_layers", None)
        if availableLayers is not None:
            self.setupLayers(availableLayers)

    def getLayers(self) -> List[Layer]:
        if not self.loaded or len(self.layers) == 0:
            self.load(remote=True)

        return self.layers

    def getLayer(self, idx: int) -> Layer:
        if not self.loaded:
            self.load()

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
                self.manager.exportConfig()
                return
