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
import os

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFillSymbol,
    QgsGeometry,
    QgsMessageLog,
    QgsProject,
    QgsRectangle,
    QgsSimpleLineSymbolLayer,
    QgsVectorLayer,
)
from qgis.gui import QgsMessageBar, QgsRubberBand
from qgis.PyQt.QtCore import QByteArray, QCoreApplication, QSettings, Qt, QTranslator
from qgis.PyQt.QtGui import QColor, QIcon, QPixmap
from qgis.PyQt.QtWidgets import QAction, QTableWidgetItem

from .core.Service import ServiceNotExists
from .core.ServiceManager import ServiceManager
from .core.utils.QUrlIcon import QUrlIcon

# Import the code for the DockWidget
from .grData_dockwidget import grDataDockWidget

# Initialize Qt resources from file resources.py
from .resources import *

# Local Imports
from .sub.helper_functions import (
    fill_tree_widget,
    fillServiceLayers,
    fillServices,
    filter_tree_widget_leafs,
    filter_tree_widget_roots,
)

basePath = os.path.dirname(os.path.abspath(__file__))
settings_path = os.path.join(basePath, "assets/settings")


class grData:
    grdata = QAction()

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
        self.actions = list()
        self.menu = self.tr("&Greek Data")
        self.toolbar = self.iface.addToolBar("grData")
        self.toolbar.setObjectName("grData")

        # print "** INITIALIZING grData"
        self.tm = QgsApplication.taskManager()
        self.pluginIsActive = False
        self.dockwidget = None

        # DEV
        self.rubber_band: QgsRubberBand = QgsRubberBand(
            self.iface.mapCanvas(), Qgis.GeometryType.Polygon
        )
        self.serviceManager = ServiceManager()

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

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
    ):
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

    def rubberband_from_current_bbox(self):
        self.rubber_band.reset(Qgis.GeometryType.Polygon)

        bbox, bbox_crs = (
            self.serviceManager.selectedService.selectedLayer.native_extent()
        )
        rect = QgsRectangle(bbox)
        rubber_geom = QgsGeometry.fromRect(rect)

        # self.rubber_band.setFillColor(Qt.red)
        self.rubber_band.setFillColor(QColor(255, 0, 0, 20))
        self.rubber_band.setStrokeColor(QColor(255, 0, 0, 100))

        # Set the rubber band geometry
        self.rubber_band.setToGeometry(
            rubber_geom, QgsCoordinateReferenceSystem(bbox_crs)
        )  # ("EPSG:4326"))

        # Show the rubber band on the map canvas
        self.rubber_band.show()

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "img", "icon.png")
        icon = QIcon(icon_path)
        self.grdata = QAction(icon, "Greek Open Data Access", self.iface.mainWindow())
        self.grdata.triggered.connect(self.run)
        self.grdata.setCheckable(False)
        self.iface.addToolBarIcon(self.grdata)

        self.add_action(
            icon_path,
            text=self.tr("Greek Data Access"),
            callback=self.run,
            parent=self.iface.mainWindow(),
        )

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""
        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)
        self.pluginIsActive = False
        self.rubber_band.hide()

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        self.rubber_band.hide()
        # print "** UNLOAD grData"
        self.first_start = True
        for action in self.actions:
            self.iface.removePluginWebMenu(self.tr("&Greek Data"), action)
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

            # DEV: New tab
            self.fill_connections_list()

            self.dockwidget.current_layer_details_tree.setHeaderLabels(
                ["Attribute", "Value"]
            )
            self.dockwidget.current_layer_details_tree.setColumnWidth(0, 150)
            self.dockwidget.current_layer_details_tree.setColumnWidth(1, 250)
            self.dockwidget.current_layer_details_tree.setSortingEnabled(True)

            self.dockwidget.current_layer_details_tree.setHeaderHidden(False)

            # Add filter services targets (services, layers)
            self.dockwidget.filter_services_combobox.clear()
            self.dockwidget.filter_services_combobox.addItems(["Services", "Layers"])

            self.dockwidget.filter_services_line_edit.textChanged.connect(
                self.filter_connections_list
            )

            self.dockwidget.current_layer_add_to_map_btn.clicked.connect(
                self.add_layer_to_map
            )

            # Connections list: Selection changed
            self.dockwidget.conn_list_widget.currentItemChanged.connect(
                self.connListChanged
            )

    # ------------------- NEW  -------------------------------------------------------
    def fill_connections_list(self):
        services = self.serviceManager.listServices()
        self.dockwidget.conn_list_widget.clear()
        fillServices(self.dockwidget.conn_list_widget, services)

        # Double-click
        self.dockwidget.conn_list_widget.itemDoubleClicked.connect(
            self.handle_connections_list_double_click
        )

    def filter_connections_list(self, filter_text):
        filterTarget = self.dockwidget.filter_services_combobox.currentText()
        if filterTarget == "Services":
            filter_tree_widget_roots(self.dockwidget.conn_list_widget, filter_text)
        elif filterTarget == "Layers":
            filter_tree_widget_leafs(self.dockwidget.conn_list_widget, filter_text)
        else:
            return

    def handle_connections_list_double_click(self, item, column):
        parent = item.parent()

        # Top level item (service)
        if not parent:
            return

        self.add_layer_to_map(item, parent)

    def expand_service(self, item):
        if item.childCount() > 0:
            return

        name = item.text(0)
        service = self.serviceManager.getService(name)

        if service.getLayers() is None:
            msg_bar = self.iface.messageBar()
            msg_bar.pushMessage(
                "Loading ",
                f"Service {name} is being loaded",
                level=Qgis.Info,
            )
            return

        fillServiceLayers(item, service)

    def add_layer_to_map(self, item=None, parent=None):

        if item and parent:
            service = self.serviceManager.getService(parent.text(0))
            layer = service.getLayer(parent.indexOfChild(item))

            # Set selected service & layer
            self.serviceManager.setSelectedService(service.name)
            self.serviceManager.selectedService.setSelectedLayer(layer.id)

        # print(
        #     f"selected service: {self.serviceManager.selectedService.name}, selected layer: {self.serviceManager.selectedService.selectedLayer.name}"
        # )
        bbox = self.serviceManager.selectedService.selectedLayer.addToMap()

    def connListChanged(self, layer):
        selectedItem = self.dockwidget.conn_list_widget.currentItem()
        parent = selectedItem.parent()
        if not parent:
            self.expand_service(selectedItem)
            return

        service = self.serviceManager.getService(parent.text(0))
        layer = service.getLayer(parent.indexOfChild(selectedItem))

        # Set selected service & layer
        self.serviceManager.setSelectedService(service.name)
        self.serviceManager.selectedService.setSelectedLayer(layer.id)

        self.dockwidget.current_layer_details_tree.setHeaderLabels(["Key", "Value"])
        fill_tree_widget(self.dockwidget.current_layer_details_tree, layer.attributes)
        self.dockwidget.current_layer_description_label.setText(
            layer.attributes["description"]
        )

        self.dockwidget.current_layer_name_label.setText(layer.name)
        self.dockwidget.current_layer_url_label.setText(layer.url)

        self.dockwidget.current_layer_copyright_label.setText(
            layer.attributes.get("copyrightText")
        )

        self.dockwidget.current_layer_add_to_map_btn.setEnabled(True)

        # Display the layer's extent
        try:
            self.rubberband_from_current_bbox()
        except Exception as e:
            # QgsMessageLog.logMessage(str(e), "grData", Qgis.Critical)
            None
