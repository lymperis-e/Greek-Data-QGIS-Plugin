from os.path import dirname, join
from typing import Callable, Union

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsDataSourceUri,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsVectorLayer,
)


# class data model: possible values are esri-raster, esri-vector, wms, wfs
class DataModel:
    """
    Enum for the different data models that can be used in the application.
    Data models represent the respective ESRI & OGC conventions for data representation (the underlying theoretical data-models)
    """

    esri_raster = "esri-raster"
    esri_vector = "esri-vector"
    wms = "wms"
    wfs = "wfs"


class Layer:
    # Available datamodels:
    # esri-raster, esri-vector, wms, wfs
    def __init__(
        self,
        idx,
        url,
        name,
        data_model: DataModel,
        attributes=None,
        geometry_type=None,
        **kwargs,
    ):
        self.id = idx
        self.url = url
        self.name = name
        self.type = data_model
        self.attributes = attributes
        self.geometryType = self.__setupGeometry(geometry_type)
        self.extent = attributes.get("extent", None)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<GrdLayer: {self.name}>"

    def __eq__(self, other) -> bool:
        return self.url == other.url

    def qgs_extent(self) -> QgsRectangle:
        return self.getQgisLayer().extent()

    def native_extent(self) -> QgsRectangle:
        return (
            QgsRectangle(
                self.extent["xmin"],
                self.extent["ymin"],
                self.extent["xmax"],
                self.extent["ymax"],
            ),
            f"EPSG:{self.extent['spatialReference']['wkid']}",
        )

    def addToMap(self) -> None:
        qgis_layer = self.getQgisLayer()

        # if not qgis_layer:
        #     return

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
        if self.type == DataModel.esri_vector:
            return self._QgsEsriVector()

        if self.type == DataModel.esri_raster:
            return self._QgsEsriRaster()

        if self.type == DataModel.wfs:
            return self._QgsWfs()

        if self.type == DataModel.wms:
            return self._QgsWms()

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

        url = self.url.split("?")[0]
        typename = self.url.split("typename=")[1].split("&")[0]

        ds = QgsDataSourceUri()
        ds.setParam("url", url)
        ds.setParam("typename", typename)
        ds.setParam("service", "WFS")
        ds.setParam("version", "auto")
        ds.setParam("restrictToRequestBBOX", "1")
        ds.setParam("pagingEnabled", "true")
        # uri = f"{self.url}&SERVICE=WFS&REQUEST=GetFeature"
        return QgsVectorLayer(ds.uri(), self.name, "WFS")

    def _QgsWms(self) -> QgsRasterLayer:
        uri = self.url
        return QgsRasterLayer(uri, self.name, "WMS")

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
        if self.type == DataModel.esri_vector:
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

        if self.type == DataModel.esri_raster:
            return "raster"

        # OGC
        if self.type == DataModel.wfs:
            if geom_type == "Point":
                return "point"
            if geom_type == "LineString":
                return "line"

            if geom_type == "MultiLineString":
                return "line"

            if geom_type == "Polygon":
                return "polygon"

            if geom_type == "MultiPolygon":
                return "polygon"

        if self.type == DataModel.wms:
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
