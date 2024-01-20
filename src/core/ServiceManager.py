import json
from typing import Dict, List, Union

import requests

from .AbstractService import ServiceNotExists
from .ESRIService import ESRIService
from .OGCService import OGCService
from .ServiceFactory import ServiceFactory


class ServiceManager:
    remote_repo = "https://gist.githubusercontent.com/lymperis-e/2619fc1d13fd57be2faa4373f5bfa825/raw/f879d3ec37706732173654661533c66257c97bfc/services.json"

    def __init__(self):
        self.available_services = self.load_remote_services()
        self.services = self.instantiate_services()

    def load_remote_services(self) -> Dict[str, str]:
        """
        Fetch a remote resource describing avalable services, and load them
        """
        response = requests.get(
            url=self.remote_repo,
            headers={"user-agent": "grdata-qgis-plugin/2.0"},
            timeout=10,
        )
        available_services = json.loads(response.content)["services"]

        return available_services

    def instantiate_services(self) -> List[Union[OGCService, ESRIService]]:
        services = []

        for service in self.available_services:
            service_instance = ServiceFactory(
                name=service["name"], url=service["url"], service_type=service["type"]
            ).new()

            services.append(service_instance)

        return services

    def getService(self, name: str) -> Union[ESRIService, OGCService]:
        for service in self.services:
            if service.name == name:
                return service
        raise ServiceNotExists(name)

    def getServicesList(self) -> List[Union[OGCService, ESRIService]]:
        return self.services
