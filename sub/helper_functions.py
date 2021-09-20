from qgis.PyQt.QtWidgets import QTreeWidgetItem


def fill_tree_item(item, value, exp):
    item.setExpanded(exp)
    if type(value) is dict:
      for key, val in sorted(value.items()):
        child = QTreeWidgetItem()
        child.setText(0, unicode(key))
        item.addChild(child)
        fill_tree_item(child, val, exp)
    elif type(value) is list:
      for val in value:
        child = QTreeWidgetItem()
        item.addChild(child)
        if type(val) is dict:      
          child.setText(0, '[dict]')
          fill_tree_item(child, val, exp)
        elif type(val) is list:
          child.setText(0, '[list]')
          fill_tree_item(child, val, exp)
        else:
          child.setText(0, unicode(val))              
        child.setExpanded(True)
    else:
      child = QTreeWidgetItem()
      child.setText(0, unicode(value))
      item.addChild(child)


def fill_tree_widget(widget, value, expanded=False):
    widget.clear()
    fill_tree_item(widget.invisibleRootItem(), value, expanded)    







