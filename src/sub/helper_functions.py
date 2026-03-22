import hashlib
import os
from os.path import dirname, isfile, join
from urllib.parse import urlparse

import requests
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QTreeWidgetItem

plugin_logo = join(dirname(dirname(__file__)), "assets", "img", "icon.png")
cache_root = join(dirname(dirname(__file__)), ".cache")
icons_cache_dir = join(cache_root, "icons")


def get_base_url(url):
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    return base_url


def ensure_cache_directories():
    os.makedirs(icons_cache_dir, exist_ok=True)


def _service_icon_cache_path(service):
    if not isinstance(service.icon, str) or service.icon == "":
        return None

    parsed = urlparse(service.icon)
    _, ext = os.path.splitext(parsed.path)
    if ext.lower() not in [".png", ".jpg", ".jpeg", ".ico", ".svg", ".webp"]:
        ext = ".img"

    hashed = hashlib.sha256(service.icon.encode("utf-8")).hexdigest()
    return join(icons_cache_dir, f"{hashed}{ext}")


def cache_service_icon(service):
    """Cache service icon to the plugin .cache/icons directory and return local path."""
    if service.icon is None:
        return None

    ensure_cache_directories()

    cache_path = _service_icon_cache_path(service)
    if cache_path is None:
        return None

    if isfile(cache_path):
        return cache_path

    try:
        response = requests.get(service.icon, timeout=4)
        if response.status_code != 200:
            return None

        with open(cache_path, "wb") as f:
            f.write(response.content)

        return cache_path
    except Exception:
        return None


def service_qicon(service):
    """
    Get the icon of a service without blocking the UI thread.

    Args:
        service (grdata.core.Service.GrdService): _description_

    Returns:
        QIcon: The icon of the service
    """
    if service.icon is None:
        return QIcon(plugin_logo)

    cache_path = _service_icon_cache_path(service)
    if cache_path and isfile(cache_path):
        return QIcon(cache_path)

    # Avoid synchronous network requests while populating the tree.
    # Use service icon only when it points to a local file.
    if isinstance(service.icon, str) and isfile(service.icon):
        return QIcon(service.icon)

    return QIcon(plugin_logo)


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
