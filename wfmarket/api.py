from typing import Any, Dict, List, Optional, Tuple
import requests
from .util import rate_limited
from .config import get_config_value
from .cache import load_cache_entry, save_cache_entry

API_BASE = "https://api.warframe.market/v1"

class WFMClient:
	def __init__(self, platform: str = "pc", language: str = "en"):
		self.session = requests.Session()
		self.session.headers.update({
			"Language": language,
			"Platform": platform,
			"Accept": "application/json",
			"User-Agent": "wfmarket-tool/0.1"
		})
		self.platform = platform
		self.language = language
		self.statistics_ttl = int(get_config_value("cache", "statistics_ttl", default=900))
		self.orders_ttl = int(get_config_value("cache", "orders_ttl", default=300))
		self.item_ttl = int(get_config_value("cache", "item_ttl", default=3600))
		self.cache_enabled = bool(get_config_value("cache", "enabled", default=True))

	def _get(self, path: str, params: Dict = None) -> dict:
		with rate_limited():
			r = self.session.get(f"{API_BASE}{path}", params=params or {}, timeout=30)
			r.raise_for_status()
			return r.json()

	def list_items(self) -> List[dict]:
		data = self._get("/items")
		items = data["payload"]["items"]
		if isinstance(items, dict):
			lang = self.session.headers.get("Language", "en")
			# Warframe Market used to return language -> items mappings, but now often
			# returns a flat list. Support both response shapes.
			if lang in items:
				return items[lang]
			# fall back to English or the first available language
			if "en" in items:
				return items["en"]
			return next(iter(items.values()), [])
		return items

	def item_full(self, url_name: str) -> dict:
		cache_key = f"item:{self.platform}:{url_name}"
		cached = load_cache_entry(cache_key, self.item_ttl)
		if cached is not None:
			return cached
		data = self._get(f"/items/{url_name}")
		item = data["payload"]["item"]
		save_cache_entry(cache_key, item)
		return item

	def item_statistics(self, url_name: str, statistics_type: str = "48hours") -> List[dict]:
		cache_key = f"statistics:{self.platform}:{statistics_type}:{url_name}"
		cached = load_cache_entry(cache_key, self.statistics_ttl)
		if cached is not None:
			return cached
		data = self._get(f"/items/{url_name}/statistics", params={"type": statistics_type})
		stats = data["payload"].get("statistics_closed", {})
		entries = stats.get(statistics_type, [])
		save_cache_entry(cache_key, entries)
		return entries

	def sell_orders(self, url_name: str, online_only: bool = False) -> List[dict]:
		cache_key = f"orders_raw:{self.platform}:{url_name}"
		cached_orders = load_cache_entry(cache_key, self.orders_ttl) if self.cache_enabled else None
		if cached_orders is None:
			data = self._get(f"/items/{url_name}/orders")
			raw_orders = []
			for order in data["payload"]["orders"]:
				if order.get("order_type") != "sell":
					continue
				if not order.get("visible", True):
					continue
				raw_orders.append(order)
			if self.cache_enabled:
				save_cache_entry(cache_key, raw_orders)
		else:
			raw_orders = cached_orders
		out = []
		for o in raw_orders:
			if online_only:
				status = (o.get("user") or {}).get("status")
				if status not in ("ingame", "online"):
					continue
			out.append(o)
		return out

	def sell_orders_summary(
		self,
		url_name: str,
		online_only: bool = False,
		top_n: int = 4,
		mod_rank: Optional[int] = None,
	) -> Dict[str, Any]:
		rank_key = "*" if mod_rank is None else str(mod_rank)
		cache_key = f"orders:{self.platform}:{'online' if online_only else 'all'}:{url_name}:{top_n}:{rank_key}"
		cached = load_cache_entry(cache_key, self.orders_ttl)
		if cached is not None:
			return cached
		orders = self.sell_orders(url_name, online_only=online_only)
		if mod_rank is not None:
			filtered_orders = []
			for order in orders:
				order_rank = order.get("mod_rank")
				if order_rank is None:
					order_rank = 0
				if order_rank != mod_rank:
					continue
				filtered_orders.append(order)
			orders = filtered_orders
		prices = sorted(
			[o["platinum"] for o in orders if "platinum" in o],
			key=lambda p: p
		)
		top_prices = prices[:top_n]
		min_price = top_prices[0] if top_prices else None
		avg_top = sum(top_prices) / len(top_prices) if top_prices else None
		error = None
		if len(top_prices) > 1:
			error = (max(top_prices) - min(top_prices)) / 2.0
		elif top_prices:
			error = 0.0
		summary = {
			"order_count": len(prices),
			"min_price": float(min_price) if min_price is not None else None,
			"avg_price_top": float(avg_top) if avg_top is not None else None,
			"avg_price_error": float(error) if error is not None else None,
			"top_prices": [float(p) for p in top_prices],
		}
		save_cache_entry(cache_key, summary)
		return summary

	def min_price_and_count(self, url_name: str, online_only: bool = False, mod_rank: Optional[int] = None):
		summary = self.sell_orders_summary(url_name, online_only=online_only, mod_rank=mod_rank)
		return summary["min_price"], summary["order_count"]
