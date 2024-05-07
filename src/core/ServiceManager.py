import json
from os.path import dirname, join
from typing import Dict, List, Union

import requests

from .ESRIService import ESRIService
from .OGCService import OGCService
from .Service import GrdService, ServiceNotExists
from .ServiceFactory import ServiceFactory

CONFIG_FILE = join(dirname(dirname(__file__)), "assets", "settings", "services.json")


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
        self.servicesConf = self._readConfigFile()

        if len(self.services) == 0:
            self.services = self.__instantiate_services()

        self.selectedService = None

    def _readConfigFile(self) -> Union[Dict, None]:
        """
        Read all the services that are cached locally from the config file
        """
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)

        return config.get("services")

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

        for service in self.servicesConf:
            service_instance = ServiceFactory(
                serviceManager=self, serviceConf=service, **service
            ).new()

            services.append(service_instance)

        # Old implementation, prioritize remote repo
        # for service in self.available_services:

        #     print(f"Creating service {service.get('name')}")

        #     # Get the service configuration
        #     sname = service.get("name")
        #     sconf = None
        #     for s in self.servicesConf:
        #         if s.get("name") == sname:
        #             sconf = s
        #             break

        #     service_instance = ServiceFactory(
        #         serviceManager=self,
        #         serviceConf=sconf,
        #         **service,
        #     ).new()

        #     services.append(service_instance)

        return services

    def setSelectedService(self, name: str) -> None:
        """
        Set the selected service

        Args:
            name (str): The name of the service
        """
        self.selectedService = self.getService(name)

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
