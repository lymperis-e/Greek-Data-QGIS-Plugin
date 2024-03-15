import json
from os.path import dirname, join
from typing import Dict, List, Union

import requests

from .ESRIService import ESRIService
from .OGCService import OGCService
from .Service import GrdService, ServiceNotExists
from .ServiceFactory import ServiceFactory


class ServiceManager:
    remote_repo = "https://gist.githubusercontent.com/lymperis-e/2619fc1d13fd57be2faa4373f5bfa825/raw"

    def __init__(
        self,
        available_services: Dict[str, str] = None,
        services: List[GrdService] = None,
    ) -> None:
        self.available_services = (
            self.__load_remote_services()
            if available_services is None
            else available_services
        )
        self.services = list() if services is None else services

        if len(self.services) == 0:
            self.services = self.__instantiate_services()

    def __load_remote_services(self) -> Dict[str, str]:
        """
        Fetch a remote resource describing available services, and load them
        """
        response = requests.get(
            url=self.remote_repo,
            headers={"user-agent": "grdata-qgis-plugin/2.0"},
            timeout=10,
        )

        # try:
        available_services = json.loads(response.content).get("services")
        # except Exception as e:
        #    print(e)
        #    available_services = list()

        return available_services

    def __instantiate_services(self) -> List[GrdService]:
        """
        Instantiate the services from the list of available services.

        Returns:
            List[GrdService]: A list of GrdService instances
        """
        services = list()

        for service in self.available_services:
            service_instance = ServiceFactory(
                name=service["name"],
                url=service["url"],
                service_type=service["type"],
                serviceManager=self,
            ).new()

            services.append(service_instance)

        return services

    def getService(self, name: str) -> GrdService:
        """
        Get a service by name

        Args:
            name (str): The name of the service

        Raises:
            ServiceNotExists: If the service does not exist

        Returns:
            GrdService: The service instance
        """
        for service in self.services:
            if service.name == name:
                return service
        raise ServiceNotExists(name)

    def listServices(self) -> List[GrdService]:
        """
        Get the list of services

        Returns:
            List[GrdService]: The list of services
        """
        return self.services

    def toJson(self) -> Dict[str, Union[str, List[Dict[str, str]]]]:
        """
        Serialize the services to a dictionary

        Returns:
            Dict[str, Union[str, List[Dict[str, str]]]]: The serialized services
        """
        return {"services": [service.toJson() for service in self.services]}

    def exportConfig(self, overwrite=False) -> None:
        settings_path = join(
            dirname(dirname(__file__)), "assets", "settings", "services.json"
        )

        if overwrite:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(self.toJson(), f, indent=4)
            return

        with open(settings_path, "r", encoding="utf-8") as f:
            current_config = json.load(f)
            current_config = {**current_config, **self.toJson()}

        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(current_config, f, indent=4)
