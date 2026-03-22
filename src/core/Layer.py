from os.path import dirname, join
from typing import Callable, Union

from qgis.core import (QgsCoordinateReferenceSystem, QgsDataSourceUri,
                       QgsProject, QgsRasterLayer, QgsRectangle,
                       QgsVectorLayer)


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
        self.attributes = attributes or {}
        self.geometryType = self.__setupGeometry(geometry_type)
        self.extent = self.attributes.get("extent", None)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<GrdLayer: {self.name}>"

    def __eq__(self, other) -> bool:
        return self.url == other.url

    def qgs_extent(self) -> QgsRectangle:
        return self.getQgisLayer().extent()

    def native_extent(self) -> QgsRectangle:
        crs = (
            self.extent["spatialReference"]["latestWkid"]
            if "latestWkid" in self.extent["spatialReference"]
            else self.extent["spatialReference"]["wkid"]
        )
        return (
            QgsRectangle(
                self.extent["xmin"],
                self.extent["ymin"],
                self.extent["xmax"],
                self.extent["ymax"],
            ),
            f"EPSG:{crs}",
        )

    def get_crs(self) -> str:
        if self.type in (DataModel.esri_vector, DataModel.esri_raster):
            return self.extent["spatialReference"]["latestWkid"]

        elif self.type in (DataModel.wfs, DataModel.wms):
            crs_str = self.attributes["crs"].replace("urn:ogc:def:crs:EPSG::", "")
            return int(crs_str) if crs_str.isdigit() else crs_str

        return None

    def addToMap(self) -> None:
        qgis_layer = self.getQgisLayer()

        # if not qgis_layer:
        #     return

        CRS = self.get_crs()
        crs = QgsCoordinateReferenceSystem(CRS)
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
        CRS = self.get_crs()
        uri = f"crs='{CRS}' " + f"url='{self.url}' "
        return QgsVectorLayer(uri, self.name, "arcgisfeatureserver")

    def _QgsEsriRaster(self) -> QgsRasterLayer:
        """
        Wraps the instance in a QgsRasterLayer
        """
        CRS = self.get_crs()

        lyrId = self.url.split("/")[-1]
        bareUrl = self.url.split("/" + lyrId)[0]
        uri = f"crs='{CRS}' format='PNG32' layer='{lyrId}' url='{bareUrl}' "
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
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "type": self.type,
            "geometry_type": self.geometryType,
            "attributes": self.attributes,
        }

    def __setupGeometry(self, geom_type) -> str:
        """
        Returns the geometry type of the layer

        Returns:
            str: geometry type
        """
        # Normalize geometry token once to support different providers/encodings.
        geom = str(geom_type or "").strip()
        geom_lower = geom.lower()

        if "point" in geom_lower and "line" not in geom_lower:
            return "point"

        if "line" in geom_lower:
            return "line"

        if "polygon" in geom_lower or "envelope" in geom_lower:
            return "polygon"

        if self.type == DataModel.esri_raster:
            return "raster"

        # OGC
        if self.type == DataModel.wfs and geom:
            # Common GML/QName values: gml:PointPropertyType, MultiLineString, etc.
            if "point" in geom_lower:
                return "point"
            if "line" in geom_lower:
                return "line"
            if "polygon" in geom_lower:
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

        base = join(dirname(dirname(__file__)), "assets", "icons")

        if self.geometryType == "raster":
            return join(base, "mIconRasterLayer.svg")

        if self.geometryType == "point":
            return join(base, "mIconPointLayer.svg")

        if self.geometryType == "line":
            return join(base, "mIconLineLayer.svg")

        if self.geometryType == "polygon":
            return join(base, "mIconPolygonLayer.svg")

        # Fallbacks when geometry is not present in capabilities.
        if self.type in (DataModel.esri_raster, DataModel.wms):
            return join(base, "mIconRasterLayer.svg")

        if self.type in (DataModel.esri_vector, DataModel.wfs):
            return join(base, "mIconVector.svg")

        return join(base, "mIconVector.svg")
