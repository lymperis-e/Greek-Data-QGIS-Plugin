import time
from typing import Dict, List, Optional, Union

from qgis.PyQt.QtCore import QObject, pyqtSignal

from ..sub.capabilities_cache import (load_capabilities_cache,
                                      save_capabilities_cache)
from .Layer import Layer
from .layer_hierarchy import LayerGroup


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
        service_id=None,
        manager=None,
        config=None,
        loaded=False,
    ):
        super().__init__()

        self.name = name
        self.url = url
        self.type = service_type
        self.id = service_id or ""
        self.loaded = loaded
        self.manager = manager
        self.config = config
        self.updated_at = None
        self.layers = None
        self.layer_structure = None  # Hierarchical layer representation
        self.capabilities = None
        self.available_layers = None
        self.icon = None
        self.selectedLayer = None

        self.loaded = loaded
        self.state = GrdServiceState.LOADED if loaded else GrdServiceState.NOT_LOADED

        self._loadConfig()

    def _loadConfig(self) -> None:
        """
        Load static service metadata from services.json and dynamic capabilities/layers
        from cache (.cache/capabilities).
        """
        serviceConf = self.config or {}
        self.id = str(serviceConf.get("id", self.id) or "")
        self.icon = serviceConf.get("icon")

        cached = load_capabilities_cache(service_id=self.id)
        if cached is not None:
            self.updated_at = cached.get("updated_at")
            self.capabilities = cached.get("capabilities")
            self.available_layers = cached.get("available_layers")

            # Load flat layer list
            cached_layers = cached.get("layers")
            if cached_layers:
                self._setupLayers(cached_layers, export_conf=False)

            # Load hierarchical layer structure if available
            cached_layer_structure = cached.get("layer_structure")
            if cached_layer_structure:
                try:
                    self.layer_structure = LayerGroup.from_dict(cached_layer_structure)
                except Exception:
                    # If deserialization fails, layer_structure stays None
                    pass
            return

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

    def _setupLayers(self, available_layers, export_conf=True, layer_structure=None) -> None:
        """
        Setup the layers of the service, based on the available layers.

        Args:
            available_layers: List of layer dicts to convert to Layer objects
            export_conf: Whether to save to cache after setup
            layer_structure: Optional LayerGroup representing the hierarchical structure
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

        # Store the hierarchical structure if provided
        if layer_structure is not None:
            self.layer_structure = layer_structure

        if len(self.layers) > 0:
            self.loaded = True
            self.state = GrdServiceState.LOADED
            self.changed.emit(GrdServiceState.LOADED)

            if export_conf:
                self.exportConfig()

        else:
            self.state = GrdServiceState.ERROR
            self.changed.emit(GrdServiceState.ERROR)

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

    def get_layer_hierarchy(self) -> Optional[LayerGroup]:
        """
        Return the hierarchical layer structure if available.
        This is used by the UI to render nested layer groups.

        Returns:
            LayerGroup representing the hierarchy, or None if keine hierarchy exists
        """
        return self.layer_structure

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
            print(f"Layer with index {idx} does not exist.")

        return self.layers[idx]

    def toJson(self) -> dict:
        result = {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "type": self.type,
            "updated_at": self.updated_at,
            "capabilities": self.capabilities,
            "available_layers": self.available_layers,
            "icon": self.icon,
            "layers": [layer.toJson() for layer in self.layers] if self.layers else [],
        }
        # Include hierarchical structure if available
        if self.layer_structure is not None:
            result["layer_structure"] = self.layer_structure.to_dict()
        return result

    def exportConfig(self) -> None:
        payload = {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "type": self.type,
            "updated_at": self.updated_at,
            "capabilities": self.capabilities,
            "available_layers": self.available_layers,
            "icon": self.icon,
            "layers": [layer.toJson() for layer in self.layers] if self.layers else [],
        }
        # Include hierarchical structure if available
        if self.layer_structure is not None:
            payload["layer_structure"] = self.layer_structure.to_dict()
        save_capabilities_cache(service_id=self.id, payload=payload)
