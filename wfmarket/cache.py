from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any, Optional

from .config import load_config

_CACHE_CONFIG = load_config().get("cache", {})
_CACHE_ENABLED = bool(_CACHE_CONFIG.get("enabled", True))
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
_CACHE_DIR = Path(_CACHE_CONFIG.get("directory") or _DEFAULT_CACHE_DIR)
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _key_to_path(key: str) -> Path:
	digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
	return _CACHE_DIR / f"{digest}.json"


def load_cache_entry(key: str, ttl_seconds: int) -> Optional[Any]:
	if not _CACHE_ENABLED or ttl_seconds <= 0:
		return None
	path = _key_to_path(key)
	if not path.exists():
		return None
	try:
		with path.open("r", encoding="utf-8") as fh:
			payload = json.load(fh)
	except (OSError, json.JSONDecodeError):
		return None
	timestamp = payload.get("timestamp")
	if timestamp is None:
		return None
	if time.time() - float(timestamp) > ttl_seconds:
		return None
	return payload.get("data")


def save_cache_entry(key: str, data: Any) -> None:
	if not _CACHE_ENABLED:
		return
	path = _key_to_path(key)
	try:
		with path.open("w", encoding="utf-8") as fh:
			json.dump({"timestamp": time.time(), "data": data}, fh)
	except OSError:
		pass
