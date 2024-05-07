from os.path import dirname, join

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QTreeWidgetItem

from ..core.utils.QUrlIcon import QUrlIcon

plugin_logo = join(dirname(dirname(__file__)), "assets", "img", "icon.png")


def get_base_url(url):
    from urllib.parse import urlparse

    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    return base_url


def service_qicon(service):
    """
    Get the icon of a service (if available) by querying the service's url for a favicon.ico

    Args:
        service (grdata.core.Service.GrdService): _description_

    Returns:
        QIcon: The icon of the service
    """
    if service.icon is None:
        return QIcon(plugin_logo)

    qUriIcon = QUrlIcon(service.icon).icon()
    if qUriIcon is None:
        return QIcon(plugin_logo)
    return QIcon(qUriIcon)


# ------------


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


# ------------


# Services
def addServiceItem(service, parent):
    print(service)
    child = QTreeWidgetItem()
    child.setText(0, unicode(service.name))
    child.setIcon(0, service_qicon(service))

    parent.addChild(child)

    return child


# ------------


def fillServices(parentItem, services):
    for service in services:
        serviceItem = addServiceItem(service, parentItem.invisibleRootItem())
        if service.loaded:
            fillServiceLayers(serviceItem, service, expanded=False)


# Generic Tree Utils


def fill_tree_item(item, value, exp):
    """
    Fill a tree widget item with the value

    Args:
        item (QTreeWidgetItem): The item to fill
        value (any): The value to fill the item with. Can be str, int, float, dict, list
        exp (_type_): set the item expanded
    """
    item.setExpanded(exp)
    if isinstance(value, dict):
        for key, val in sorted(value.items()):
            child = QTreeWidgetItem()
            child.setText(0, unicode(key))
            child.setIcon(0, QIcon(plugin_logo))

            item.addChild(child)
            fill_tree_item(child, val, exp)

    elif isinstance(value, list):
        for val in value:
            child = QTreeWidgetItem()
            child.setIcon(0, QIcon(plugin_logo))

            item.addChild(child)

            if isinstance(val, dict):
                child.setText(0, "[dict]")
                if "name" in val:
                    child.setText(0, unicode(val["name"]))

                fill_tree_item(child, val, exp)
            elif isinstance(val, list):
                child.setText(0, "[list]")
                fill_tree_item(child, val, exp)
            else:
                child.setText(0, unicode(val))
            child.setExpanded(True)

    else:
        item.setText(1, unicode(value))


def fill_subtree_widget(parentItem, value, expanded=True):
    """
    Fill a tree widget item, completing its whole subtree recursively with the value

    Args:
        parentItem (QTreeWidgetItem): The item to fill
        value (any): The value to fill the item with. Can be str, int, float, dict, list
        expanded (bool, optional): Set to expanded . Defaults to True.
    """
    fill_tree_item(parentItem, value, expanded)


def fill_tree_widget(widget, value, expanded=False):
    """
    Fill a tree widget with the value recursively

    Args:
        widget (QtreeWidget): The tree widget to fill
        value (any): The value to fill the tree widget with. Can be str, int, float, dict, list
        expanded (bool, optional): Set the widget to expanded. Defaults to False.
    """
    widget.clear()
    fill_tree_item(widget.invisibleRootItem(), value, expanded)


def toggle_tree_widget_all(tree_widget, hidden=False):
    """
    Traverse all items in the tree and hide/show them recursively
    """

    def hide_tree_widget_item(item):
        item.setHidden(hidden)
        for index in range(item.childCount()):
            hide_tree_widget_item(item.child(index))

    hide_tree_widget_item(tree_widget.invisibleRootItem())


def filter_tree_widget_leafs(tree_widget, filter_text, parent_item=None):
    """
    Filter the tree_widget by the filter_text

    Args:
        tree_widget (QTreeWidget): The tree widget to filter
        filter_text (str): The text to filter by
        parent_item (QTreeWidgetItem, optional):  The parent item. Defaults to None.
    """
    # If filter_text is empty, show all items
    if filter_text == "":
        toggle_tree_widget_all(tree_widget, hidden=False)
        return

    # Hide all items
    toggle_tree_widget_all(tree_widget, hidden=True)

    # Find leafs that match the filter_text recursively
    matching_leafs = list()

    def find_matching_leafs(item):
        for index in range(item.childCount()):
            child = item.child(index)
            if filter_text.lower() in child.text(0).lower():
                matching_leafs.append(child)
            find_matching_leafs(child)

    if parent_item is None:
        parent_item = tree_widget.invisibleRootItem()
    find_matching_leafs(parent_item)

    # Show the matching leafs
    for leaf in matching_leafs:
        leaf.setHidden(False)

    # Show the parents of the matching leafs
    for leaf in matching_leafs:
        parent = leaf.parent()
        while parent is not None:
            parent.setHidden(False)
            parent = parent.parent()

    # Show the root
    parent_item.setHidden(False)


def filter_tree_widget_roots(tree_widget, filter_text):
    """
    Filter the tree_widget's root elements by the filter_text
    Args:
        tree_widget (QTreeWidget): The tree widget to filter
        filter_text (str): The text to filter by
    """
    for item_index in range(tree_widget.topLevelItemCount()):
        item = tree_widget.topLevelItem(item_index)
        if not filter_text.lower() in item.text(0).lower():
            item.setHidden(True)
        else:
            item.setHidden(False)
