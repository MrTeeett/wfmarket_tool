"""
Candidate scan for dissolving mods/rivens into Endo.
IMPORTANT: the actual Endo yield varies per item. This module uses an approximate
value – the price per abstract "rank_value" unit. A precise conversion can be
provided through the table in config.toml.
"""
from typing import Optional, Dict
import pandas as pd
from ..api import WFMClient

def riven_endo_candidates(platform="pc", language="en",
						  min_mastery: int = 8,
						  min_mod_rank: int = 8,
						  only_online: bool = False,
						  limit_items: Optional[int] = 300,
						  endo_table: Optional[Dict[str, Dict[int, int]]] = None) -> pd.DataFrame:
	"""
	endo_table: optional mapping {"rarity": {rank: endo_yield}} with accurate numbers.
	Warframe Market sell orders sometimes include 'mod_rank'. Rivens expose fewer
	fields, so mastery requirements are read from the item itself when available.
	"""
	client = WFMClient(platform=platform, language=language)
	items = client.list_items()
	df = pd.DataFrame(items)

	# Filter items by keywords to keep only mods and rivens.
	mask = (df["item_name"].str.contains("Riven", case=False, na=False) |
			df["item_name"].str.contains("Mod", case=False, na=False))
	df = df[mask].reset_index(drop=True)
	if limit_items:
		df = df.head(limit_items)

	rows = []
	for _, row in df.iterrows():
		url = row["url_name"]
		# Minimal price for the item itself
		p_min, cnt = client.min_price_and_count(url, online_only=only_online)
		if p_min is None:
			continue
		# Try to fetch mastery/rarity details when available
		try:
			full = client.item_full(url)
		except Exception:
			full = {}
		rarity = None
		mastery = None
		for it in (full.get("items_in_set") or []):
			if it.get("url_name") == url:
				rarity = it.get("rarity")
				mastery = it.get("mastery_level")
				break

		if mastery is not None and mastery < min_mastery:
			continue

		# Pseudo value: use the Endo table if provided; otherwise fall back to (mod_rank * 10)
		# Orders sometimes contain mod_rank; as a fallback assume the common maximum rank = 10
		rank_value = None
		if endo_table and rarity:
			# assume the item can reach rank 10
			rank_value = endo_table.get(str(rarity).lower(), {}).get(10)
		if rank_value is None:
			rank_value = 10 * 10  # rough placeholder

		price_per_unit = p_min / rank_value if rank_value else None

		rows.append({
			"link": f"https://warframe.market/items/{url}?type=sell",
			"item_name": row["item_name"],
			"url_name": url,
			"rarity": rarity,
			"mastery": mastery,
			"sell_orders_count": cnt,
			"min_price": p_min,
			"value_units": rank_value,
			"price_per_value": round(price_per_unit, 4) if price_per_unit else None
		})

	out = pd.DataFrame(rows)
	if not out.empty:
		out = out.sort_values(by="price_per_value", ascending=True, na_position="last").reset_index(drop=True)
	return out
