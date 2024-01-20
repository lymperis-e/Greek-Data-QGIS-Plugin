from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QTreeWidgetItem


def fill_tree_item(item, value, exp, clicked):
    item.setExpanded(exp)
    if isinstance(value, dict):
        for key, val in sorted(value.items()):
            child = QTreeWidgetItem()
            child.setText(0, unicode(key))
            child.setIcon(0, QIcon(":/plugins/grData/assets/img/icon.png"))

            item.clicked.connect(clicked)

            item.addChild(child)
            fill_tree_item(child, val, exp, clicked)
    elif isinstance(value, list):
        for val in value:
            child = QTreeWidgetItem()
            item.addChild(child)
            if isinstance(val, dict):
                child.setText(0, "[dict]")
                fill_tree_item(child, val, exp, clicked)
            elif isinstance(val, list):
                child.setText(0, "[list]")
                fill_tree_item(child, val, exp, clicked)
            else:
                child.setText(0, unicode(val))
            child.setExpanded(True)

            item.clicked.connect(clicked)
    else:
        child = QTreeWidgetItem()
        child.setText(1, unicode(value))
        child.setIcon(0, QIcon(":/plugins/grData/assets/img/icon.png"))
        item.setIcon(0, QIcon(":/plugins/grData/assets/img/icon.png"))

        item.addChild(child)

        item.clicked.connect(clicked)


def fill_subtree_widget(parentItem, value, expanded=True, clicked=None):
    fill_tree_item(parentItem, value, expanded, clicked)


def fill_tree_widget(widget, value, expanded=False, clicked=None):
    widget.clear()
    fill_tree_item(widget.invisibleRootItem(), value, expanded, clicked)
