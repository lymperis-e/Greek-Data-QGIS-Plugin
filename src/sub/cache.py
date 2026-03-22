import os
from os.path import dirname, join

_plugin_root = dirname(dirname(__file__))
CACHE_DIR = join(_plugin_root, ".cache")
ICONS_CACHE_DIR = join(CACHE_DIR, "icons")
CAPABILITIES_CACHE_DIR = join(CACHE_DIR, "capabilities")


def get_cache_dir() -> str:
    return CACHE_DIR


def get_icons_cache_dir() -> str:
    return ICONS_CACHE_DIR


def ensure_cache_directories() -> None:
    os.makedirs(ICONS_CACHE_DIR, exist_ok=True)
    os.makedirs(CAPABILITIES_CACHE_DIR, exist_ok=True)
