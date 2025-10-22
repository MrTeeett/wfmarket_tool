"""
Reporting utilities for tracking Warframe mod prices (unranked vs fully ranked).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from ..api import WFMClient


RARITY_WEIGHTS: Dict[str, int] = {
	"common": 1,
	"uncommon": 2,
	"rare": 3,
	"legendary": 4,
}


@dataclass
class OrderSummary:
	order_count: int
	min_price: Optional[float]
	avg_price_top: Optional[float]
	avg_price_error: Optional[float]


def _summarize_orders(orders: Iterable[dict], target_rank: Optional[int], top_n: int) -> OrderSummary:
	prices: List[float] = []
	for order in orders:
		order_rank = order.get("mod_rank")
		if order_rank is None:
			order_rank = 0
		if target_rank is not None and order_rank != target_rank:
			continue
		price = order.get("platinum")
		if price is None:
			continue
		try:
			prices.append(float(price))
		except (TypeError, ValueError):
			continue
	prices.sort()
	order_count = len(prices)
	top_prices = prices[:top_n]
	if not top_prices:
		return OrderSummary(order_count=order_count, min_price=None, avg_price_top=None, avg_price_error=None)
	min_price = top_prices[0]
	avg_price = sum(top_prices) / len(top_prices)
	if len(top_prices) > 1:
		error = (max(top_prices) - min(top_prices)) / 2.0
	else:
		error = 0.0
	return OrderSummary(
		order_count=order_count,
		min_price=round(min_price, 2),
		avg_price_top=round(avg_price, 2),
		avg_price_error=round(error, 2),
	)


def _endo_cost_to_max(rarity: str, max_rank: int) -> Optional[int]:
	if max_rank is None or max_rank <= 0:
		return 0
	weight = RARITY_WEIGHTS.get((rarity or "").lower())
	if weight is None:
		return None
	return int(10 * weight * (2 ** int(max_rank) - 1))


def build_mods_report(
	platform: str = "pc",
	language: str = "en",
	rarity_filter: Optional[Iterable[str]] = None,
	only_online: bool = False,
	top_n: int = 4,
	filter_contains: Optional[str] = None,
	limit_items: Optional[int] = None,
) -> pd.DataFrame:
	client = WFMClient(platform=platform, language=language)
	items = client.list_items()
	filter_substring = (filter_contains or "").strip().lower() or None
	target_rarities = {r.lower() for r in rarity_filter} if rarity_filter else None

	candidates: List[Tuple[str, str]] = []
	seen: set[str] = set()
	for entry in items:
		url_name = entry.get("url_name")
		if not url_name or url_name in seen:
			continue
		item_name = entry.get("item_name") or ""
		if filter_substring and filter_substring not in item_name.lower() and filter_substring not in url_name.lower():
			continue
		candidates.append((url_name, item_name))
		seen.add(url_name)
	if limit_items:
		candidates = candidates[:limit_items]

	rows: List[Dict[str, object]] = []
	for url_name, fallback_name in candidates:
		try:
			item_full = client.item_full(url_name)
		except Exception:
			continue
		item_details = None
		for component in item_full.get("items_in_set") or []:
			if component.get("url_name") == url_name:
				item_details = component
				break
		if not item_details:
			continue
		tags = item_details.get("tags") or []
		if "mod" not in tags:
			continue
		rarity = (item_details.get("rarity") or "").lower()
		if target_rarities and rarity not in target_rarities:
			continue
		max_rank = item_details.get("mod_max_rank") or 0
		try:
			max_rank = int(max_rank)
		except (TypeError, ValueError):
			max_rank = 0
		display_name = None
		if isinstance(language, str):
			lang_block = item_details.get(language.lower())
			if isinstance(lang_block, dict):
				display_name = lang_block.get("item_name")
		if not display_name:
			display_name = item_details.get("en", {}).get("item_name") or fallback_name or url_name.replace("_", " ").title()

		try:
			orders = client.sell_orders(url_name, online_only=only_online)
		except Exception:
			continue
		summary_rank0 = _summarize_orders(orders, target_rank=0, top_n=top_n)
		summary_rank_max = _summarize_orders(orders, target_rank=max_rank if max_rank > 0 else 0, top_n=top_n)
		if summary_rank0.order_count == 0 and summary_rank_max.order_count == 0:
			continue

		endo_to_max = _endo_cost_to_max(rarity, max_rank)
		avg_unranked = summary_rank0.avg_price_top
		avg_maxed = summary_rank_max.avg_price_top if max_rank > 0 else summary_rank0.avg_price_top
		price_diff = None
		price_diff_percent = None
		endo_per_platinum = None
		platinum_per_endo = None
		if avg_unranked is not None and avg_maxed is not None:
			price_diff = round(avg_maxed - avg_unranked, 2)
			if avg_unranked:
				price_diff_percent = round((price_diff / avg_unranked) * 100, 2)
			if price_diff and price_diff > 0 and endo_to_max not in (None, 0):
				endo_per_platinum = round(endo_to_max / price_diff, 2)
				platinum_per_endo = round(price_diff / endo_to_max, 4)

		rows.append({
			"link": f"https://warframe.market/items/{url_name}?type=sell",
			"url_name": url_name,
			"item_name": display_name,
			"rarity": rarity or None,
			"max_rank": max_rank,
			"endo_to_max": endo_to_max,
			"unranked_min": summary_rank0.min_price,
			"unranked_avg": avg_unranked,
			"unranked_error": summary_rank0.avg_price_error,
			"unranked_orders": summary_rank0.order_count,
			"maxed_min": summary_rank_max.min_price,
			"maxed_avg": avg_maxed,
			"maxed_error": summary_rank_max.avg_price_error,
			"maxed_orders": summary_rank_max.order_count,
			"price_diff": price_diff,
			"price_diff_percent": price_diff_percent,
			"endo_per_platinum": endo_per_platinum,
			"platinum_per_endo": platinum_per_endo,
		})

	if not rows:
		return pd.DataFrame()

	df = pd.DataFrame(rows)
	# Sorting: prioritize mods with higher platinum gain per Endo, then higher price diff.
	if "platinum_per_endo" in df.columns:
		df = df.sort_values(
			by=["platinum_per_endo", "price_diff"],
			ascending=[False, False],
			na_position="last"
		).reset_index(drop=True)
	return df
