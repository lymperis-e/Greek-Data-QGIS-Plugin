from qgis.core import (
    QgsApplication, QgsTask, QgsMessageLog, Qgis
    )
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QPixmap
import requests
from .xml import xmltodict







MESSAGE_CATEGORY = 'custom_geoserver_requests'

class custom_geoserver_get_details(QgsTask):
    """"""
    DETAILS_DICT=None
    details_dict_signal = pyqtSignal(dict)

    def __init__(self, custom_geoserver_layers, current_item, domain_url, description):
        super().__init__(description, QgsTask.CanCancel)
        self.current_item = current_item
        self.custom_geoserver_layers = custom_geoserver_layers
        self.domain_url = domain_url
        self.exception = None

    def run(self):
        """Here you implement your heavy lifting.
        Should periodically test for isCanceled() to gracefully
        abort.
        This method MUST return True or False.
        Raising exceptions will crash QGIS, so we handle them
        internally and raise them in self.finished
        """
        QgsMessageLog.logMessage('Executing request: DescribeFeatureType "{}"'.format(
                                     self.description()),
                                 MESSAGE_CATEGORY, Qgis.Info)
        

        try:
            #self.dockwidget.custom_geoserver_details_tree.clear()
            payload = {'request': 'DescribeFeatureType',
            'version': '1.1.0',
            'typeName': self.custom_geoserver_layers[self.current_item]['name']
            }
            r = requests.get('http://{}/geoserver/ows?service=WFS'.format(self.domain_url), params=payload, headers = {'user-agent': 'grdata-qgis-plugin/0.0.1'})
            # r.content is used, because the response is actually Binary data representing an xml dict
            obj = xmltodict.parse(r.content)
            # xmltodict.parse parses the xml to a Python object, which is then parsed to a list
            obj_list = obj['xsd:schema']['xsd:complexType']['xsd:complexContent']['xsd:extension']['xsd:sequence']['xsd:element']
            res_dict = {}
            for element in obj_list:
                if element['@name'] == 'the_geom':
                    element['@name'] = 'Geometry'
                res_dict[element['@name']] = element['@type'].split(':')[1]
            self.DETAILS_DICT = res_dict

            if self.isCanceled():
                return False
            return True
        except Exception as excep:
            self.exception = Exception(excep)

    def finished(self, result):
        """
        This function is automatically called when the task has
        completed (successfully or not).
        You implement finished() to do whatever follow-up stuff
        should happen after the task is complete.
        finished is always called from the main thread, so it's safe
        to do GUI operations and raise Python exceptions here.
        result is the return value from self.run.
        """
        if result:
            self.details_dict_signal.emit(self.DETAILS_DICT)
            QgsMessageLog.logMessage('Succesfully fetched data from custom_geoserver.gov',
              MESSAGE_CATEGORY, Qgis.Success)


        else:
            if self.exception is None:
                self.details_dict_signal.emit({'none':'none'})
                QgsMessageLog.logMessage(
                    'Request "{name}" not successful but without '\
                    'exception (probably the task was manually '\
                    'canceled by the user)'.format(
                        name=self.description()),
                    MESSAGE_CATEGORY, Qgis.Warning)
            else:
                self.details_dict_signal.emit({'none':'none'})
                QgsMessageLog.logMessage(
                    'Request "{name}" Exception: {exception}'.format(
                        name=self.description(),
                        exception=self.exception),
                    MESSAGE_CATEGORY, Qgis.Critical)
                raise self.exception

    def cancel(self):
        self.details_dict_signal.emit({'none':'none'})
        QgsMessageLog.logMessage(
            'RandomTask "{name}" was canceled'.format( 
                name=self.description()),
            MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()



class custom_geoserver_get_thumbnail(QgsTask):
    """"""
    THUMBNAIL=None
    thumbnail_path_signal = pyqtSignal(QPixmap)
    unnknown_er_signal = pyqtSignal(str)

    def __init__(self, custom_geoserver_layers, current_item, domain_url, description):
        super().__init__(description, QgsTask.CanCancel)
        self.current_item = current_item
        self.custom_geoserver_layers = custom_geoserver_layers
        self.domain_url = domain_url
        self.exception = None

    def run(self):
        """Here you implement your heavy lifting.
        Should periodically test for isCanceled() to gracefully
        abort.
        This method MUST return True or False.
        Raising exceptions will crash QGIS, so we handle them
        internally and raise them in self.finished
        """
        QgsMessageLog.logMessage('Executing request: Fetching thumbnail "{}"'.format(
                                     self.description()),
                                 MESSAGE_CATEGORY, Qgis.Info)
        

        try:
            
            payload = {'request': 'GetMap',
            'version': '1.1.0',
            'layers': self.custom_geoserver_layers[self.current_item]['name'],
            'bbox':'104022.946289062,3850785.50048828,1007956.56329346,4624047.76568604',
            'width':'248',
            'height':'248',
            'srs':'EPSG:2100'

            }
            r = requests.get('http://{}/geoserver/wms?service=WMS&format=image%2Fjpeg'.format(self.domain_url), params=payload, headers = {'user-agent': 'grdata-qgis-plugin/0.0.1'})
            
           
            self.THUMBNAIL = QPixmap()
            self.THUMBNAIL.loadFromData(r.content)


            if self.isCanceled():
                return False
            return True
        except Exception as excep:
            self.exception = Exception(excep)

    def finished(self, result):
        """
        This function is automatically called when the task has
        completed (successfully or not).
        You implement finished() to do whatever follow-up stuff
        should happen after the task is complete.
        finished is always called from the main thread, so it's safe
        to do GUI operations and raise Python exceptions here.
        result is the return value from self.run.
        """
        if result:
            self.thumbnail_path_signal.emit(self.THUMBNAIL)
            QgsMessageLog.logMessage('Succesfully fetched data from custom_geoserver.gov',
              MESSAGE_CATEGORY, Qgis.Success)


        else:
            if self.exception is None:
                self.thumbnail_path_signal.emit(self.THUMBNAIL)
                QgsMessageLog.logMessage(
                    'Request "{name}" not successful but without '\
                    'exception (probably the task was manually '\
                    'canceled by the user)'.format(
                        name=self.description()),
                    MESSAGE_CATEGORY, Qgis.Warning)
            else:
                QgsMessageLog.logMessage(
                    'Request "{name}" Exception: {exception}'.format(
                        name=self.description(),
                        exception=self.exception),
                    MESSAGE_CATEGORY, Qgis.Critical)
                self.thumbnail_path_signal.emit(self.THUMBNAIL)    
                raise self.exception

    def cancel(self):
        self.thumbnail_path_signal.emit(self.THUMBNAIL)
        QgsMessageLog.logMessage(
            'RandomTask "{name}" was canceled'.format( 
                name=self.description()),
            MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()








class custom_geoserver_load_service(QgsTask):
    """"""
    SERVICES_DICT={}
    service_dict_signal = pyqtSignal(dict)
    

    def __init__(self, domain_url, description):
        super().__init__(description, QgsTask.CanCancel)
        self.domain_url = domain_url
        self.exception = None
        self.SERVICES_DICT={}

    def run(self):
        """"""
        

        payload = {'request': 'GetCapabilities',
            'version': '2.0.0'
            }
        r = requests.get('http://{}/geoserver/ows?service=WFS'.format(self.domain_url), params=payload, headers = {'user-agent': 'grdata-qgis-plugin/0.0.1'})
        # r.content is used, because the response is actually Binary data representing an xml dict
        obj = xmltodict.parse(r.content)
        # xmltodict.parse parses the xml to a Python object, which is then parsed to a list
        obj_list = obj['wfs:WFS_Capabilities']['FeatureTypeList']
        
       
        for f in obj_list['FeatureType']:
            self.SERVICES_DICT[f['Title']] = {"name":f['Name'], "description": f['Abstract'], "crs": f['DefaultCRS'], "bbox": f['ows:WGS84BoundingBox']}


        if self.isCanceled():
            return False
        return True
       



    def finished(self, result):
        """"""
        
        if result:
            self.service_dict_signal.emit(self.SERVICES_DICT)
            QgsMessageLog.logMessage('Succesfully fetched Capabilities',
              MESSAGE_CATEGORY, Qgis.Success)

        else:
            if self.exception is None:
                self.service_dict_signal.emit({'none':'none'})
                QgsMessageLog.logMessage(
                    'Request "{name}" not successful but without '\
                    'exception (probably the task was manually '\
                    'canceled by the user)'.format(
                        name=self.description()),
                    MESSAGE_CATEGORY, Qgis.Warning)
                # Show disconnected status
                
            else:
                self.service_dict_signal.emit({'none':'none'})
                QgsMessageLog.logMessage(
                    'Request "{name}" Exception: {exception}'.format(
                        name=self.description(),
                        exception=self.exception),
                    MESSAGE_CATEGORY, Qgis.Critical)
                
                # Show disconnected status
                self.dockwidget.custom_geoserver_status_label.setText("<font color='Red'>Disconnected</font>")
                self.dockwidget.custom_geoserver_status_label.setEnabled(False)
                self.dockwidget.custom_geoserver_status_icon_con.setEnabled(False)

                #raise the error
                raise self.exception
                

    def cancel(self):
        self.service_dict_signal.emit({'none':'none'})
        QgsMessageLog.logMessage(
            'RandomTask "{name}" was canceled'.format( 
                name=self.description()),
            MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()