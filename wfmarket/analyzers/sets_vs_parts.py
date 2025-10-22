from typing import Callable, List, Optional, Any, Dict
import math
import time
from datetime import datetime, timezone, timedelta
import pandas as pd
from ..api import WFMClient

ProgressFn = Callable[[str, int, int, float], None]

def _determine_category(tags: Optional[List[str]]) -> str:
	if not tags:
		return "other"
	lower = {t.lower() for t in tags}
	if "warframe" in lower:
		return "warframes"
	if lower & {"primary", "rifle", "bow", "shotgun", "sniper", "launcher"}:
		return "primary"
	if lower & {"secondary", "pistol", "sidearm"}:
		return "secondary"
	if "melee" in lower:
		return "melee"
	if lower & {"archwing", "archgun", "archmelee", "space", "landing craft", "spacecraft"}:
		return "archwing"
	if lower & {"sentinel", "companion", "kubrow", "kavat", "moa", "beast", "robot"}:
		return "companions"
	return "other"

def _item_link(url_name: str, language: str) -> str:
	language_part = language.lower().replace("_", "-")
	if language_part == "en":
		language_part = ""
	else:
		language_part = f"/{language_part}"
	return f"https://warframe.market{language_part}/items/{url_name}?type=sell"

def _localized_name(entry: dict, language: str) -> str:
	if not entry:
		return ""
	name = entry.get("item_name")
	if name:
		return name
	lang_block = entry.get(language)
	if isinstance(lang_block, dict):
		name = lang_block.get("item_name")
		if name:
			return name
	en_block = entry.get("en")
	if isinstance(en_block, dict):
		name = en_block.get("item_name")
		if name:
			return name
	return entry.get("url_name") or ""

def _parse_iso8601(dt_str: str) -> Optional[datetime]:
	if not dt_str:
		return None
	try:
		return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
	except ValueError:
		return None

def _stats_last_24h(entries: List[dict], now_utc: datetime) -> tuple[int, Optional[float]]:
	cutoff = now_utc - timedelta(hours=24)
	total_volume = 0
	weighted_price = 0.0
	last_price = None
	has_price_data = False
	for entry in entries or []:
		price = entry.get("wa_price")
		if price is None:
			price = entry.get("avg_price")
		if price is None:
			price = entry.get("median")
		if price is not None:
			last_price = float(price)
		dt = _parse_iso8601(entry.get("datetime"))
		if dt is None or dt < cutoff:
			continue
		volume = entry.get("volume") or 0
		total_volume += volume
		if price is not None:
			weighted_price += float(price) * volume
			has_price_data = True
	if total_volume > 0 and has_price_data:
		return total_volume, weighted_price / total_volume
	if last_price is not None:
		return total_volume, last_price
	return total_volume, None

def _iter_prime_sets(client: WFMClient,
					 items_df: pd.DataFrame,
					 language: str,
					 limit_sets: Optional[int] = None,
					 progress_callback: Optional[ProgressFn] = None) -> List[dict]:
	out: List[dict] = []
	total_candidates = len(items_df)
	start_ts = time.perf_counter()
	processed = 0

	def report():
		if not progress_callback or processed == 0:
			return
		elapsed = time.perf_counter() - start_ts
		avg = elapsed / processed if processed else 0.0
		remaining = avg * max(total_candidates - processed, 0)
		progress_callback("scan", processed, total_candidates, remaining)

	for idx, (_, row) in enumerate(items_df.iterrows(), start=1):
		processed = idx
		url_name = row["url_name"]
		item_name = (row.get("item_name") or "").lower()
		if not (url_name.endswith("_set") or item_name.endswith(" set")):
			report()
			continue
		try:
			item = client.item_full(url_name)
		except Exception:
			report()
			continue
		items_in_set = item.get("items_in_set") or []
		set_objs = [i for i in items_in_set if i.get("set_root", False)]
		if not set_objs:
			report()
			continue
		set_obj = dict(set_objs[0])
		set_obj["items_in_set"] = items_in_set
		set_obj["url_name"] = url_name
		set_obj["item_name"] = row.get("item_name") or _localized_name(set_obj, language)
		set_obj["category"] = _determine_category(set_obj.get("tags"))
		out.append(set_obj)
		report()
		if limit_sets and len(out) >= limit_sets:
			break
	if progress_callback and (processed == 0 or processed < total_candidates):
		progress_callback("scan", processed, total_candidates, 0.0)
	return out

def build_sets_report(platform="pc", language="en", filter_contains="prime",
				  only_online=False, limit_sets: Optional[int]=None,
				  fetch_part_statistics: bool = True,
				  live_price_top_n: int = 4,
				  progress_callback: Optional[ProgressFn]=None) -> pd.DataFrame:
	client = WFMClient(platform=platform, language=language)
	items = client.list_items()
	items_df = pd.DataFrame(items)
	if filter_contains:
		mask_name = items_df["item_name"].str.contains(filter_contains, case=False, na=False)
		mask_url = items_df["url_name"].str.contains(filter_contains, case=False, na=False)
		items_df = items_df[mask_name | mask_url].reset_index(drop=True)
	set_objs = _iter_prime_sets(client, items_df, language=language, limit_sets=limit_sets, progress_callback=progress_callback)
	if limit_sets:
		set_objs = set_objs[:limit_sets]

	now_utc = datetime.now(timezone.utc)
	stats_cache: dict[str, tuple[int, Optional[float]]] = {}
	order_summary_cache: dict[tuple[str, bool, int], Dict[str, Any]] = {}

	def fetch_stats(url_name: str) -> tuple[int, Optional[float]]:
		if url_name in stats_cache:
			return stats_cache[url_name]
		entries = client.item_statistics(url_name)
		volume, avg_price = _stats_last_24h(entries, now_utc)
		stats_cache[url_name] = (volume, avg_price)
		return volume, avg_price

	def fetch_order_summary(url_name: str) -> Dict[str, Any]:
		key = (url_name, only_online, live_price_top_n)
		if key not in order_summary_cache:
			order_summary_cache[key] = client.sell_orders_summary(url_name, online_only=only_online, top_n=live_price_top_n)
		return order_summary_cache[key]

	set_records: List[Dict[str, Any]] = []
	total_sets = len(set_objs)
	start_ts = time.perf_counter()

	for idx, set_obj in enumerate(set_objs, start=1):
		set_url = set_obj["url_name"]
		set_volume, set_avg_price = fetch_stats(set_url)
		set_orders = fetch_order_summary(set_url)
		set_live_avg = set_orders.get("avg_price_top")
		set_live_err = set_orders.get("avg_price_error")
		parts_src = [p for p in set_obj.get("items_in_set") or [] if not p.get("set_root", False)]
		part_rows: List[dict] = []
		sum_parts_prices = 0.0 if fetch_part_statistics else None
		has_avg_prices = False
		sum_parts_live = 0.0
		has_live_prices = False
		for part in parts_src:
			part_url = part["url_name"]
			quantity = int(part.get("quantity_for_set") or 1)
			part_orders = fetch_order_summary(part_url)
			part_live_avg = part_orders.get("avg_price_top")
			part_live_err = part_orders.get("avg_price_error")
			part_volume: Optional[int] = None
			part_avg_price: Optional[float] = None
			if fetch_part_statistics:
				part_volume, part_avg_price = fetch_stats(part_url)
			else:
				part_volume = part_orders.get("order_count")
			part_name = _localized_name(part, language)
			if sum_parts_prices is not None and part_avg_price is not None:
				sum_parts_prices += part_avg_price * quantity
				has_avg_prices = True
			if part_live_avg is not None:
				sum_parts_live += part_live_avg * quantity
				has_live_prices = True
			part_rows.append({
				"group_url": set_url,
				"row_type": "part",
				"link": _item_link(part_url, language),
				"url_name": part_url,
				"item_name": part_name,
				"volume_24h": part_volume,
				"avg_price_24h": part_avg_price,
				"live_price_avg_top": part_live_avg,
				"live_price_err_top": part_live_err,
				"quantity_for_set": quantity,
				"sum_parts_avg_24h": None,
				"sum_parts_live_top": None,
				"pct_diff_avg_24h": None,
				"pct_diff_live_top": None,
				"category": set_obj.get("category", "other"),
			})
		if sum_parts_prices is not None and not has_avg_prices:
			sum_parts_prices = None
		if not has_live_prices:
			sum_parts_live = None
		price_diff = None
		if set_avg_price is not None and sum_parts_prices is not None:
			price_diff = round(sum_parts_prices - set_avg_price, 2)
		live_price_diff = None
		if set_live_avg is not None and sum_parts_live is not None:
			live_price_diff = round(sum_parts_live - set_live_avg, 2)
		pct_diff_avg = None
		if sum_parts_prices is not None and set_avg_price and set_avg_price > 0:
			pct_diff_avg = (sum_parts_prices - set_avg_price) / set_avg_price
		pct_diff_live = None
		if sum_parts_live is not None and set_live_avg and set_live_avg > 0:
			pct_diff_live = (sum_parts_live - set_live_avg) / set_live_avg
		category = set_obj.get("category", "other")
		set_row = {
			"group_url": set_url,
			"row_type": "set",
			"link": _item_link(set_url, language),
			"url_name": set_url,
			"item_name": _localized_name(set_obj, language),
			"volume_24h": set_volume,
			"avg_price_24h": set_avg_price,
			"live_price_avg_top": set_live_avg,
			"live_price_err_top": set_live_err,
			"price_diff": price_diff,
			"live_price_diff": live_price_diff,
			"quantity_for_set": 1,
			"sum_parts_avg_24h": sum_parts_prices,
			"sum_parts_live_top": sum_parts_live,
			"pct_diff_avg_24h": pct_diff_avg,
			"pct_diff_live_top": pct_diff_live,
			"category": category,
		}
		set_records.append({"set": set_row, "parts": part_rows})
		if progress_callback:
			elapsed = time.perf_counter() - start_ts
			avg = elapsed / idx if idx else 0.0
			remaining = avg * (total_sets - idx)
			progress_callback("calc", idx, total_sets, remaining)

	if progress_callback:
		progress_callback("calc", total_sets, total_sets, 0.0)

	def _sort_key(record: Dict[str, Any]):
		row = record["set"]
		live_diff = row.get("live_price_diff")
		if live_diff is not None:
			return (False, live_diff)
		diff = row.get("price_diff")
		return (diff is None, math.inf if diff is None else diff)

	set_records.sort(key=_sort_key)

	report_rows: List[dict] = []
	for record in set_records:
		set_row = record["set"]
		report_rows.append(set_row)
		for part_row in record["parts"]:
			qty = int(part_row.get("quantity_for_set") or 1)
			for idx in range(qty):
				row_copy = part_row.copy()
				row_copy["quantity_for_set"] = qty if idx == 0 else None
				row_copy["price_diff"] = None
				row_copy["live_price_diff"] = None
				report_rows.append(row_copy)

	report_df = pd.DataFrame(report_rows)
	if not report_df.empty:
		if "avg_price_24h" in report_df:
			report_df["avg_price_24h"] = report_df["avg_price_24h"].apply(lambda x: round(x, 2) if isinstance(x, (int, float)) else x)
		if "price_diff" in report_df:
			report_df["price_diff"] = report_df["price_diff"].apply(lambda x: round(x, 2) if isinstance(x, (int, float)) else x)
		if "live_price_avg_top" in report_df:
			report_df["live_price_avg_top"] = report_df["live_price_avg_top"].apply(lambda x: round(x, 2) if isinstance(x, (int, float)) else x)
		if "live_price_err_top" in report_df:
			report_df["live_price_err_top"] = report_df["live_price_err_top"].apply(lambda x: round(x, 2) if isinstance(x, (int, float)) else x)
		if "live_price_diff" in report_df:
			report_df["live_price_diff"] = report_df["live_price_diff"].apply(lambda x: round(x, 2) if isinstance(x, (int, float)) else x)
		if "sum_parts_avg_24h" in report_df:
			report_df["sum_parts_avg_24h"] = report_df["sum_parts_avg_24h"].apply(lambda x: round(x, 2) if isinstance(x, (int, float)) else x)
		if "sum_parts_live_top" in report_df:
			report_df["sum_parts_live_top"] = report_df["sum_parts_live_top"].apply(lambda x: round(x, 2) if isinstance(x, (int, float)) else x)
		if "pct_diff_avg_24h" in report_df:
			report_df["pct_diff_avg_24h"] = report_df["pct_diff_avg_24h"].apply(lambda x: round(x, 4) if isinstance(x, (int, float)) else x)
		if "pct_diff_live_top" in report_df:
			report_df["pct_diff_live_top"] = report_df["pct_diff_live_top"].apply(lambda x: round(x, 4) if isinstance(x, (int, float)) else x)
		for col in ("group_url", "quantity_for_set"):
			if col in report_df.columns:
				report_df.drop(columns=[col], inplace=True)
	return report_df
