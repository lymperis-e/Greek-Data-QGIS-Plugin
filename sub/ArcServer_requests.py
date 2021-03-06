import requests
import json
from qgis.core import (
    QgsApplication, QgsTask, QgsMessageLog, Qgis
    )
from qgis.PyQt.QtCore import pyqtSignal


#DEPENDENCIES THAT NEED TO BE INSTALLED BY THE USER######





MESSAGE_CATEGORY = 'ArcServer_get_details'

class ArcServer_load_service(QgsTask):
    """"""
    #Globally needed params
    SERVICES_DICT={}
    LAYERS_DETAILS_DICT = {}
    LAYER_PATH_DICT = {}
    service_dict_signal = pyqtSignal(list)
    
    #Params for the requesting part
    ArcServer_base_url = 'http://{}/arcgis/rest/services'
    folders_to_exclude = ["Basemap", "Utilities","Thematic_Map", "TEST_DXF2GDB_SERVICE", "temp", "PrintLayouts" ]


    def __init__(self, domain_url, description):
        super().__init__(description, QgsTask.CanCancel)
        self.domain_url = domain_url
        self.exception = None

        self.SERVICES_DICT={}
        self.LAYERS_DETAILS_DICT = {}
        self.LAYER_PATH_DICT = {}

        self.ArcServer_base_url = 'http://{}/arcgis/rest/services'.format(self.domain_url)

    def run(self):
        """"""
        
        # Construct the first request   (FOLDERS)
        payload = {"f":"pjson"}
        r = requests.get(self.ArcServer_base_url, params=payload, headers = {'user-agent': 'grdata-qgis-plugin/0.0.1'})
        #r.raise_for_status()                                                    # Raise an exception if error code occurs
        
        response_obj = json.loads(r.content)                                    # Pack the response in json, and extract the 1st level folders
        A_folders = response_obj['folders']
        
        for f in A_folders:
            if not f in self.folders_to_exclude:                                # Check if the folder is in the excluded directories list    
                self.SERVICES_DICT[f] = ""



        #Construct the second series of requests   (SERVICES)
        for folder in self.SERVICES_DICT.keys():
            r = requests.get(self.ArcServer_base_url+'/'+str(folder), params=payload, headers = {'user-agent': 'grdata-qgis-plugin/0.0.1'})
            #if r.status_code == 200:
            response_obj = json.loads(r.content)
            B_services = response_obj['services']    # B_services is a LIST of DICTS
            service_dict={}

            for service in B_services:              #Some renaming
                name = ""
                name = service["name"].split("/")[1]

                service_dict[name] = ""
                
            self.SERVICES_DICT[folder] = service_dict



        #Construct the third series of requests     (LAYERS)
        for folder in self.SERVICES_DICT.keys():
            for service in self.SERVICES_DICT[folder].keys():
                r = requests.get(self.ArcServer_base_url+'/'+str(folder)+"/"+str(service)+"/MapServer/layers", params=payload, headers = {'user-agent': 'grdata-qgis-plugin/0.0.1'})
                if r.status_code == 200:
                    response_obj = json.loads(r.content)
                    C_layers = response_obj['layers']    # C_layers is a LIST of DICTS
                    layers_list=[]

                    i = 0
                    for layer in C_layers:
                        layers_list.append(layer["name"]) 
                        self.LAYERS_DETAILS_DICT[layer["name"]] = layer     #the total details of the layer are passed to LDD, and returned as a dict of layer_names/layer_details
                        self.LAYER_PATH_DICT[layer['name']] = str(folder)+'/'+str(service)+'/'+str(i)
                        i+=1

                        
                    self.SERVICES_DICT[folder][service] = layers_list       #the layer name is appended to SD to be returned in order to fill the list tree
                       






        if self.isCanceled():
            return False
        return True
       







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
            self.service_dict_signal.emit([self.SERVICES_DICT, self.LAYERS_DETAILS_DICT, self.LAYER_PATH_DICT])
            QgsMessageLog.logMessage('Succesfully fetched Capabilities data from ArcServer',
              MESSAGE_CATEGORY, Qgis.Success)

        else:
            if self.exception is None:
                self.service_dict_signal.emit([self.SERVICES_DICT, self.LAYERS_DETAILS_DICT, self.LAYER_PATH_DICT])
                QgsMessageLog.logMessage(
                    'Request "{name}" not successful but without '\
                    'exception (probably the task was manually '\
                    'canceled by the user)'.format(
                        name=self.description()),
                    MESSAGE_CATEGORY, Qgis.Warning)
                # Show disconnected status
                
            else:
                self.service_dict_signal.emit([self.SERVICES_DICT, self.LAYERS_DETAILS_DICT, self.LAYER_PATH_DICT])
                QgsMessageLog.logMessage(
                    'Request "{name}" Exception: {exception}'.format(
                        name=self.description(),
                        exception=self.exception),
                    MESSAGE_CATEGORY, Qgis.Critical)
                
                # Show disconnected status
                self.dockwidget.ArcServer_status_label.setText("<font color='Red'>Disconnected</font>")
                self.dockwidget.ArcServer_status_label.setEnabled(False)
                self.dockwidget.ArcServer_status_icon_con.setEnabled(False)

                #raise the error
                raise self.exception
                

    def cancel(self):
        self.service_dict_signal.emit([self.SERVICES_DICT, self.LAYERS_DETAILS_DICT, self.LAYER_PATH_DICT])
        QgsMessageLog.logMessage(
            'RandomTask "{name}" was canceled'.format( 
                name=self.description()),
            MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()








