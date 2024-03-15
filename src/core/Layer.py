from os.path import dirname, join
from typing import Callable, Union

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsVectorLayer,
)


class Layer:
    # Available datamodels:
    # esri-raster, esri-vector, wms, wfs
    def __init__(
        self,
        url,
        name,
        data_model,
        attributes=None,
        geometry_type=None,
        extent=None,
        *args,
        **kwargs,
    ):
        self.url = url
        self.name = name
        self.type = data_model
        self.attributes = attributes
        self.geometryType = self.__setupGeometry(geometry_type)
        self.extent = extent

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<GrdLayer: {self.name}>"

    def __eq__(self, other) -> bool:
        return self.url == other.url

    def qgs_extent(self) -> QgsRectangle:
        return self.getQgisLayer().extent()

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
        if self.type == "esri-vector":
            return self._QgsEsriVector()

        if self.type == "esri-raster":
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

    def __setupGeometry(self, geom_type) -> str:
        """
        Returns the geometry type of the layer

        Returns:
            str: geometry type
        """
        # ESRI
        if self.type == "esri-vector":
            if geom_type == "esriGeometryPoint":
                return "point"
            if geom_type == "esriGeometryPolyline":
                return "line"
            if geom_type == "esriGeometryPolygon":
                return "polygon"
            if geom_type == "esriGeometryEnvelope":
                return "polygon"
            if geom_type == "esriGeometryMultipoint":
                return "point"

        if self.type == "esri-raster":
            return "raster"

        return None

    def getIcon(self) -> str:
        """
        Returns the path to the icon for the layer's type

        Returns:
            str: icon path
        """

        if self.geometryType == "raster":
            return join(
                dirname(dirname(__file__)), "assets", "icons", "mIconRasterLayer.svg"
            )

        if self.geometryType == "point":
            return join(
                dirname(dirname(__file__)), "assets", "icons", "mIconPointLayer.svg"
            )

        if self.geometryType == "line":
            return join(
                dirname(dirname(__file__)), "assets", "icons", "mIconLineLayer.svg"
            )

        if self.geometryType == "polygon":
            return join(
                dirname(dirname(__file__)), "assets", "icons", "mIconPolygonLayer.svg"
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
