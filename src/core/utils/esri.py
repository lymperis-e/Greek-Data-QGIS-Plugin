import json

import requests


def query_esri_server(url, parent_url=None, parent_type=None):
    # Query the REST endpoint
    payload = {"f": "pjson"}
    response = requests.get(
        url,
        params=payload,
        headers={"user-agent": "grdata-qgis-plugin/1.0.0"},
        ).json()

    # Initialize the dictionary for this level of the directory
    service_dict = {}

    # Add any services at this level of the directory to the dictionary
    for service in response.get('services', []):
        service_name = service['name'].split('/')[-1]
        service_type = service['type']
        service_url = f"{url}/{service_name}/{service_type}"

        service_layers = query_esri_server(service_url, url, service_type)

        service_dict[service_name] = {
            "name": service_name,
            "type": service_type,
            "url": service_url,
            "layers": service_layers
            }

    # Recursively add any subdirectories and layers to the dictionary
    for folder in response.get('folders', []):
        folder_url = f"{url}/{folder}"
        folder_dict = query_esri_server(folder_url, url, folder)
        if folder_dict:
            service_dict[folder] = folder_dict

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

        service_dict[layer_id] = {
            "id": layer_id,
            "name": layer_name,
            "url": layer_url
            }

    return service_dict
