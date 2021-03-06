# -*- coding: utf-8 -*-
"""
/***************************************************************************
 grData
                                 A QGIS plugin
 Simple & centralised access to the official Greek Goverment Spatial Data Infrastructures and Geospatial Data Servers. This plugin provides catalog search and direct layer loading functions for the majority of official greek data sources. 
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-09-08
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Lymperis Efstathios
        email                : geo.elymperis@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import json


from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QByteArray
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtWidgets import QAction, QTableWidgetItem

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the DockWidget
from .grData_dockwidget import grDataDockWidget
import os
from qgis.core import QgsVectorLayer, QgsProject, Qgis, QgsApplication, QgsMessageLog




#Local Imports
from .sub.helper_functions import fill_tree_widget 


from .sub.ArcServer_requests import ArcServer_load_service as ASLS

from .sub.custom_geoserver_requests import custom_geoserver_get_details as CGGD
from .sub.custom_geoserver_requests import custom_geoserver_load_service as CGLS
from .sub.custom_geoserver_requests import custom_geoserver_get_thumbnail as CGGT


basePath = os.path.dirname(os.path.abspath(__file__))
settings_path = os.path.join(basePath, 'assets/sets')



class grData:
    
    
    
    custom_geoserver_Layers={}
    custom_geoserver_selected_item = None
    custom_geoserver_currentServer=str
    geoserver_ServersDomains={}
    


    # Globals for ArcServer Services search
    hidden_2=0
    hidden_3=0
   
                               
    ArcServer_ServersDomains={}
    ArcServer_currentServer=str
    ArcServer_Layers = {}
    ArcServer_selected_item = None


                                
    grdata=QAction()

    



    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        locale_path = os.path.join(
            self.plugin_dir, "i18n", "grData_{}.qm".format(locale)
        )

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr("&Greek Data")
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar("grData")
        self.toolbar.setObjectName("grData")

        # print "** INITIALIZING grData"
        self.tm = QgsApplication.taskManager()
        self.pluginIsActive = False
        self.dockwidget = None

        with open(os.path.join(settings_path, 'services.json'), 'r') as fp:
                current_services = json.loads(fp.read())
                for service, domain in current_services['Geoserver_Services'].items():
                    self.geoserver_ServersDomains[service] = domain
                for service, domain in current_services['ArcServer_Services'].items():
                    self.ArcServer_ServersDomains[service] = domain
        fp.close()
        



       
      
    
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate("grData", message)

    def add_action(self,icon_path,text,callback,enabled_flag=True,add_to_menu=True,add_to_toolbar=True,status_tip=None,whats_this=None,parent=None,):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToWebMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon = QIcon(':/plugins/grData/icon.png')
        self.grdata = QAction(icon, "Greek Open Data Access", self.iface.mainWindow())
        self.grdata.triggered.connect(self.run)
        self.grdata.setCheckable(False)
        self.iface.addToolBarIcon(self.grdata)

        icon_path = ":/plugins/grData/icon.png"
        self.add_action(
            icon_path,
            text=self.tr("Greek Data Access"),
            callback=self.run,
            parent=self.iface.mainWindow(),
        )

  


    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        # print "** CLOSING grData"

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        # print "** UNLOAD grData"
        self.first_start = True
        for action in self.actions:
            self.iface.removePluginWebMenu(self.tr(u"&Greek Data"), action)
            self.iface.removeToolBarIcon(action)
            self.iface.removeToolBarIcon(self.grdata)
        # remove the toolbar
        del self.toolbar

    # --------------------------------------------------------------------------

    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            if self.dockwidget is None:
         
                self.dockwidget = grDataDockWidget()

            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.dockwidget)
            self.dockwidget.show()

           

            

            # 2. ArcServer
            self.dockwidget.ArcServer_list_tree.itemClicked.connect(self.ArcServer_list_changed)
            self.dockwidget.ArcServer_search_line.textChanged.connect(self.filter_ArcServer)
            self.dockwidget.ArcServer_add_button_2.clicked.connect(self.add_ArcServer_layer)
            self.dockwidget.ArcServer_details_checkbox.stateChanged.connect(lambda: self.dockwidget.ArcServer_attribute_table.setEnabled(self.dockwidget.ArcServer_details_checkbox.isChecked()))
            
            self.ArcServer_Layers.clear()
            self.dockwidget.ArcServer_header_label.setText("Select a Data Source:")
            self.dockwidget.widget.setEnabled(False)


            self.dockwidget.ArcServer_status_label.setHidden(True)
            self.dockwidget.ArcServer_status_icon_con.setHidden(True)

            # 3. Custom
            

            # 3.a Custom geoserver tab
            self.dockwidget.custom_geoserver_list.itemClicked.connect(self.custom_geoserver_list_changed)
            self.dockwidget.custom_geoserver_add_button.clicked.connect(self.add_custom_geoserver_layer)
            self.dockwidget.custom_geoserver_search_line.textChanged.connect(self.filter_custom_geoserver)
            self.dockwidget.custom_geoserver_list.itemSelectionChanged.connect(lambda: self.dockwidget.custom_geoserver_add_button.setEnabled(True))
            self.dockwidget.custom_geoserver_details_checkbox.stateChanged.connect(lambda: self.dockwidget.custom_geoserver_details_tree.setEnabled(self.dockwidget.custom_geoserver_details_checkbox.isChecked()))
            self.dockwidget.custom_geoserver_loading_label.setVisible(False)
            self.dockwidget.custom_geoserver_status_icon_con.setEnabled(False)
            self.dockwidget.custom_geoserver_preview_checkbox.stateChanged.connect(lambda: self.dockwidget.custom_geoserver_image_preview.setHidden(not self.dockwidget.custom_geoserver_preview_checkbox.isChecked()))


            # 4. Custom geoserver loading etc
            self.custom_geoserver_Layers.clear()
            self.dockwidget.custom_geoserver_services_list.clear()
            self.dockwidget.custom_geoserver_header_label.setText("Select a Data Source:")
            self.dockwidget.widget_9.setEnabled(False)

            self.dockwidget.custom_geoserver_status_label.setHidden(True)
            self.dockwidget.custom_geoserver_status_icon_con.setHidden(True)




            
            for service in self.geoserver_ServersDomains.keys():
                self.dockwidget.custom_geoserver_services_list.addItem(service)

            for service in self.ArcServer_ServersDomains.keys():
                self.dockwidget.ArcServer_services_list.addItem(service)    


            self.dockwidget.custom_geoserver_services_list.currentTextChanged.connect(self.custom_geoserver_service_changed)
            self.dockwidget.ArcServer_services_list.currentTextChanged.connect(self.ArcServer_service_changed)

            














    def add_custom_geoserver_layer(self):
        layer_name=None
        layer_title=None
        server=None

        try:
            server = self.dockwidget.custom_geoserver_services_list.currentText()
            layer_title = self.custom_geoserver_selected_item
            layer_name = self.custom_geoserver_Layers[self.custom_geoserver_selected_item]['name']


            domain = self.geoserver_ServersDomains[server]

            """Add the selected layer to the map"""
            uri = 'http://{}/geoserver/ows?service=WFS&request=GetFeature&version=2.0.0&outputFormat=json&srsName=EPSG:4326&typeNames={}'.format(domain, layer_name)
            new_layer = QgsVectorLayer(uri, layer_title, "OGR")
            if not new_layer.isValid():
                print("Layer failed to load!")
            else:
                QgsProject.instance().addMapLayer(new_layer)
        except:
            self.iface.messageBar().pushMessage("Ooops", "Something went wrong...", level=Qgis.Critical, duration=3)

    def custom_geoserver_load_services(self):
        """"""
        self.dockwidget.custom_geoserver_status_label.setHidden(False)
        self.dockwidget.custom_geoserver_status_icon_con.setHidden(False)
        

        # Clear the current list of layers
        self.custom_geoserver_Layers.clear()
        self.dockwidget.custom_geoserver_list.clear()
        
        domain = self.geoserver_ServersDomains[self.custom_geoserver_currentServer]
        

        get_serv = CGLS(domain ,'load_available_services')
        #If the method is succesful, connect the signal that passes the available layers dict to the main thread
        get_serv.service_dict_signal.connect(self.custom_geoserver_update_services)
        self.tm.addTask(get_serv)
                       
    def custom_geoserver_update_services(self, services_dict):
        """"""
        
        

        # Check if it is empty, meaning the request failed
        if not services_dict == {'none':'none'}:
            for layer_title, layer_details in services_dict.items():
                
                self.custom_geoserver_Layers[layer_title] = layer_details
                self.dockwidget.custom_geoserver_list.addItem(layer_title)
            
            self.dockwidget.custom_geoserver_status_label.setText("<font color='Green'>Connected</font>")
            self.dockwidget.custom_geoserver_status_label.setEnabled(True)
            self.dockwidget.custom_geoserver_status_icon_con.setEnabled(True)  
            
            self.dockwidget.widget_9.setEnabled(True)

        else:

            self.dockwidget.custom_geoserver_status_label.setText("<font color='Red'>Disconnected</font>")
            self.dockwidget.custom_geoserver_status_label.setEnabled(False)
            self.dockwidget.custom_geoserver_status_icon_con.setEnabled(False)

    def custom_geoserver_list_changed(self, item):


        """Update the currently selected object of the custom_geoserver list"""
        self.custom_geoserver_selected_item = item.text()
        self.dockwidget.custom_geoserver_layer_description_label.setText(self.custom_geoserver_Layers[self.custom_geoserver_selected_item]['description'])
        if self.dockwidget.custom_geoserver_details_checkbox.isChecked() is True:
            self.custom_geoserver_get_thumbnail(item.text())
            self.custom_geoserver_get_details(item.text())
            
            
    def filter_custom_geoserver(self, text):
        #filter_text = str(self.dockwidget.custom_geoserver_search_line.text()).lower()
        filter_text = text.lower()
        for row in range(self.dockwidget.custom_geoserver_list.count()):
            if filter_text in str(self.dockwidget.custom_geoserver_list.item(row).text()).lower():
                self.dockwidget.custom_geoserver_list.setRowHidden(row, False)
            else:
                self.dockwidget.custom_geoserver_list.setRowHidden(row, True)

    def custom_geoserver_get_details(self, item):
        print('Starting..')
        self.dockwidget.custom_geoserver_loading_label.setVisible(True)
        self.custom_geoserver_get_thumbnail(item)
        try:
            
            domain = self.geoserver_ServersDomains[self.custom_geoserver_currentServer]
            get_det = CGGD(self.custom_geoserver_Layers, item, domain ,'Layer details request')
            get_det.details_dict_signal.connect(self.custom_geoserver_update_details)
            self.tm.addTask(get_det)
            self.dockwidget.custom_geoserver_loading_label.setVisible(False)

        except:
            print('Unexpected Error')
            self.dockwidget.custom_geoserver_loading_label.setVisible(False)

    def custom_geoserver_get_thumbnail(self, item):
        QgsMessageLog.logMessage('Executing request: Fetching thumbnail . . . ','custom_geoserver_requests', Qgis.Info)
        domain = self.geoserver_ServersDomains[self.custom_geoserver_currentServer]
        try:
            thumb = CGGT(self.custom_geoserver_Layers, item, domain, 'get layer thumbnail')
            thumb.thumbnail_path_signal.connect(self.custom_geoserver_update_thumbnail)
            self.tm.addTask(thumb)
        except:
            None

    def custom_geoserver_update_thumbnail(self, thumbnail):
        QgsMessageLog.logMessage('Executing request: FETCHED! thumbnail . . . ','custom_geoserver_requests', Qgis.Info)
        try:
            self.dockwidget.custom_geoserver_image_preview.setPixmap(thumbnail)
        except:
            None

    def custom_geoserver_update_details(self, details_dict):
        if not details_dict == {'none':'none'}:
            fill_tree_widget(self.dockwidget.custom_geoserver_details_tree, details_dict)
        else:
            fill_tree_widget(self.dockwidget.custom_geoserver_details_tree, {'Error':'Could not fetch resources from custom_geoserver.gov'}, True)


    def custom_geoserver_service_changed(self, currentText):
        self.custom_geoserver_currentServer = currentText
        

        self.dockwidget.custom_geoserver_list.clear()
        self.dockwidget.custom_geoserver_header_label.setText(currentText)
        self.dockwidget.tabWidget.setTabText(0, currentText)
        self.custom_geoserver_load_services()

























    
    def ArcServer_load_services(self):
        """"""
        
        self.dockwidget.ArcServer_status_label.setHidden(False)
        self.dockwidget.ArcServer_status_icon_con.setHidden(False)



        self.dockwidget.ArcServer_list_tree.clear()
        
        domain = self.ArcServer_ServersDomains[self.ArcServer_currentServer]
        
        get_serv = ASLS(domain, 'load_ArcServer_available_services')


        #If the method is succesful, connect the signal that passes the available layers dict to the main thread
        get_serv.service_dict_signal.connect(self.ArcServer_update_services)
        self.tm.addTask(get_serv)
                       
    def ArcServer_get_details(self, item):
        try:
            # All details tab
            fill_tree_widget(self.dockwidget.ArcServer_details_tree, self.ArcServer_Layers[1][item])

            #Attribute table tab
            fields = self.ArcServer_Layers[1][item]['fields']
            table = self.dockwidget.ArcServer_attribute_table
            table.clear()
            table.setRowCount(0)
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(['Attribute','Type(Length)'])
            table.horizontalHeader().setVisible(True)
            

            for field in fields:
                try:
                    table.insertRow(table.rowCount()) 
                    item = QTableWidgetItem(field["alias"])
                    table.setItem(table.rowCount()-1, 0, item)

                    item = QTableWidgetItem(field["type"].replace("esriFieldType","")+"({})".format(field['length']))
                    table.setItem(table.rowCount()-1, 1, item)
                except:
                    continue
            


        except:
            fill_tree_widget(self.dockwidget.ArcServer_details_tree, {'Error':'Unknown'}, True)

    def ArcServer_update_services(self, services_dict):
        """"""
        
        # Retrieve the results dict
        # Unlike geodata, ArcServer layers' dict contains all the layer info for every layer.
        # It thus needs to be parsed, and only include the layers' names in the list tree,
        # while all the other details do in the details list 
        
        self.ArcServer_Layers = {}
        self.ArcServer_Layers = services_dict
        

        # Check if it is empty, meaning the request failed
        if not services_dict == {'none':'none'}:
            self.dockwidget.ArcServer_list_tree.clear()

            self.dockwidget.widget.setEnabled(True)


            fill_tree_widget(self.dockwidget.ArcServer_list_tree, self.ArcServer_Layers[0], True)

            
  
            
            self.dockwidget.ArcServer_list_tree.setEnabled(True)

            self.dockwidget.ArcServer_status_label.setText("<font color='Green'>Connected</font>")
            self.dockwidget.ArcServer_status_label.setEnabled(True)
            self.dockwidget.ArcServer_status_icon_con.setEnabled(True)  

        else:

            self.dockwidget.ArcServer_status_label.setText("<font color='Red'>Disconnected</font>")
            self.dockwidget.ArcServer_status_label.setEnabled(False)
            self.dockwidget.ArcServer_status_icon_con.setEnabled(False)

    def ArcServer_list_changed(self):
        """Update the currently selected object of the ArcServer list"""
      
        getSelected = self.dockwidget.ArcServer_list_tree.selectedItems()
        if getSelected:
            baseNode = getSelected[0]
            getChildNode = baseNode.text(0)
            self.ArcServer_selected_item = getChildNode
        
        # Write the layer's name on the label above the attributes list
        self.dockwidget.ArcServer_layer_name_1.setText(getChildNode)
        self.dockwidget.ArcServer_layer_name_2.setText(getChildNode)

        # Add Button enabling/disabling
        if baseNode.childCount()==0:
            self.dockwidget.ArcServer_add_button_2.setEnabled(True)
        else:
            self.dockwidget.ArcServer_add_button_2.setEnabled(False)
        
        # Fill the details tab 
        if self.dockwidget.ArcServer_details_checkbox.isChecked() is True:
            self.dockwidget.ArcServer_details_tree.clear()
            if baseNode.childCount()==0:             
                print(getChildNode)
                self.dockwidget.ArcServer_list_tree.headerItem().setText(0, getChildNode)    #TODO TODO TODO
                self.ArcServer_get_details(getChildNode)

    def filter_ArcServer(self, text):
        print(self.hidden_3)
        print(self.hidden_2)
        #filter_text = str(self.dockwidget.geodata_search_line.text()).lower()
        filter_text = text.lower()
        root = self.dockwidget.ArcServer_list_tree.invisibleRootItem()
        c = root.childCount()

        
     
        hidden_1=0
        # Level 1 Nodes
        for i in range(c):
            item_1 = root.child(i)
            cc_count = item_1.childCount()
            
            if cc_count==0:                     # Handle nodes that are empty from the beggining
                if len(filter_text) > 0:
                    item_1.setHidden(True)
                else:
                    item_1.setHidden(False)                
            
            # Level 2 Nodes
            hidden_2=0
            for j in range(cc_count):
                item_2 = item_1.child(j)
                ccc_count = item_2.childCount()
                if ccc_count==0:
                    if filter_text=="":
                        item_2.setHidden(False)
                    else:
                        item_2.setHidden(True)
                # Level 3 Nodes
                hidden_3=0
                for k in range(ccc_count):
                    item_3 = item_2.child(k)
                    cur_text = item_3.text(0).lower() # text at first (0) column
                    # Check item level3
                    if not filter_text in cur_text:
                        item_3.setHidden(True)
                        hidden_3+=1
                        print(hidden_3)
                        print(ccc_count)
                        if hidden_3==ccc_count:
                            item_2.setHidden(True)
                            hidden_2+=1
                            if hidden_2==cc_count:
                                item_1.setHidden(True)
                    else:
                        if item_3.isHidden()==True:
                            item_3.setHidden(False)
                            if item_2.isHidden()==True:
                                item_2.setHidden(False)
                                if item_1.isHidden()==True:
                                    item_1.setHidden(False)
                        
    def add_ArcServer_layer(self):
        layer = self.ArcServer_Layers[2][self.ArcServer_selected_item]
        #layer = self.ArcServer_selected_item
        
        
        uri = "crs='EPSG:2100' filter='' " + "url='http://{}/arcgis/rest/services/{}/MapServer/{}' ".format(self.ArcServer_ServersDomains[self.ArcServer_currentServer],layer.split('/')[0]+'/'+layer.split('/')[1], layer.split('/')[2]) + " table='' sql='' "
        new_layer = QgsVectorLayer(uri, str(self.ArcServer_selected_item), "arcgisfeatureserver")
        if not new_layer.isValid():
            print("Layer failed to load!")
        else:
            QgsProject.instance().addMapLayer(new_layer)

    def ArcServer_service_changed(self, currentText):
        self.ArcServer_Layers.clear()
        self.ArcServer_currentServer = currentText
        

        self.dockwidget.ArcServer_list_tree.clear()
        self.dockwidget.ArcServer_header_label.setText(currentText)
        self.dockwidget.tabWidget.setTabText(1, currentText)
        self.ArcServer_load_services()
