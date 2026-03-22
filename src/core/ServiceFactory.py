from .ESRIService import ESRIService
from .OGCService import OGCService


class ServiceFactory:
    def __init__(self, serviceManager=None, serviceConf=None, **kwargs):
        self.name = kwargs.get("name")
        self.id = kwargs.get("id")
        self.url = kwargs.get("url")
        self.data_model = kwargs.get("type")
        self.serviceManager = serviceManager
        self.serviceConf = serviceConf

    def new(self):
        """
        Class factory method
        """

        if self.data_model == "esri":
            return ESRIService(
                self.name,
                self.url,
                service_id=self.id,
                manager=self.serviceManager,
                config=self.serviceConf,
            )

        if self.data_model == "ogc":
            return OGCService(
                self.name,
                self.url,
                service_id=self.id,
                manager=self.serviceManager,
                config=self.serviceConf,
            )

        return None
