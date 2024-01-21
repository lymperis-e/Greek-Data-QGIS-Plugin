from os.path import dirname, join

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QTreeWidgetItem

from ..core.Layer import Layer
from ..core.utils.QUrlIcon import QUrlIcon

plugin_logo = join(dirname(dirname(__file__)), "assets", "img", "icon.png")


def get_base_url(url):
    from urllib.parse import urlparse

    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    return base_url


def service_icon(service):
    ico_url = get_base_url(service.url) + "/favicon.ico"
    qUriIcon = QUrlIcon(ico_url).icon()

    if qUriIcon is None:
        qUriIcon = QIcon(plugin_logo)
    return QIcon(qUriIcon)


# Layers
def addLayerItem(layer, parent):
    child = QTreeWidgetItem()
    child.setText(0, unicode(layer.name))
    child.setIcon(0, QIcon(layer.getIcon()))
    child.setToolTip(
        0, f"{layer.name} ({layer.type})"
    )  # Set the tooltip with the desired context
    parent.addChild(child)


def fillServiceLayers(parentItem, service, expanded=True):
    service_layers = service.getLayers()
    for layer in service_layers:
        addLayerItem(layer, parentItem)

    parentItem.setExpanded(expanded)


# Services
def addServiceItem(service, parent):
    child = QTreeWidgetItem()
    child.setText(0, unicode(service.name))
    child.setIcon(0, service_icon(service))

    parent.addChild(child)


def fillServices(parentItem, services):
    for service in services:
        addServiceItem(service, parentItem.invisibleRootItem())


# Generic, to be DEPRECATED
def fill_tree_item(item, value, exp):
    item.setExpanded(exp)
    if isinstance(value, dict):
        for key, val in sorted(value.items()):
            child = QTreeWidgetItem()
            child.setText(0, unicode(key))
            child.setIcon(0, QIcon(plugin_logo))

            item.addChild(child)
            fill_tree_item(child, val, exp)

    # Layers list
    elif isinstance(value, list) and all(isinstance(x, Layer) for x in value):
        print("Layers list")
        print(value)
        print("----")
        for lyr in value:
            print("Layer: ", lyr.name)
            icn = lyr.getIcon()
            print("Icon: ", icn)
            child = QTreeWidgetItem()
            child.setText(0, unicode(lyr.name))
            child.setIcon(0, QIcon(icn))
            item.addChild(child)

    elif isinstance(value, list):
        for val in value:
            child = QTreeWidgetItem()
            child.setIcon(0, QIcon(plugin_logo))

            item.addChild(child)

            if isinstance(val, dict):
                child.setText(0, "[dict]")
                fill_tree_item(child, val, exp)
            elif isinstance(val, list):
                child.setText(0, "[list]")
                fill_tree_item(child, val, exp)
            else:
                child.setText(0, unicode(val))
            child.setExpanded(True)

    else:
        child = QTreeWidgetItem()
        child.setText(1, unicode(value))
        child.setIcon(0, QIcon(plugin_logo))
        item.setIcon(0, QIcon(plugin_logo))

        item.addChild(child)


def fill_subtree_widget(parentItem, value, expanded=True):
    fill_tree_item(parentItem, value, expanded)


def fill_tree_widget(widget, value, expanded=False):
    widget.clear()
    fill_tree_item(widget.invisibleRootItem(), value, expanded)
