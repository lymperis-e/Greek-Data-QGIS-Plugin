from typing import Dict, List, Union

import requests
from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsTask
from qgis.PyQt.QtCore import pyqtSignal

from .Layer import Layer


class OGCService:
    def __init__(self, name, url):
        self.name = name
        self.url = url

        self.capabilities = dict()
        self.available_layers = list()
        self.layers = list()

        self.tm = QgsApplication.taskManager()

    def getCapabilities(self):
        pass

    def setupLayers(self, available_layers) -> None:
        for layer in available_layers:
            layer_instance = Layer(layer["url"], layer["name"], layer["type"])
            self.layers.append(layer_instance)

    def load(self) -> None:
        self.getCapabilities()

    def getLayers(self) -> List[Layer]:
        return self.layers

    def add_to_map(self):
        layer_name = None
        layer_title = None
        server = None

        try:
            server = self.dockwidget.custom_geoserver_services_list.currentText()
            layer_title = self.custom_geoserver_selected_item
            layer_name = self.custom_geoserver_Layers[
                self.custom_geoserver_selected_item
            ]["name"]

            domain = self.domain

            # Add the selected layer to the map
            uri = f"http://{domain}/geoserver/ows?service=WFS&request=GetFeature&version=2.0.0&outputFormat=json&srsName=EPSG:4326&typeNames={layer_name}"

            new_layer = QgsVectorLayer(uri, layer_title, "OGR")
            if not new_layer.isValid():
                print("Layer failed to load!")
            else:
                QgsProject.instance().addMapLayer(new_layer)
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Ooops", "Something went wrong...", e, level=Qgis.Critical, duration=3
            )
