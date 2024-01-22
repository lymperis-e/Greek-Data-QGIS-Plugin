from os.path import dirname, join
from typing import Callable, Union

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)


class Layer:
    # Available types:
    # esri-map, esri-feature, wms, wfs
    def __init__(self, url, name, feature_type, attributes=None, *args, **kwargs):
        self.url = url
        self.name = name
        self.type = feature_type
        self.attributes = attributes

    def __str__(self) -> str:
        return self.name

    def addToMap(self) -> None:
        qgis_layer = self.getQgisLayer()
        crs = QgsCoordinateReferenceSystem("EPSG:2100")
        qgis_layer.setCrs(crs)

        # if not qgis_layer.isValid():
        #    print("Layer failed to load!")
        # else:
        QgsProject.instance().addMapLayer(qgis_layer)

    def getQgisLayer(self) -> Union[QgsVectorLayer, QgsRasterLayer]:
        """
        Returns the *Layer instance* as a proper QGIS layer object, depending on the instance's type (e.g. WMS, ESRI FeatureServer etc)
        """
        if self.type == "esri-feature":
            return self._QgsEsriVector()

        if self.type == "esri-map":
            return self._QgsEsriRaster()
        return None

    def _QgsEsriVector(self) -> QgsVectorLayer:
        """
        Wraps the instance in a QgsVectorLayer
        """
        uri = "crs='EPSG:2100' " + f"url='{self.url}' "
        return QgsVectorLayer(uri, self.name, "arcgisfeatureserver")

    def _QgsEsriRaster(self) -> QgsRasterLayer:
        """
        Wraps the instance in a QgsRasterLayer
        """
        lyrId = self.url.split("/")[-1]
        bareUrl = self.url.split("/" + lyrId)[0]
        uri = f"crs='EPSG:2100' format='PNG32' layer='{lyrId}' url='{bareUrl}' "
        return QgsRasterLayer(uri, self.name, "arcgismapserver")

    def _QgsWfs(self) -> QgsVectorLayer:
        uri = "{url}/ows?service=WFS&request=GetFeature&version=2.0.0&outputFormat=json&srsName=EPSG:4326&typeNames={self.name}"
        return QgsVectorLayer(uri, self.name, "OGR")

    def _QgsWms(self) -> QgsRasterLayer:
        pass

    def toJson(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "type": self.type,
            "attributes": self.attributes,
        }

    def getIcon(self) -> str:
        """
        Returns the path to the icon for the layer's type

        Returns:
            str: icon path
        """
        if self.type == "esri-feature":
            return join(
                dirname(dirname(__file__)), "assets", "icons", "mIconVector.svg"
            )
        if self.type == "esri-map":
            return join(
                dirname(dirname(__file__)), "assets", "icons", "mIconRasterLayer.svg"
            )
        if self.type == "wms":
            return join(
                dirname(dirname(__file__)), "assets", "icons", "mIconRasterLayer.svg"
            )
        if self.type == "wfs":
            return join(
                dirname(dirname(__file__)), "assets", "icons", "mIconVector.svg"
            )
        return None
