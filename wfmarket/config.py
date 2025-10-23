from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict
import copy
import tomllib
import tomli_w


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"

DEFAULT_CONFIG: Dict[str, Any] = {
        "platform": "pc",
        "language": "en",
        "ui_language": "en",
        "limits": {
                "rate_delay": 0.35,
        },
        "sets": {
                "out": "warframe_market_sets.xlsx",
                "only_online": False,
                "filter_contains": "prime",
                "limit_sets": 80,
                "progress": True,
                "fetch_part_statistics": True,
                "live_price_top_n": 4,
        },
        "endo": {
                "out": "endo_candidates.xlsx",
                "only_online": False,
                "min_mastery": 8,
                "min_mod_rank": 8,
                "limit_items": 300,
        },
        "mods": {
                "out": "mod_prices.xlsx",
                "only_online": False,
                "rarities": ["rare", "legendary"],
                "filter_contains": "",
                "limit_items": 200,
                "progress": True,
                "live_price_top_n": 3,
        },
        "gui": {
                "all_out": "warframe_market_reports.xlsx",
        },
        "cache": {
                "enabled": True,
                "directory": "",
                "statistics_ttl": 900,
                "orders_ttl": 300,
                "item_ttl": 3600,
        },
}


def _deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in updates.items():
                if (
                        key in base
                        and isinstance(base[key], dict)
                        and isinstance(value, dict)
                ):
                        _deep_merge(base[key], value)
                else:
                        base[key] = value
        return base


@lru_cache(maxsize=1)
def load_config(config_path: Path = CONFIG_PATH) -> Dict[str, Any]:
        config: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        if not config_path.exists():
                return config
        with config_path.open("rb") as fh:
                try:
                        user_config = tomllib.load(fh)
                except tomllib.TOMLDecodeError:
                        return config
        return _deep_merge(config, user_config)


def get_config_value(*keys: str, default: Any = None) -> Any:
        config = load_config()
        current: Any = config
        for key in keys:
                if not isinstance(current, dict):
                        return default
                current = current.get(key, default)
        return current if current is not None else default


def save_config(updates: Dict[str, Any], config_path: Path = CONFIG_PATH) -> Dict[str, Any]:
        """Persist a subset of settings to the TOML configuration file."""

        if not isinstance(updates, dict):
                raise TypeError("updates must be a dictionary")

        existing: Dict[str, Any] = {}
        if config_path.exists():
                with config_path.open("rb") as fh:
                        try:
                                existing = tomllib.load(fh)
                        except tomllib.TOMLDecodeError:
                                existing = {}

        merged = copy.deepcopy(existing)
        _deep_merge(merged, updates)

        if not config_path.parent.exists():
                config_path.parent.mkdir(parents=True, exist_ok=True)

        with config_path.open("wb") as fh:
                tomli_w.dump(merged, fh)

        load_config.cache_clear()
        return load_config(config_path)
