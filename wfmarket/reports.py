from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

from .constants import MODS_COLUMN_ORDER


def prepare_mods_export(
        df: pd.DataFrame,
        text: Dict[str, Any],
        live_price_top_n: int,
) -> Tuple[pd.DataFrame, List[str], List[str]]:
        column_order = list(MODS_COLUMN_ORDER)
        for column in column_order:
                if column not in df.columns:
                        df[column] = None

        rarity_labels = text.get("mods_rarity_labels", {})
        if rarity_labels and "rarity" in df.columns:
                def _map_rarity(value: Any) -> Any:
                        if isinstance(value, str):
                                lower = value.lower()
                                if lower in rarity_labels:
                                        return rarity_labels[lower]
                                return value.title()
                        return value

                df["rarity"] = df["rarity"].apply(_map_rarity)

        headers_template = text.get("mods_headers", [])
        headers = [header.format(n=live_price_top_n) for header in headers_template]
        rename_map = {key: headers[idx] for idx, key in enumerate(column_order) if idx < len(headers)}

        export_df = df[column_order].rename(columns=rename_map)
        return export_df, column_order, headers
