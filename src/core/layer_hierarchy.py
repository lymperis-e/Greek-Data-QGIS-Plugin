"""
Layer hierarchy module for preserving upstream server resource structures.

This module provides classes and utilities for building and working with hierarchical
layer structures that reflect the organization of upstream servers (ESRI groups,
GeoServer workspaces, WMS layer groups, etc.).
"""

from typing import Dict, List, Optional, Union


class LayerGroup:
    """
    Represents a group/folder of layers that may contain both individual layers
    and nested subgroups, mirroring the upstream server's resource structure.

    Attributes:
        name: The group name (e.g., "Administrative Boundaries")
        children: List of Layer or LayerGroup objects
    """

    def __init__(self, name: str, children: Optional[List] = None):
        """
        Initialize a LayerGroup.

        Args:
            name: Group name
            children: List of Layer or LayerGroup instances (defaults to empty list)
        """
        self.name = name
        self.children = children or []

    def add_child(self, child) -> None:
        """Add a child (Layer or LayerGroup) to this group."""
        self.children.append(child)

    def flatten(self) -> List:
        """
        Return a flat list of all Layer objects in this group and subgroups.

        Returns:
            List of Layer objects, recursively collected from all children
        """
        from .Layer import Layer

        flat = []
        for child in self.children:
            if isinstance(child, Layer):
                flat.append(child)
            elif isinstance(child, LayerGroup):
                flat.extend(child.flatten())
        return flat

    def to_dict(self) -> Dict:
        """
        Convert this LayerGroup to a JSON-serializable dictionary.

        Returns:
            Dict with 'type': 'group', 'name': str, 'children': list of dicts
        """
        return {
            "type": "group",
            "name": self.name,
            "children": [self._child_to_dict(child) for child in self.children],
        }

    @staticmethod
    def _child_to_dict(child) -> Dict:
        """Convert a child (Layer or LayerGroup) to dict format."""
        from .Layer import Layer

        if isinstance(child, LayerGroup):
            return child.to_dict()
        elif isinstance(child, Layer):
            return {
                "type": "layer",
                "layer_json": child.toJson(),
            }
        else:
            return {}

    @classmethod
    def from_dict(cls, data: Dict) -> "LayerGroup":
        """
        Reconstruct a LayerGroup from a dictionary (reverse of to_dict).

        Args:
            data: Dictionary with structure from to_dict()

        Returns:
            LayerGroup instance with reconstructed hierarchy
        """
        from .Layer import Layer

        group = cls(data.get("name", ""))
        for child_data in data.get("children", []):
            if child_data.get("type") == "group":
                group.add_child(LayerGroup.from_dict(child_data))
            elif child_data.get("type") == "layer":
                layer_json = child_data.get("layer_json", {})
                raw_type = layer_json.get("type", "")
                attributes = layer_json.get("attributes", {}) or {}
                raw_geometry = layer_json.get(
                    "geometry_type",
                    layer_json.get("geometryType", attributes.get("geometryType")),
                )

                # Backward compatibility: normalize legacy raw ArcGIS types from cached hierarchy
                # so geometry parsing/icon selection remains correct.
                if raw_type == "MapServer":
                    normalized_type = "esri-raster"
                elif raw_type == "FeatureServer":
                    normalized_type = "esri-vector"
                else:
                    normalized_type = raw_type

                layer = Layer(
                    idx=layer_json.get("id", 0),
                    url=layer_json.get("url", ""),
                    name=layer_json.get("name", ""),
                    data_model=normalized_type,
                    attributes=attributes,
                    geometry_type=raw_geometry,
                )
                group.add_child(layer)
        return group

    def __repr__(self) -> str:
        child_count = len(self.children)
        return f"<LayerGroup: {self.name} ({child_count} children)>"


def build_hierarchy_from_flat_with_paths(
    flat_layers: List, path_info: Dict[int, str]
) -> Optional[LayerGroup]:
    """
    Build a hierarchical LayerGroup structure from a flat layer list where each layer
    has an associated path (e.g., "Folder A/Subfolder B/Layer Name").

    Args:
        flat_layers: List of Layer objects
        path_info: Dict mapping layer index to path string (e.g., {0: "Group A/Layer 1"})

    Returns:
        LayerGroup representing the full hierarchy, or None if no valid paths
    """
    from .Layer import Layer

    if not flat_layers or not path_info:
        return None

    # Build hierarchy by creating groups as needed
    root = LayerGroup("Root")
    group_cache = {frozenset(): root}  # Map from path tuple to LayerGroup

    for layer in flat_layers:
        path_str = path_info.get(layer.id)
        if not path_str:
            path_str = layer.name
        
        # Split path into segments (e.g., "A/B/C" → ["A", "B", "C"])
        segments = [s.strip() for s in str(path_str).split("/") if s.strip()]

        if len(segments) == 1:
            # Single segment = direct child of root
            root.add_child(layer)
        else:
            # Multi-segment path: create/navigate group structure
            current_parent = root
            for i, segment in enumerate(segments[:-1]):
                # Build group cache key (path to this point)
                path_key = frozenset(enumerate(segments[:i+1]))
                if path_key not in group_cache:
                    group = LayerGroup(segment)
                    current_parent.add_child(group)
                    group_cache[path_key] = group
                current_parent = group_cache[path_key]

            # Add layer to final parent group
            current_parent.add_child(layer)

    return root if root.children else None
