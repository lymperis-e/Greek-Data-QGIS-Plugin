from typing import Dict, List, Union

import requests

from .Layer import Layer

#from .utils.esri import query_esri_server



class ESRIService:
    def __init__(self, name, url):
        self.name = name
        self.url = url

        self.capabilities = dict()
        self.available_layers = list()
        self.layers = list()

    def getCapabilities(self) -> Dict:
        self.capabilities, self.available_layers = self.query_esri_server(self.url)
        return self.capabilities

    def setupLayers(self) -> None:
        for layer in self.available_layers:
            layer_instance = Layer(layer.url, layer.name, layer.type)
            self.layers.append(layer_instance)

    def load(self) -> None:
        self.getCapabilities()
        self.setupLayers()

    def getLayers(self) -> List[Layer]:
        return self.layers

    def query_esri_server(self, url, parent_url=None, parent_type=None) -> Dict[str, Dict[str, str]]:
        # Query the REST endpoint
        payload = {"f": "pjson"}
        response = requests.get(
            url,
            params=payload,
            headers={"user-agent": "grdata-qgis-plugin/1.0.0"},
        ).json()

        # Initialize the dictionary for this level of the directory
        capabilities = dict()
        layers = list()

        # Add any services at this level of the directory to the dictionary
        for service in response.get('services', []):
            service_name = service['name'].split('/')[-1]
            service_type = service['type']
            service_url = f"{url}/{service_name}/{service_type}"

            service_layers = self.query_esri_server(
                service_url, url, service_type)

            capabilities[service_name] = {
                "name": service_name,
                "type": service_type,
                "url": service_url,
                "layers": service_layers
            }

        # Recursively add any subdirectories and layers to the dictionary
        for folder in response.get('folders', []):
            folder_url = f"{url}/{folder}"
            folder_dict = self.query_esri_server(folder_url, url, folder)
            if folder_dict:
                capabilities[folder] = folder_dict

        # Add any layers for this service to the dictionary
        for layer in response.get('layers', []):
            layer_id = int(layer['id'])
            layer_name = layer['name']
            layer_url = url

            if parent_url:
                layer_url = parent_url
            if parent_type:
                layer_url += f"/{parent_type}"
            layer_url += f"/{layer_id}"

            capabilities[layer_id] = {
                "id": layer_id,
                "name": layer_name,
                "url": layer_url
            }

            layers.append({
                "id": layer_id,
                "name": layer_name,
                "url": layer_url
            })

        return capabilities, layers
