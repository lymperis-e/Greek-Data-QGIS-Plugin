import json
from os.path import dirname, join

import requests
from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsTask
from qgis.PyQt.QtCore import pyqtSignal

CONFIG_FILE = join(dirname(dirname(__file__)), "assets", "settings", "services.json")


class FetchFromGithub(QgsTask):
    """
    Fetch source.json from github and update the local sources.json file,
    if the fetched file contains new services. Existing services will not be updated.

    Args:
        QgsTask (_type_): _description_
    """

    fetched = pyqtSignal(list)
    github_url = "https://raw.githubusercontent.com/lymperis-e/Greek-Data-QGIS-Plugin/dev/services.json"

    def __init__(self):
        super().__init__(
            f"Updating services from {self.github_url} ", QgsTask.CanCancel
        )

        self.new_services = []
        self.exception = None

    def __fetch(self):
        """
        Fetch the source.json file from github
        """
        try:
            response = requests.get(
                self.github_url,
                headers={"user-agent": "grdata-qgis-plugin/1.0.0"},
                timeout=10,
                allow_redirects=True,
                cookies=None,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.exception = e
            return None

    def __compare(self, fetched_services):
        """
        Compare the fetched services with the local services. If a service does not exist in the local services,
        it will be added to the new_services list.

        If a service has been modified in the local services, it will not be updated. For example, if the layers array
        of a service has been modified, the service will not be updated.
        """
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            local_services = json.load(file).get("services", [])

        # Index the local services by url
        local_services_index = {service["url"]: service for service in local_services}

        new_services = []
        for service in fetched_services:
            if not service["url"] in local_services_index.keys():
                new_services.append(service)

        return new_services

    def run(self):
        fetched_services = self.__fetch().get("services", None)

        if fetched_services is None:
            return False

        self.new_services = self.__compare(fetched_services)

        if not self.new_services or self.isCanceled():
            return True

        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            current_config = json.load(file)
            services = current_config.get("services", None)

            if not services:
                current_config["services"] = self.new_services
            else:
                current_config["services"].extend(self.new_services)

        with open(CONFIG_FILE, "w", encoding="utf-8") as file:
            json.dump(current_config, file, indent=4)

        return True

    def finished(self, result):
        if result:
            self.fetched.emit(self.new_services)
        else:
            QgsMessageLog.logMessage(
                f"Failed to fetch services from {self.github_url}",
                "GRData",
                Qgis.Critical,
            )


class GrdSourcesUpdater:
    def __init__(self):
        self.tm = QgsApplication.taskManager()

    def onFetched(self, new_services):
        print("New services fetched: ", len(new_services))
        if new_services:
            QgsMessageLog.logMessage(
                f"New services fetched: {len(new_services)}", "GRData", Qgis.Info
            )

    def update(self, callback=None):
        print("Updating services...")

        task = FetchFromGithub()
        task.fetched.connect(self.onFetched)

        if callback:
            task.fetched.connect(callback)

        self.tm.addTask(task)
