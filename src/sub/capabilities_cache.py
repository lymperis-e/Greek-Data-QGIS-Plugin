import json
import os
from os.path import join
from typing import Dict, Optional

from .cache import CAPABILITIES_CACHE_DIR, ensure_cache_directories

_cache_presence_index: Dict[str, bool] = {}


def _service_cache_file(service_id: str) -> str:
    safe_id = (service_id or "").strip() or "unknown_service"
    return join(CAPABILITIES_CACHE_DIR, f"{safe_id}.json")


def load_capabilities_cache(
    service_id: str,
) -> Optional[Dict[str, object]]:
    ensure_cache_directories()
    safe_id = (service_id or "").strip() or "unknown_service"
    cache_file = _service_cache_file(safe_id)

    if not os.path.isfile(cache_file):
        _cache_presence_index[safe_id] = False
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            payload = json.load(f)

        if not isinstance(payload, dict):
            _cache_presence_index[safe_id] = False
            return None

        _cache_presence_index[safe_id] = True

        return payload
    except Exception:
        _cache_presence_index[safe_id] = False
        return None


def has_capabilities_cache(service_id: str) -> bool:
    ensure_cache_directories()
    safe_id = (service_id or "").strip() or "unknown_service"

    if safe_id in _cache_presence_index:
        return _cache_presence_index[safe_id]

    cache_file = _service_cache_file(safe_id)
    exists = os.path.isfile(cache_file)
    _cache_presence_index[safe_id] = exists
    return exists


def save_capabilities_cache(
    service_id: str,
    payload: Dict[str, object],
) -> None:
    ensure_cache_directories()
    safe_id = (service_id or "").strip() or "unknown_service"
    cache_file = _service_cache_file(safe_id)
    tmp_file = f"{cache_file}.tmp"

    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    os.replace(tmp_file, cache_file)
    _cache_presence_index[safe_id] = True
