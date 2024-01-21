import requests
from qgis.PyQt.QtGui import QIcon, QPixmap


class QUrlIcon:
    def __init__(self, url):
        self.url = url
        self._icon = QIcon()
        try:
            response = requests.get(self.url, timeout=5)
            if response.status_code != 200:
                self._icon = None
            else:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                self._icon = QIcon(pixmap)

        except Exception as e:
            print(e)
            self._icon = None

    def icon(self):
        return self._icon
