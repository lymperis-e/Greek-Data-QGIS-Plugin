from .ESRIService import ESRIService
from .OGCService import OGCService


class ServiceFactory:
    def __init__(self, name, url, service_type):
        self.name = name
        self.url = url
        self.type = service_type

    def new(self):
        """
        Class factory method
        """

        if self.type == "esri":
            return ESRIService(self.name, self.url)

        if self.type == "ogc":
            return OGCService(self.name, self.url)

        return None
