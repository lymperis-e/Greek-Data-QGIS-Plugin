import json
import os
from os.path import join
from typing import Dict, Optional

from .cache import CAPABILITIES_CACHE_DIR, ensure_cache_directories


def _service_cache_file(service_id: str) -> str:
    safe_id = (service_id or "").strip() or "unknown_service"
    return join(CAPABILITIES_CACHE_DIR, f"{safe_id}.json")


def load_capabilities_cache(
    service_id: str,
) -> Optional[Dict[str, object]]:
    ensure_cache_directories()
    cache_file = _service_cache_file(service_id)

    if not os.path.isfile(cache_file):
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            payload = json.load(f)

        if not isinstance(payload, dict):
            return None

        return payload
    except Exception:
        return None


def save_capabilities_cache(
    service_id: str,
    payload: Dict[str, object],
) -> None:
    ensure_cache_directories()
    cache_file = _service_cache_file(service_id)
    tmp_file = f"{cache_file}.tmp"

    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    os.replace(tmp_file, cache_file)
