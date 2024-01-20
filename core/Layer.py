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
    def __init__(self, url, name, feature_type):
        self.url = url
        self.name = name
        self.type = feature_type

    def __str__(self) -> str:
        return self.name

    def addToMap(self) -> None:
        qgis_layer = self.getQgisLayer()
        crs = QgsCoordinateReferenceSystem("EPSG:2100")
        qgis_layer.setCrs(crs)

        if not qgis_layer.isValid():
            print("Layer failed to load!")
        else:
            QgsProject.instance().addMapLayer(qgis_layer)

    def getQgisLayer(self) -> Union[QgsVectorLayer, QgsRasterLayer]:
        """
        Returns the *Layer instance* as a proper QGIS layer object, depending on the instance's type (e.g. WMS, ESRI FeatureServer etc)
        """
        if self.type == "esri-feature":
            return self._EsriVector()

        if self.type == "esri-map":
            return self._EsriRaster()

    def _EsriVector(self) -> QgsVectorLayer:
        """
        Wraps the instance in a QgsVectorLayer
        """
        uri = "crs='EPSG:2100' filter='' " + f"url='{self.url}' " + " table='' sql='' "
        return QgsVectorLayer(uri, self.name, "arcgisfeatureserver")

    def _EsriRaster(self) -> QgsRasterLayer:
        """
        Wraps the instance in a QgsRasterLayer
        """
        uri = self.url
        return QgsRasterLayer(uri, self.name)

    def _Wfs(self) -> QgsVectorLayer:
        uri = "{url}/ows?service=WFS&request=GetFeature&version=2.0.0&outputFormat=json&srsName=EPSG:4326&typeNames={self.name}"
        return QgsVectorLayer(uri, self.name, "OGR")

    def _Wms(self) -> QgsRasterLayer:
        pass
