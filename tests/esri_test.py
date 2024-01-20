import sys

# sys.path.append("C:\\OSGeo4W\\apps\\Python39")
# sys.path.append("C:\\OSGeo4W\\apps\\qgis-ltr\\bin")
# sys.path.append("C:\\OSGeo4W\\apps\\qgis-ltr")
# sys.path.append("C:\\OSGeo4W\\bin")
# sys.path.append("C:\\OSGeo4W\\apps\\Qt5")
# sys.path.append("C:\\OSGeo4W\\apps\\Python39\\lib\\site-packages\\PyQt5")


sys.path.append("C:\\OSGeo4W\\apps\\qgis-ltr\\python")
sys.path.append("C:\\OSGeo4W\\apps\\Python39\\lib\\site-packages")
sys.path.append("C:\\OSGeo4W\\apps\\qgis-ltr\\python\\qgis")


import json

from core.ESRIService import ESRIService as Service

services = [
    # {
    #    "name": "Πολεοδομία",
    #    "type": "esri",
    #    "url": "http://gis.epoleodomia.gov.gr/arcgis/rest/services"
    #    },
    {
        "name": "Ktima",
        "type": "esri",
        "url": "http://gis.ktimanet.gr/inspire/rest/services",
    },
    {"name": "GGB", "type": "esri", "url": "http://gis.ggb.gr/arcgis/rest/services/"},
    {
        "name": "EAGME",
        "type": "esri",
        "url": "https://gaia.igme.gr/server/rest/services/",
    },
]


def test_class():
    capabilities_list = list()
    for service in services:
        instance = Service(
            service["name"], service["url"], service["name"], service["type"]
        )
        capabilities = instance.getCapabilities()

        capabilities_list.append(capabilities)

    with open("./data/capabilities.json", "w", encoding="utf8") as f:
        json.dump({"services": capabilities_list}, f, ensure_ascii=False)


if __name__ == "__main__":
    test_class()
