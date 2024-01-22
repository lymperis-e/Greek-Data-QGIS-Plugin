from .ESRIService import ESRIService
from .OGCService import OGCService


class ServiceFactory:
    def __init__(self, name, url, service_type, serviceManager=None):
        self.name = name
        self.url = url
        self.type = service_type
        self.serviceManager = serviceManager

    def new(self):
        """
        Class factory method
        """

        if self.type == "esri":
            return ESRIService(self.name, self.url, manager=self.serviceManager)

        if self.type == "ogc":
            return OGCService(self.name, self.url, manager=self.serviceManager)

        return None
